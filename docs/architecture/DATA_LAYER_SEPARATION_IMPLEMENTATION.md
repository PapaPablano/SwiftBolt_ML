# Data Layer Separation Implementation Summary

**Last Reviewed:** February 2026. Layer separation (historical / intraday / forecast) remains in place; primary OHLC provider is Alpaca; tables include `ohlc_bars_v2` with provider and `is_forecast` flags.

## Overview
Implemented a complete data layering architecture to separate historical, intraday, and forecast data flows, preventing the data corruption issues described in `@dataintegrity.md`.

## Problem Solved
Previously, three independent data flows (Polygon historical, Tradier intraday, ML forecasts) were writing to the same `ohlc_bars` table without coordination, causing:
- Massive price swings when intraday data overwrote historical data
- Mixed data sources with no tracking
- No way to distinguish between verified historical data and live intraday updates
- Forecasts mixed with actual data

## Solution Architecture

### Three Separate Layers
```
┌─────────────────────────────────────────────────────────────┐
│ Historical Layer (Polygon)                                   │
│ - Provider: "polygon"                                        │
│ - Dates: < TODAY                                             │
│ - Status: "verified"                                         │
│ - Immutable once written                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Intraday Layer (Tradier)                                     │
│ - Provider: "tradier"                                        │
│ - Dates: TODAY only                                          │
│ - Status: "live" (market open) → "verified" (after close)   │
│ - Updates every 15 min, locks at 4:05 PM ET                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Forecast Layer (ML)                                          │
│ - Provider: "ml_forecast"                                    │
│ - Dates: > TODAY (t+1 to t+10)                              │
│ - Status: "provisional"                                      │
│ - Includes confidence bands                                  │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. Database Schema (`ohlc_bars_v2`)
**File:** `backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql`

**Key Features:**
- `provider` field: tracks data source (polygon/tradier/ml_forecast)
- `is_intraday` / `is_forecast` flags for layer identification
- `data_status`: verified/live/provisional
- Confidence bands for forecasts: `upper_band`, `lower_band`, `confidence_score`
- Database-level validation triggers enforce separation rules
- Unique constraint: `(symbol_id, timeframe, ts, provider, is_forecast)`

**Functions:**
- `validate_ohlc_v2_write()`: Enforces layer separation rules at DB level
- `get_chart_data_v2()`: Fetches data with proper layer priority
- `is_intraday_locked()`: Checks if intraday writes are locked after market close

### 2. Validation Rules Engine
**File:** `backend/supabase/functions/_shared/data-validation.ts`

**Classes:**
- `PolygonHistoricalRule`: Only writes to dates < today
- `TradierIntradayRule`: Only writes to today, locks at 4:05 PM ET
- `MLForecastRule`: Only writes to future dates (t+1 to t+10)
- `DataValidator`: Orchestrates validation for all writes

**Usage:**
```typescript
const validation = dataValidator.validateWrite(bar);
if (!validation.valid) {
  console.error(validation.reason);
}
```

### 3. Historical Backfill Service
**File:** `ml/src/scripts/deep_backfill_ohlc_v2.py`

**Features:**
- Fetches from Polygon API with `adjusted=false`
- Writes with `provider='polygon'`, `is_forecast=false`, `is_intraday=false`
- Filters out today's data (historical only)
- Uses `ON CONFLICT DO NOTHING` to prevent updates

**Usage:**
```bash
python ml/src/scripts/deep_backfill_ohlc_v2.py --symbol AAPL
python ml/src/scripts/deep_backfill_ohlc_v2.py --all --timeframe d1
```

### 4. Intraday Update Service
**File:** `backend/supabase/functions/_shared/intraday-service-v2.ts`

**Features:**
- Fetches 5-min bars from Tradier
- Aggregates to daily OHLC
- Writes with `provider='tradier'`, `is_intraday=true`
- Checks market status and lock time
- Status: "live" during market hours, "verified" after close

**Usage:**
```typescript
const service = new IntradayServiceV2(supabaseUrl, supabaseKey, tradierToken);
await service.updateIntraday('AAPL');
```

### 5. ML Forecast Service
**File:** `ml/src/services/forecast_service_v2.py`

**Features:**
- Generates forecasts for t+1 to t+10 days
- Writes with `provider='ml_forecast'`, `is_forecast=true`
- Includes confidence bands from model output
- Gets base price from latest intraday or historical data

**Usage:**
```bash
python -m ml.src.services.forecast_service_v2 --symbol AAPL --horizon 10
python -m ml.src.services.forecast_service_v2 --all
```

### 6. Chart Query API
**File:** `backend/supabase/functions/chart-data-v2/index.ts`

**Features:**
- Fetches all three layers in one query
- Separates data by layer for client rendering
- Returns structured response with metadata

**Response Format:**
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "layers": {
    "historical": {
      "count": 60,
      "provider": "polygon",
      "data": [...]
    },
    "intraday": {
      "count": 1,
      "provider": "tradier",
      "data": [...]
    },
    "forecast": {
      "count": 10,
      "provider": "ml_forecast",
      "data": [...]
    }
  }
}
```

