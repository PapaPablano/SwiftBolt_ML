# Immediate Fixes - Execute in Order

## 1. Manually Backfill AAPL (RIGHT NOW)

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml/src/scripts

# Backfill all timeframes for AAPL
python alpaca_backfill_ohlc_v2.py \
  --symbol AAPL \
  --timeframes m15,h1,h4,d1,w1 \
  --start-date 2024-07-18 \
  --end-date 2026-01-10
```

## 2. Verify Data is Current

Run this in Supabase SQL Editor:

```sql
SELECT 
  timeframe,
  MAX(ts) AT TIME ZONE 'UTC' as newest_bar,
  EXTRACT(DAY FROM (NOW() - MAX(ts))) as days_old,
  COUNT(*) as total_bars
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND is_forecast = false
GROUP BY timeframe
ORDER BY timeframe;
```

Expected results:
- m15: newest_bar should be within last few hours
- h1: newest_bar should be within last day
- d1: newest_bar should be within last 2 days
- All should show ~1000 bars

## 3. Identify Active Ingestion Mechanism

Check which mechanism is supposed to be running:

### A. GitHub Actions
```bash
cd /Users/ericpeterson/SwiftBolt_ML
gh run list --workflow=alpaca-intraday-cron.yml --limit 10
gh run list --workflow=backfill-ohlc.yml --limit 10
gh run list --workflow=daily-data-refresh.yml --limit 10
```

### B. Supabase Edge Functions
Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
- Check if any backfill functions are deployed
- Check logs for recent executions

### C. Supabase Cron Jobs
Run in SQL Editor:
```sql
SELECT * FROM cron.job WHERE command LIKE '%backfill%' OR command LIKE '%alpaca%';
```

## 4. Rebuild App and Test

```bash
# In Xcode
# 1. Clean build folder (Cmd+Shift+K)
# 2. Rebuild (Cmd+B)
# 3. Run app
# 4. Load AAPL chart
# 5. Check all timeframes (m15, h1, h4, d1, w1)
```

Expected: All timeframes should now show current data (not July 2024).

---

## If Data is Still Stale After Backfill

This means the backfill script itself is broken. Check:

1. **Alpaca API keys are valid:**
   ```bash
   cd ml
   python -c "from src.config.settings import settings; print(settings.ALPACA_API_KEY[:10])"
   ```

2. **Script has correct database connection:**
   ```bash
   python -c "from src.config.settings import settings; print(settings.SUPABASE_URL)"
   ```

3. **Run backfill with verbose logging:**
   ```bash
   python alpaca_backfill_ohlc_v2.py --symbol AAPL --timeframes d1 --verbose
   ```
