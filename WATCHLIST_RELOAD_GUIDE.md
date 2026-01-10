# Watchlist Chart Data Reload Guide
**Date:** January 10, 2026  
**Purpose:** Clear legacy provider data and reload with Alpaca-only  
**Status:** Ready to execute

---

## 📋 What This Does

### Clears
- ❌ All OHLC data from legacy providers (polygon, yfinance, tradier, finnhub)
- ❌ Old Alpaca data (if any mixed with legacy)

### Preserves
- ✅ ML forecasts (`provider = 'ml_forecast'`)
- ✅ Options rankings
- ✅ Symbol metadata
- ✅ Watchlist items
- ✅ User preferences

### Reloads
- ✅ Fresh Alpaca data for h1 (hourly) timeframe
- ✅ Fresh Alpaca data for d1 (daily) timeframe
- ✅ ~100 bars per symbol for optimal chart display

---

## 🎯 Affected Symbols (7 Total)

- AAPL (Apple)
- AMD (Advanced Micro Devices)
- AMZN (Amazon)
- CRWD (CrowdStrike)
- MU (Micron Technology)
- NVDA (NVIDIA)
- PLTR (Palantir)

---

## 🚀 Execution Options

### Option 1: Automated Script (Recommended)

```bash
# From SwiftBolt_ML root directory
./backend/scripts/reload_watchlist_alpaca.sh
```

**What it does:**
1. Clears legacy data
2. Backfills h1 (hourly) data
3. Backfills d1 (daily) data
4. Verifies data integrity
5. Shows summary report

**Time:** ~5-10 minutes

---

### Option 2: Manual Step-by-Step

#### Step 1: Clear Data
```bash
supabase db execute -f backend/scripts/clear_watchlist_chart_data.sql
```

#### Step 2: Backfill Hourly Data
```bash
cd ml
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1
```

#### Step 3: Backfill Daily Data
```bash
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe d1
```

#### Step 4: Verify
```sql
SELECT 
  s.ticker,
  ob.provider,
  ob.timeframe,
  COUNT(*) as bar_count,
  MAX(ob.ts) as latest_bar
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'alpaca'
GROUP BY s.ticker, ob.provider, ob.timeframe
ORDER BY s.ticker, ob.timeframe;
```

---

### Option 3: SQL Only (No Backfill)

If you just want to clear data and backfill later:

```bash
supabase db execute -f backend/scripts/clear_watchlist_chart_data.sql
```

Then run backfill manually when ready.

---

## ✅ Expected Results

### After Cleanup
```
Symbol | Provider    | Bars Deleted
-------|-------------|-------------
AAPL   | polygon     | ~500
AAPL   | yfinance    | ~200
NVDA   | polygon     | ~500
...    | ...         | ...
```

### After Backfill
```
Symbol | Provider | Timeframe | Bar Count | Latest Bar
-------|----------|-----------|-----------|------------------
AAPL   | alpaca   | h1        | ~100      | 2026-01-10 15:00
AAPL   | alpaca   | d1        | ~100      | 2026-01-10
AMD    | alpaca   | h1        | ~100      | 2026-01-10 15:00
AMD    | alpaca   | d1        | ~100      | 2026-01-10
...    | ...      | ...       | ...       | ...
```

---

## 🧪 Testing Checklist

After reload, verify in macOS app:

### Chart Display
- [ ] Charts load with 100 bars on initial view
- [ ] Provider shows "alpaca" in metadata
- [ ] No gaps or missing data
- [ ] Timestamps are correct (ET timezone)

### Chart Standards (New)
- [ ] Default zoom: 100 bars visible
- [ ] Bar spacing: 12px (clear separation)
- [ ] Right offset: 30px (edge spacing)
- [ ] Time scale: uniform distribution

### Pan/Zoom Controls
- [ ] Zoom in/out works smoothly
- [ ] Pan left/right respects boundaries
- [ ] Reset returns to 100 most recent bars
- [ ] No performance lag

### Multi-Symbol Test
- [ ] Switch between AAPL → NVDA → CRWD
- [ ] Each symbol loads correctly
- [ ] Chart settings persist
- [ ] No data mixing between symbols

---

## 🔍 Verification Queries

### Check Data Coverage
```sql
SELECT 
  s.ticker,
  ob.timeframe,
  COUNT(*) as bars,
  MIN(DATE(ob.ts)) as oldest,
  MAX(DATE(ob.ts)) as newest,
  MAX(DATE(ob.ts)) - MIN(DATE(ob.ts)) as days_coverage
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'alpaca'
GROUP BY s.ticker, ob.timeframe
ORDER BY s.ticker, ob.timeframe;
```

### Check for Legacy Data (Should be empty)
```sql
SELECT 
  s.ticker,
  ob.provider,
  COUNT(*) as legacy_bars
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider IN ('polygon', 'yfinance', 'tradier', 'finnhub')
GROUP BY s.ticker, ob.provider;
```

### Verify ML Forecasts Preserved
```sql
SELECT 
  s.ticker,
  COUNT(*) as forecast_count,
  MAX(ob.ts) as latest_forecast
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'ml_forecast'
GROUP BY s.ticker;
```

---

## ⚠️ Troubleshooting

### Issue: Backfill script fails
**Check:**
- Alpaca API credentials in `.env`
- Network connectivity
- API rate limits

**Fix:**
```bash
# Verify credentials
cat ml/.env | grep ALPACA

# Test single symbol first
python ml/src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL --timeframe h1
```

### Issue: Charts still show old data
**Check:**
- Clear macOS app cache
- Restart app
- Verify database has new data

**Fix:**
```bash
# Force refresh in app
# Or clear local cache and reload
```

### Issue: Missing bars for some symbols
**Check:**
- Symbol is tradable on Alpaca
- Market hours (no data outside 9:30-16:00 ET)
- Weekends/holidays excluded

**Fix:**
```bash
# Re-run backfill for specific symbol
python ml/src/scripts/alpaca_backfill_ohlc_v2.py --symbols SYMBOL --timeframe h1
```

---

## 📊 Benefits of This Reload

1. **Clean Alpaca Migration** - Single source of truth
2. **Chart Standardization** - 100 bars default across all timeframes
3. **Performance** - No mixed provider queries
4. **Consistency** - All data from same source
5. **Testing** - Verify new chart standards work correctly

---

## 🔗 Related Files

- **Cleanup SQL:** `backend/scripts/clear_watchlist_chart_data.sql`
- **Reload Script:** `backend/scripts/reload_watchlist_alpaca.sh`
- **Backfill Script:** `ml/src/scripts/alpaca_backfill_ohlc_v2.py`
- **Chart Standards:** `CHART_STANDARDS.md`
- **Migration:** `backend/supabase/migrations/20260110120000_alpaca_only_migration.sql`

---

## ✅ Summary

**Ready to execute:** All scripts created and tested  
**Safe:** Preserves ML forecasts and rankings  
**Fast:** ~5-10 minutes for 7 symbols  
**Clean:** Fresh Alpaca-only data  
**Verified:** Includes validation queries

**Next Action:** Run `./backend/scripts/reload_watchlist_alpaca.sh`
