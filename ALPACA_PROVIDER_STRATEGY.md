# Alpaca-Only Provider Strategy

## Overview

As of January 2026, SwiftBoltML uses **Alpaca as the single primary data provider** for all OHLC data across all timeframes (m15, h1, h4, d1, w1).

Legacy providers (Polygon, Tradier, Yahoo Finance) are available as **read-only fallback** for historical data continuity.

---

## Provider Hierarchy

### Primary Provider: Alpaca
- **Coverage**: All timeframes (15m, 1h, 4h, daily, weekly)
- **History**: 7+ years of historical data
- **Real-time**: Live market data during trading hours
- **Quality**: High-quality, verified market data
- **Status**: ✅ Active for all new data writes

### Legacy Providers (Read-Only Fallback)
1. **Polygon** - Historical data (pre-Alpaca migration)
2. **Tradier** - Historical intraday data (pre-Alpaca migration)
3. **Yahoo Finance** - Historical daily/weekly data (pre-Alpaca migration)

**Note**: Legacy providers are only queried if Alpaca data is missing for a specific timestamp. No new data is written with legacy providers.

---

## Database Strategy

### Write Rules (Enforced by Trigger)
```sql
-- New data MUST use 'alpaca' provider
-- Legacy providers are read-only
CREATE TRIGGER validate_ohlc_v2_write
  BEFORE INSERT OR UPDATE ON ohlc_bars_v2
  FOR EACH ROW
  EXECUTE FUNCTION validate_ohlc_v2_write();
```

**Validation Logic:**
- ✅ Allow: `provider = 'alpaca'` (all writes)
- ✅ Allow: `provider IN ('polygon', 'tradier', 'yfinance')` (UPDATE only, for corrections)
- ❌ Block: New INSERT with legacy providers

### Query Strategy (get_chart_data_v2)

**For Intraday (m15, h1, h4):**
```sql
-- 1. Query Alpaca data (primary)
SELECT * FROM ohlc_bars_v2 
WHERE provider = 'alpaca' AND timeframe = 'h1'

UNION ALL

-- 2. Query legacy data (fallback, only if Alpaca missing)
SELECT * FROM ohlc_bars_v2 
WHERE provider IN ('polygon', 'tradier')
  AND NOT EXISTS (
    SELECT 1 FROM ohlc_bars_v2 
    WHERE provider = 'alpaca' AND ts = o.ts
  )

-- 3. Deduplicate with priority: Alpaca > Polygon > Tradier
ORDER BY ts ASC, 
  CASE provider 
    WHEN 'alpaca' THEN 1 
    WHEN 'polygon' THEN 2 
    WHEN 'tradier' THEN 3 
  END ASC
```

**For Daily/Weekly (d1, w1):**
```sql
-- Same strategy: Alpaca primary, legacy fallback
-- Priority: Alpaca > Polygon > YFinance
```

---

## Data Layers (Edge Function)

The `chart-data-v2` Edge Function returns three layers:

### 1. Historical Layer
- **Source**: Alpaca (primary) or legacy providers (fallback)
- **Criteria**: `DATE(ts) < CURRENT_DATE`
- **Flag**: `is_intraday = false`

### 2. Intraday Layer
- **Source**: Alpaca only
- **Criteria**: `DATE(ts) = CURRENT_DATE`
- **Flag**: `is_intraday = true`

### 3. Forecast Layer
- **Source**: ML predictions
- **Criteria**: `DATE(ts) > CURRENT_DATE`
- **Flag**: `is_forecast = true`

---

## Client-Side Handling (macOS App)

### ChartViewModel.buildBars()

**For Intraday Timeframes (m15, h1, h4):**
```swift
// Merge historical (Alpaca backfill) + today's intraday (Alpaca)
let historical = response.layers.historical.data  // Alpaca historical
let intraday = response.layers.intraday.data      // Alpaca today
let merged = (historical + intraday).sorted(by: { $0.ts < $1.ts })
```

**For Daily/Weekly (d1, w1):**
```swift
// Prefer historical, fallback to intraday
let bars = !historical.isEmpty ? historical : intraday
```

### Provider Logging
Console logs show provider for each layer:
```
[DEBUG] - Historical: 1000 (provider: alpaca)
[DEBUG] - Intraday: 6 (provider: alpaca)
[DEBUG] - Final bars: 1006
```

---

## Backfill Scripts

### Primary Script: alpaca_backfill_ohlc_v2.py

**Usage:**
```bash
# Backfill all watchlist symbols for h1 timeframe
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1

# Force re-backfill specific symbol
python src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL --timeframe h1 --force
```

**What it does:**
1. Fetches data from Alpaca API
2. Writes to `ohlc_bars_v2` with `provider='alpaca'`
3. Uses `ON CONFLICT DO NOTHING` to avoid duplicates
4. Respects rate limits (200ms delay between requests)

### Gap Detection: backfill_with_gap_detection.py

**Usage:**
```bash
# Validate all data and detect gaps
python src/scripts/backfill_with_gap_detection.py --all
```

**What it does:**
1. Checks for missing data periods
2. Calculates coverage percentage
3. Identifies which symbols/timeframes need attention
4. Provides retry commands for gaps

---

## Migration Status

### ✅ Completed
- Database schema updated with Alpaca provider support
- `get_chart_data_v2()` function uses Alpaca-first strategy
- Write validation trigger enforces Alpaca-only for new data
- Python backfill scripts use Alpaca API
- Edge Function updated with Alpaca-only comments
- macOS app comments updated to reference Alpaca
- GitHub Action for daily automated backfill

### 📊 Data Status
- **Alpaca data**: Jan 9, 2026 (current)
- **Legacy data**: Pre-migration historical data (read-only)
- **Coverage**: 100% for watchlist symbols across all timeframes

---

## Troubleshooting

### Issue: Logs show "provider: polygon" or "provider: tradier"

**Cause**: Query is returning legacy fallback data because Alpaca data is missing.

**Solution**:
```bash
# Force backfill with Alpaca
python src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL --timeframe h1 --force
```

### Issue: "Duplicate key" error during backfill

**Cause**: Data already exists for that timestamp.

**Solution**: This is normal and safe. The script uses `ON CONFLICT DO NOTHING` to skip duplicates.

### Issue: Rate limit errors from Alpaca

**Cause**: Too many requests in short time.

**Solution**: Script has built-in rate limiting (200ms delay). If you hit limits, wait 1 minute and retry.

---

## API Credentials

### Required Environment Variables
```bash
# In root .env file
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
```

### GitHub Secrets (for Actions)
```
ALPACA_API_KEY
ALPACA_API_SECRET
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL
```

---

## Benefits of Alpaca-Only Strategy

1. **Consistency**: Single source of truth for all data
2. **Quality**: High-quality, verified market data
3. **Coverage**: 7+ years of history across all timeframes
4. **Simplicity**: No complex provider routing logic
5. **Reliability**: Fewer points of failure
6. **Cost**: Free tier sufficient for current usage
7. **Maintenance**: Single API to maintain and monitor

---

## References

- Database migration: `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`
- Backfill script: `ml/src/scripts/alpaca_backfill_ohlc_v2.py`
- Gap detection: `ml/src/scripts/backfill_with_gap_detection.py`
- Edge Function: `backend/supabase/functions/chart-data-v2/index.ts`
- Chart logic: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
