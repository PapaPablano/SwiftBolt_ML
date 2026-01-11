# Multi-Timeframe Data Integration Guide

## Overview

This document describes the comprehensive improvements made to ensure accurate, fresh, and ML-ready chart data across all timeframes (m15, h1, h4, d1, w1) using Alpaca as the primary data provider.

## Problem Statement

The application experienced issues with:
1. **Wildly inaccurate multi-timeframe chart data** - showing stale data months old
2. **Insufficient historical depth** - not enough bars for ML training
3. **Lack of transparency** - users couldn't see data freshness or quality
4. **No monitoring** - no automated detection of data staleness

## Solution Architecture

### 1. Enhanced Data Quality Tracking

**Backend: `/backend/supabase/functions/chart-data-v2/index.ts`**

Added comprehensive data quality metrics to every chart data response:

```typescript
dataQuality: {
  dataAgeHours: 2,           // How old is the newest bar
  isStale: false,            // Is data >24 hours old?
  hasRecentData: true,       // Is data <4 hours old?
  historicalDepthDays: 365,  // Total historical coverage
  sufficientForML: true,     // >= 250 bars for ML training
  barCount: 500              // Total number of bars
}
```

**Frontend: `/client-macos/SwiftBoltML/Models/ChartDataV2Response.swift`**

Enhanced Swift models to deserialize and present data quality:
- `DataQuality` struct with computed properties
- Helper methods `isDataFresh`, `isDataStale`, `dataAgeDescription`
- Status descriptions for user-friendly display

### 2. Visual Data Quality Indicators

**Component: `/client-macos/SwiftBoltML/Views/DataQualityBadge.swift`**

Created a UI component that displays:
- ✅ Fresh data indicator (<4 hours old)
- 🔄 Recent data indicator (<24 hours old)
- ⚠️ Stale data warning (>24 hours old)
- Clickable popover with detailed quality report
- ML training readiness status

**Integration: `/client-macos/SwiftBoltML/Views/ChartView.swift`**

Added badge to chart header next to symbol ticker:
```swift
ChartHeader(
    symbol: chartViewModel.selectedSymbol,
    dataQuality: chartViewModel.chartDataV2?.dataQuality
)
```

### 3. Automated Data Quality Validation

**Script: `/scripts/validate_data_quality.sh`**

Validates data quality against requirements:

| Timeframe | Min Bars | Max Age | Purpose |
|-----------|----------|---------|---------|
| m15       | 1000     | 4 hours | Intraday trading |
| h1        | 500      | 24 hours| Short-term analysis |
| h4        | 250      | 48 hours| Swing trading |
| d1        | 250      | 72 hours| Long-term analysis |
| w1        | 52       | 1 week  | Strategic analysis |

**Output:**
```
Symbol   Timeframe    Bars  Oldest           Newest           Age (hrs)  Depth (d)  Status
========================================================================================
AAPL     d1           500   2023-01-10       2025-01-10       2.0        730        ✅ OK
AAPL     h1           480   2024-07-15       2025-01-10       3.0        180        ✅ OK
AAPL     m15          1200  2024-12-20       2025-01-10       1.5        22         ✅ OK
```

### 4. Comprehensive Backfill System

**Script: `/scripts/comprehensive_backfill.sh`**

Ensures sufficient historical data depth:
- m15: 60 days (intraday patterns)
- h1: 180 days (6 months for patterns)
- h4: 365 days (1 year for seasonality)
- d1: 730 days (2 years for ML training)
- w1: 1460 days (4 years for long-term trends)

**Features:**
- Parallel processing of multiple symbols
- Rate-limited to respect Alpaca API limits (200 req/min)
- Automatic validation after completion
- Detailed logging and result tracking

**Usage:**
```bash
# Backfill specific symbols
./scripts/comprehensive_backfill.sh "AAPL,MSFT,NVDA"

# Backfill with force refresh
./scripts/comprehensive_backfill.sh "AAPL,MSFT,NVDA" true
```

### 5. Continuous Monitoring

**Workflow: `/.github/workflows/data-quality-monitor.yml`**

Automated monitoring that:
- Runs every 6 hours
- Validates data quality for all symbols
- Creates GitHub issues on repeated failures
- Uploads validation reports as artifacts
- Sends warnings for stale data

**GitHub Actions Integration:**
- `alpaca-intraday-cron.yml` - Updates intraday data every 15 minutes during market hours
- `daily-data-refresh.yml` - Full refresh of all timeframes daily
- `data-quality-monitor.yml` - Validates data quality every 6 hours

## Implementation Details

### Data Flow

```
Alpaca API
    ↓ (GitHub Actions Cron)
alpaca_backfill_ohlc_v2.py
    ↓ (Writes to)
PostgreSQL (ohlc_bars_v2)
    ↓ (Queried by)
get_chart_data_v2_dynamic()
    ↓ (Returns)
chart-data-v2 Edge Function
    ↓ (With DataQuality)
Swift APIClient
    ↓ (Deserializes)
ChartDataV2Response
    ↓ (Displays)
DataQualityBadge
```

### Database Schema

The `ohlc_bars_v2` table stores all OHLC data:

```sql
CREATE TABLE ohlc_bars_v2 (
    id UUID PRIMARY KEY,
    symbol_id UUID NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open DECIMAL(10, 4),
    high DECIMAL(10, 4),
    low DECIMAL(10, 4),
    close DECIMAL(10, 4),
    volume BIGINT,
    provider VARCHAR(20) NOT NULL,  -- 'alpaca', 'polygon', etc.
    is_intraday BOOLEAN DEFAULT false,
    is_forecast BOOLEAN DEFAULT false,
    data_status VARCHAR(20) DEFAULT 'complete',
    UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)
);
```

### API Response Structure