### 7. Data Migration
**File:** `backend/supabase/migrations/20260105000001_migrate_to_v2.sql`

**Features:**
- Copies existing data from `ohlc_bars` to `ohlc_bars_v2`
- Maps all existing data to `provider='polygon'`
- Only migrates historical data (dates < today)
- Creates unified view for backward compatibility

### 8. GitHub Actions Workflow
**File:** `.github/workflows/intraday-update-v2.yml`

**Features:**
- Runs every 15 minutes during market hours
- Checks market status before running
- Respects 4:05 PM ET lock time
- Updates all watchlist symbols

## Validation Rules Summary

### Historical (Polygon)
- ✅ Write to: dates < TODAY
- ❌ Cannot: write to today or future
- ❌ Cannot: be marked as intraday or forecast
- ✅ Status: "verified"

### Intraday (Tradier)
- ✅ Write to: TODAY only
- ❌ Cannot: write to past or future
- ✅ Must: be marked as intraday
- ✅ Lock: 5 min after market close (4:05 PM ET)
- ✅ Status: "live" → "verified"

### Forecast (ML)
- ✅ Write to: dates > TODAY (t+1 to t+10)
- ❌ Cannot: write to today or past
- ✅ Must: include confidence bands
- ✅ Status: "provisional"

## Migration Plan

### Phase 1: Deploy New Schema ✅
- [x] Create `ohlc_bars_v2` table
- [x] Add validation triggers
- [x] Create helper functions

### Phase 2: Deploy Services ✅
- [x] Validation rules engine
- [x] Historical backfill script
- [x] Intraday update service
- [x] ML forecast service
- [x] Chart query API

### Phase 3: Data Migration (Next Steps)
1. Run migration SQL to copy existing data
2. Test chart queries on staging
3. Update client applications to use new API
4. Run backfill for any missing historical data
5. Enable intraday updates workflow
6. Enable forecast generation

### Phase 4: Cutover (After Testing)
1. Switch all writes to `ohlc_bars_v2`
2. Update all Edge Functions
3. Monitor for issues
4. Archive old `ohlc_bars` table

## Testing Checklist

- [ ] Run database migrations on staging
- [ ] Test historical backfill for sample symbols
- [ ] Test intraday updates during market hours
- [ ] Test forecast generation
- [ ] Test chart query API with all three layers
- [ ] Verify validation rules block invalid writes
- [ ] Test backward compatibility view
- [ ] Load test with production volume

## Expected Benefits

✅ **Historical Accuracy**: Polygon data never corrupted by intraday overrides  
✅ **Live Precision**: Tradier updates only affect TODAY  
✅ **Forecast Clarity**: ML predictions separate from actual data  
✅ **No Massive Swings**: Each layer isolated and versioned  
✅ **Auditability**: `provider` + `fetched_at` tracks every row's origin  
✅ **Data Quality**: Validation rules prevent corruption at write time  

## Next Steps

1. **Deploy migrations** to staging environment
2. **Run backfill** for historical data: `python ml/src/scripts/deep_backfill_ohlc_v2.py --all`
3. **Test intraday updates** manually during market hours
4. **Generate test forecasts**: `python -m ml.src.services.forecast_service_v2 --symbol AAPL`
5. **Update client apps** to use `chart-data-v2` endpoint
6. **Enable GitHub Actions** for automated updates
7. **Monitor data quality** for first week
8. **Archive old table** after confidence period

## Files Created

### Database
- `backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql`
- `backend/supabase/migrations/20260105000001_migrate_to_v2.sql`

### Services
- `backend/supabase/functions/_shared/data-validation.ts`
- `backend/supabase/functions/_shared/intraday-service-v2.ts`
- `backend/supabase/functions/chart-data-v2/index.ts`
- `ml/src/services/forecast_service_v2.py`

### Scripts
- `ml/src/scripts/deep_backfill_ohlc_v2.py`

### Workflows
- `.github/workflows/intraday-update-v2.yml`

## Documentation
- `dataintegrity.md` - Original problem analysis
- `DATA_LAYER_SEPARATION_IMPLEMENTATION.md` - This document
