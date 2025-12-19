# OHLC Backfill Validation & Monitoring

This document provides SQL queries and procedures to validate and monitor your automated OHLC backfill system.

## Quick Health Check

Run this query to get an overview of your backfill status:

```sql
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) AS bar_count,
  MIN(o.ts) AS oldest_bar,
  MAX(o.ts) AS newest_bar,
  MAX(o.ts)::date AS newest_bar_date,
  NOW()::date - MAX(o.ts)::date AS days_behind
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
```

**What to look for:**
- `bar_count` > 0 for all watchlist symbols
- `newest_bar_date` should be recent (within 1-2 days for daily data)
- `days_behind` should be 0-1 for active symbols

---

## Validation Queries

### 1. Check specific symbol coverage

```sql
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) AS bar_count,
  MIN(o.ts) AS oldest_bar,
  MAX(o.ts) AS newest_bar
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker = 'AAPL'
GROUP BY s.ticker, o.timeframe
ORDER BY o.timeframe;
```

### 2. Identify symbols with stale data

```sql
SELECT
  s.ticker,
  o.timeframe,
  MAX(o.ts) AS newest_bar,
  NOW() - MAX(o.ts) AS time_since_last_bar
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
GROUP BY s.ticker, o.timeframe
HAVING NOW() - MAX(o.ts) > INTERVAL '2 days'
ORDER BY time_since_last_bar DESC;
```

**Action:** If symbols appear here, they may need manual backfill.

### 3. Check for gaps in data

```sql
WITH bar_gaps AS (
  SELECT
    s.ticker,
    o.timeframe,
    o.ts,
    LEAD(o.ts) OVER (PARTITION BY o.symbol_id, o.timeframe ORDER BY o.ts) AS next_ts,
    LEAD(o.ts) OVER (PARTITION BY o.symbol_id, o.timeframe ORDER BY o.ts) - o.ts AS gap
  FROM ohlc_bars o
  JOIN symbols s ON s.id = o.symbol_id
  WHERE o.timeframe = 'd1'
)
SELECT
  ticker,
  timeframe,
  ts,
  next_ts,
  gap
FROM bar_gaps
WHERE gap > INTERVAL '7 days'  -- Gaps > 1 week (accounting for weekends)
ORDER BY ticker, ts;
```

### 4. Count bars per symbol/timeframe

```sql
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) AS bar_count
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
```

### 5. Check recent backfill activity

```sql
SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) AS bars_last_24h
FROM ohlc_bars o
JOIN symbols s ON s.id = o.symbol_id
WHERE o.created_at > NOW() - INTERVAL '24 hours'
GROUP BY s.ticker, o.timeframe
ORDER BY bars_last_24h DESC;
```

**Note:** This requires a `created_at` timestamp column. If not present, check workflow logs.

---

## Monitoring Dashboard Queries

### Coverage Summary

```sql
SELECT
  o.timeframe,
  COUNT(DISTINCT o.symbol_id) AS symbols_covered,
  SUM(bars.cnt) AS total_bars,
  AVG(bars.cnt) AS avg_bars_per_symbol,
  MIN(bars.oldest) AS oldest_bar_overall,
  MAX(bars.newest) AS newest_bar_overall
FROM (
  SELECT
    symbol_id,
    timeframe,
    COUNT(*) AS cnt,
    MIN(ts) AS oldest,
    MAX(ts) AS newest
  FROM ohlc_bars
  GROUP BY symbol_id, timeframe
) AS bars
JOIN ohlc_bars o ON o.symbol_id = bars.symbol_id AND o.timeframe = bars.timeframe
GROUP BY o.timeframe
ORDER BY o.timeframe;
```

### Data Freshness Report

```sql
SELECT
  CASE
    WHEN NOW() - MAX(ts) < INTERVAL '1 day' THEN 'Current'
    WHEN NOW() - MAX(ts) < INTERVAL '3 days' THEN 'Slightly Stale'
    WHEN NOW() - MAX(ts) < INTERVAL '7 days' THEN 'Stale'
    ELSE 'Very Stale'
  END AS freshness,
  COUNT(DISTINCT symbol_id) AS symbol_count
FROM ohlc_bars
WHERE timeframe = 'd1'
GROUP BY freshness
ORDER BY
  CASE freshness
    WHEN 'Current' THEN 1
    WHEN 'Slightly Stale' THEN 2
    WHEN 'Stale' THEN 3
    ELSE 4
  END;
```

---

## Troubleshooting

### Symptom: No new bars after scheduled run

**Check:**
1. GitHub Actions workflow status (Actions tab)
2. Workflow logs for errors
3. Supabase secrets are correctly set
4. API keys are valid (Finnhub, Massive/Polygon)

**SQL Check:**
```sql
-- Should show recent data
SELECT MAX(ts) FROM ohlc_bars WHERE timeframe = 'd1';
```

### Symptom: Duplicate bars

**Check:**
```sql
SELECT
  symbol_id,
  timeframe,
  ts,
  COUNT(*) AS duplicate_count
FROM ohlc_bars
GROUP BY symbol_id, timeframe, ts
HAVING COUNT(*) > 1;
```

**Note:** Should return 0 rows. If duplicates exist, check unique constraint.

### Symptom: High API rate limiting (429 errors)

**Actions:**
1. Check workflow logs for 429 status codes
2. Increase `RATE_LIMIT_DELAY` in `backfill_ohlc.py`
3. Reduce symbols per run (split watchlist)
4. Run less frequently (every 12 hours instead of 6)

---

## Success Criteria

After a successful automated backfill setup, you should see:

- ✅ All watchlist symbols have bars in `ohlc_bars`
- ✅ Data is current (within 1-2 days)
- ✅ No large gaps in historical data
- ✅ Scheduled runs complete without errors
- ✅ Re-running workflow doesn't create duplicates

---

## Next Steps

- Set up monitoring alerts (e.g., if data becomes stale)
- Add `backfill_status` table to track job runs (optional)
- Integrate with options ranking workflow
- Consider adding gap-detection automated repair