```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "layers": {
    "historical": {
      "count": 450,
      "provider": "alpaca",
      "data": [...],
      "oldestBar": "2023-01-10T00:00:00Z",
      "newestBar": "2025-01-10T00:00:00Z"
    },
    "intraday": {
      "count": 0,
      "provider": "none",
      "data": []
    },
    "forecast": {
      "count": 10,
      "provider": "ml_forecast",
      "data": [...]
    }
  },
  "dataQuality": {
    "dataAgeHours": 2,
    "isStale": false,
    "hasRecentData": true,
    "historicalDepthDays": 730,
    "sufficientForML": true,
    "barCount": 450
  },
  "mlSummary": {...},
  "indicators": {...}
}
```

## Deployment Checklist

### 1. Backend Deployment

- [ ] Deploy enhanced `chart-data-v2` edge function to Supabase
- [ ] Verify function returns `dataQuality` in response
- [ ] Test API responses across all timeframes

### 2. Database Migration

- [ ] Apply `20260111000000_dynamic_chart_data_query.sql` if not already applied
- [ ] Verify `get_chart_data_v2_dynamic()` function exists
- [ ] Test query returns most recent bars correctly

### 3. Data Backfill

- [ ] Run comprehensive backfill for all symbols:
  ```bash
  cd /path/to/SwiftBolt_ML
  ./scripts/comprehensive_backfill.sh
  ```
- [ ] Validate data quality:
  ```bash
  ./scripts/validate_data_quality.sh
  ```
- [ ] Check all timeframes have >= 250 bars (for ML)

### 4. Frontend Deployment

- [ ] Build and test macOS app with new DataQualityBadge
- [ ] Verify badge displays correctly in chart header
- [ ] Test popover shows detailed quality information
- [ ] Verify badge updates when switching timeframes

### 5. GitHub Actions

- [ ] Enable `data-quality-monitor.yml` workflow
- [ ] Verify `alpaca-intraday-cron.yml` is running
- [ ] Check workflow secrets are configured:
  - `ALPACA_API_KEY`
  - `ALPACA_API_SECRET`
  - `DATABASE_URL`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`

## Monitoring & Alerts

### Data Quality Dashboard

View current data quality:
1. Open macOS app
2. Select any symbol
3. Check badge next to ticker symbol:
   - 🟢 Green checkmark = Fresh data
   - 🔵 Blue clock = Recent data
   - 🟠 Orange warning = Stale data
4. Click badge for detailed report

### GitHub Actions Monitoring

Check workflow runs:
```bash
# View recent intraday updates
gh run list --workflow=alpaca-intraday-cron.yml --limit 10

# View data quality reports
gh run list --workflow=data-quality-monitor.yml --limit 10

# View daily refreshes
gh run list --workflow=daily-data-refresh.yml --limit 10
```

### Database Queries

Check data freshness directly:

```sql
-- Check newest bars per timeframe
SELECT 
  s.ticker,
  o.timeframe,
  MAX(o.ts) as newest_bar,
  EXTRACT(HOUR FROM (NOW() - MAX(o.ts))) as age_hours,
  COUNT(*) as bar_count
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker IN ('AAPL', 'MSFT', 'NVDA')
  AND o.is_forecast = false
  AND o.provider = 'alpaca'
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
```

## Troubleshooting

### Issue: Data Quality Badge Shows Stale Data

**Symptoms:**
- Badge shows orange warning
- "Data is stale (> 24 hours old)" message

**Solutions:**
1. Check if GitHub Actions are running:
   ```bash
   gh run list --workflow=alpaca-intraday-cron.yml --limit 5
   ```

2. Manually trigger data refresh:
   ```bash
   gh workflow run daily-data-refresh.yml
   ```

3. Run comprehensive backfill:
   ```bash
   ./scripts/comprehensive_backfill.sh "AAPL"
   ```

### Issue: Insufficient Bars for ML

**Symptoms:**
- Badge shows "⚠️ Insufficient for ML"
- `barCount` < 250

**Solutions:**
1. Run backfill with longer history:
   ```bash
   cd ml
   python src/scripts/alpaca_backfill_ohlc_v2.py \
     --symbol AAPL \
     --timeframe d1 \
     --force
   ```

2. Verify Alpaca API has historical data:
   - Check if symbol is tradable
   - Verify date range is within Alpaca's coverage

### Issue: Badge Not Showing

**Symptoms:**
- No badge appears next to ticker symbol
- `dataQuality` is nil in response

**Solutions:**
1. Verify edge function is deployed
2. Check API response includes `dataQuality` field
3. Clear app cache and reload:
   ```swift
   ChartCache.clearAll()
   URLCache.shared.removeAllCachedResponses()
   ```

## Future Enhancements

### Phase 1: Real-Time Updates
- [ ] WebSocket integration for live data streaming
- [ ] Automatic refresh when market opens
- [ ] Push notifications for data staleness

### Phase 2: Predictive Monitoring
- [ ] Predict when data will become stale
- [ ] Pre-emptive backfill before gaps occur
- [ ] ML model for data quality forecasting

### Phase 3: Multi-Provider Fallback
- [ ] Automatic fallback to secondary providers when Alpaca fails
- [ ] Provider quality scoring
- [ ] Intelligent provider selection

## References

- [Alpaca Market Data API](https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data)
- [Database Schema Documentation](../docs/database-schema.md)
- [Edge Functions Guide](../docs/edge-functions.md)
- [GitHub Actions Workflows](../.github/workflows/README.md)

## Support

For issues or questions:
1. Check GitHub Issues for similar problems
2. Review workflow run logs in GitHub Actions
3. Check Supabase Edge Function logs
4. Review data quality validation reports

---

**Last Updated:** 2026-01-11
**Version:** 1.0.0
