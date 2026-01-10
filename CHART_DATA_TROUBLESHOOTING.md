# Chart Data Troubleshooting Guide

## Issue: Chart Showing Stale Data

**Symptom:** Chart displays old data (e.g., December 2025) despite fresh data in database.

**Root Cause:** Client-side cache contains stale data and wasn't being invalidated.

---

## ✅ Complete Fix Applied

### 1. **Immediate Fix: Clear Stale Cache**
```bash
# Clear all cached chart data
rm -rf ~/Library/Caches/ChartBarsCache/*.json

# Or clear specific symbol/timeframe
rm ~/Library/Caches/ChartBarsCache/AAPL_h1.json
```

### 2. **Permanent Fix: Automatic Cache Invalidation**

Updated `client-macos/SwiftBoltML/Services/ChartCache.swift` with:

**Cache Age Limits:**
- **Intraday (m15, h1, h4)**: 24 hours max
- **Daily (d1)**: 7 days max
- **Weekly (w1)**: 30 days max

**Data Age Validation:**
- **Intraday**: Newest bar must be < 48 hours old
- **Daily**: Newest bar must be < 14 days old
- **Weekly**: Newest bar must be < 60 days old

**Behavior:**
- Cache automatically deleted if file age exceeds limits
- Cache automatically deleted if newest bar is too old
- Fresh data fetched from Edge Function after invalidation

---

## Data Flow Pipeline

```
Database (Alpaca data)
    ↓
get_chart_data_v2() function
    ↓
Edge Function (chart-data-v2)
    ↓
macOS App (ChartViewModel)
    ↓
ChartCache (with age validation)
    ↓
WebChart Display
```

---

## Verification Steps

### 1. **Check Database Has Fresh Data**
```sql
-- Run in Supabase SQL Editor
SELECT 
  COUNT(*) as total_bars,
  MIN(ts) as oldest_bar,
  MAX(ts) as newest_bar,
  MAX(ts)::date as newest_date
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
AND timeframe = 'h1'
AND provider = 'alpaca'
AND is_forecast = false;
```

**Expected:** `newest_date` should be recent (within last 2 days for intraday)

### 2. **Test Edge Function Directly**
```bash
curl -X POST https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart-data-v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -d '{"symbol":"AAPL","timeframe":"h1","days":60}' \
  | jq '.layers.historical.data[-1]'
```

**Expected:** Last bar should show recent timestamp

### 3. **Verify macOS App**
1. Quit and relaunch SwiftBoltML app
2. Select AAPL
3. Switch to 1H timeframe
4. Check console logs for:
   - `[ChartCache] Cache expired...` (if cache was stale)
   - `[ChartCache] Saved X bars...` (fresh data cached)
5. Verify chart shows recent data (Jan 9, 2026 or later)

---

## Prevention Strategy

### Daily Automated Backfill
GitHub Action runs daily at 6 AM UTC:
- `.github/workflows/daily-data-refresh.yml`
- Backfills all timeframes (m15, h1, h4, d1, w1)
- Validates data quality with gap detection
- Auto-retries any failed symbols/timeframes

### Gap Detection
Script to validate data completeness:
```bash
cd ml
python src/scripts/backfill_with_gap_detection.py --all
```

**Output shows:**
- Bar counts per symbol/timeframe
- Coverage percentage
- Gap detection results
- Recommended retry commands

### Manual Refresh
If data appears stale:
```bash
# Quick refresh for specific timeframe
cd ml
python src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL --timeframe h1

# Full refresh with gap detection
./src/scripts/smart_backfill_all.sh
```

---

## Common Issues & Solutions

### Issue: "Backfilling X years of intraday data... 10 bars loaded"
**Cause:** Orchestrator is still hydrating gaps  
**Solution:** Wait for backfill to complete, or run manual backfill:
```bash
python src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL --timeframe h1 --force
```

### Issue: Chart shows "Loading..." indefinitely
**Cause:** Edge Function error or network issue  
**Check:** Console logs for API errors  
**Solution:** Check Supabase Edge Function logs, verify API credentials

### Issue: Chart shows mix of old and new data
**Cause:** Multiple providers with different data ranges  
**Solution:** Alpaca-only migration ensures consistency (already applied)

### Issue: Cache keeps showing stale data
**Cause:** Cache invalidation not working  
**Solution:** 
1. Verify `ChartCache.swift` has age validation code
2. Clear cache manually: `rm -rf ~/Library/Caches/ChartBarsCache/*.json`
3. Rebuild app to ensure latest code

---

## Key Files

### Database
- `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`
  - `get_chart_data_v2()` function with Alpaca-only strategy

### Edge Function
- `backend/supabase/functions/chart-data-v2/index.ts`
  - Fetches data from database
  - Default: 60 days for intraday, 10 days forecast

### macOS App
- `client-macos/SwiftBoltML/Services/ChartCache.swift`
  - Cache with automatic age validation
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
  - Loads cached data first, then fetches fresh data

### Backfill Scripts
- `ml/src/scripts/alpaca_backfill_ohlc_v2.py` - Main backfill script
- `ml/src/scripts/backfill_with_gap_detection.py` - Validation script
- `ml/src/scripts/smart_backfill_all.sh` - Automated backfill with retry

---

## Testing Checklist

After any data-related changes:

- [ ] Database has fresh data (check with SQL query)
- [ ] Edge Function returns fresh data (test with curl)
- [ ] Cache is cleared or invalidated
- [ ] macOS app shows current data
- [ ] All timeframes load correctly (m15, h1, h4, d1, w1)
- [ ] 100-bar default zoom is working
- [ ] No gaps in data (run gap detection script)
- [ ] GitHub Action is scheduled and running

---

## Contact & Support

If issues persist:
1. Check Supabase Edge Function logs
2. Review macOS app console logs
3. Run gap detection validation
4. Verify Alpaca API credentials are valid
5. Check GitHub Action run status
