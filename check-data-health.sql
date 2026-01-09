-- Data Health Check for SwiftBolt Multi-Provider Pipeline
-- Run this in your Supabase SQL Editor to verify everything is working

-- ============================================================================
-- 1. Check Backfill Job Status
-- ============================================================================

SELECT
  symbol,
  timeframe,
  status,
  progress || '%' as progress,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done_chunks,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'pending') as pending_chunks,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'running') as running_chunks,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'error') as error_chunks,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total_chunks,
  to_char(created_at, 'YYYY-MM-DD HH24:MI') as created,
  to_char(updated_at, 'YYYY-MM-DD HH24:MI') as updated
FROM backfill_jobs j
ORDER BY symbol, timeframe;

-- ============================================================================
-- 2. Check Actual Bar Data Coverage (Polygon Provider)
-- ============================================================================

SELECT
  s.ticker,
  b.timeframe,
  b.provider,
  COUNT(*) as total_bars,
  MIN(b.ts)::date as earliest_date,
  MAX(b.ts)::date as latest_date,
  ROUND(EXTRACT(EPOCH FROM (MAX(b.ts) - MIN(b.ts))) / 86400) as days_coverage,
  CASE
    WHEN COUNT(*) > 0 THEN '✅ Has Data'
    ELSE '❌ No Data'
  END as status
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.provider = 'polygon' AND b.is_forecast = false
GROUP BY s.ticker, b.timeframe, b.provider
ORDER BY s.ticker, b.timeframe;

-- ============================================================================
-- 3. Check All Data Sources (Polygon, Yahoo, Tradier)
-- ============================================================================

SELECT
  s.ticker,
  b.provider,
  b.timeframe,
  COUNT(*) as bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest,
  COUNT(DISTINCT b.ts::date) as unique_days
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.is_forecast = false
GROUP BY s.ticker, b.provider, b.timeframe
ORDER BY s.ticker, b.provider, b.timeframe;

-- ============================================================================
-- 4. Check for Data Gaps in Recent Week (Per Symbol)
-- ============================================================================

WITH recent_dates AS (
  SELECT
    s.ticker,
    generate_series(
      CURRENT_DATE - INTERVAL '7 days',
      CURRENT_DATE,
      INTERVAL '1 day'
    )::date as expected_date
  FROM symbols s
  WHERE s.ticker IN ('AAPL', 'NVDA', 'CRWD', 'AMD', 'PLTR', 'AMZN', 'MU')
    AND EXTRACT(DOW FROM generate_series(
      CURRENT_DATE - INTERVAL '7 days',
      CURRENT_DATE,
      INTERVAL '1 day'
    )) BETWEEN 1 AND 5 -- Only weekdays
),
actual_data AS (
  SELECT
    s.ticker,
    b.ts::date as actual_date,
    COUNT(*) as bars_count
  FROM ohlc_bars_v2 b
  JOIN symbols s ON s.id = b.symbol_id
  WHERE b.provider = 'polygon'
    AND b.timeframe = 'h1'
    AND b.ts::date >= CURRENT_DATE - INTERVAL '7 days'
  GROUP BY s.ticker, b.ts::date
)
SELECT
  rd.ticker,
  rd.expected_date,
  COALESCE(ad.bars_count, 0) as bars_on_date,
  CASE
    WHEN ad.bars_count IS NULL THEN '❌ Missing'
    WHEN ad.bars_count < 4 THEN '⚠️  Incomplete'
    ELSE '✅ Complete'
  END as status
FROM recent_dates rd
LEFT JOIN actual_data ad ON rd.ticker = ad.ticker AND rd.expected_date = ad.actual_date
ORDER BY rd.ticker, rd.expected_date DESC;

-- ============================================================================
-- 5. Check Recent Chunk Processing Activity
-- ============================================================================

SELECT
  symbol,
  timeframe,
  day::text as processing_date,
  status,
  try_count,
  LEFT(last_error, 100) as error_preview,
  to_char(created_at, 'MM-DD HH24:MI') as created,
  to_char(updated_at, 'MM-DD HH24:MI') as updated
FROM backfill_chunks
WHERE status IN ('done', 'running', 'error')
  AND updated_at >= NOW() - INTERVAL '1 hour'
ORDER BY updated_at DESC
LIMIT 50;

-- ============================================================================
-- 6. Verify Provider Distribution (Should Use Polygon for Intraday)
-- ============================================================================

SELECT
  b.provider,
  b.timeframe,
  COUNT(DISTINCT b.symbol_id) as unique_symbols,
  COUNT(*) as total_bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest,
  CASE
    WHEN b.timeframe IN ('m15', 'h1', 'h4') AND b.provider = 'polygon' THEN '✅ Correct'
    WHEN b.timeframe IN ('d1', 'w1') AND b.provider IN ('yfinance', 'yahoo') THEN '✅ Correct'
    ELSE '⚠️  Check Routing'
  END as routing_status
FROM ohlc_bars_v2 b
WHERE b.is_forecast = false
GROUP BY b.provider, b.timeframe
ORDER BY b.timeframe, b.provider;

-- ============================================================================
-- 7. Check Symbol-Specific Data Quality (Your Watchlist)
-- ============================================================================

WITH watchlist_symbols AS (
  SELECT UNNEST(ARRAY['AAPL', 'NVDA', 'CRWD', 'AMD', 'PLTR', 'AMZN', 'MU']) as ticker
)
SELECT
  ws.ticker,
  (SELECT COUNT(*) FROM ohlc_bars_v2 b
   JOIN symbols s ON s.id = b.symbol_id
   WHERE s.ticker = ws.ticker AND b.provider = 'polygon' AND b.timeframe = 'h1') as h1_bars,
  (SELECT MIN(b.ts)::date FROM ohlc_bars_v2 b
   JOIN symbols s ON s.id = b.symbol_id
   WHERE s.ticker = ws.ticker AND b.provider = 'polygon' AND b.timeframe = 'h1') as earliest_h1,
  (SELECT MAX(b.ts)::date FROM ohlc_bars_v2 b
   JOIN symbols s ON s.id = b.symbol_id
   WHERE s.ticker = ws.ticker AND b.provider = 'polygon' AND b.timeframe = 'h1') as latest_h1,
  (SELECT progress FROM backfill_jobs WHERE symbol = ws.ticker AND timeframe = 'h1') as backfill_progress,
  CASE
    WHEN (SELECT COUNT(*) FROM ohlc_bars_v2 b
          JOIN symbols s ON s.id = b.symbol_id
          WHERE s.ticker = ws.ticker AND b.provider = 'polygon' AND b.timeframe = 'h1') > 100
    THEN '✅ Good'
    WHEN (SELECT COUNT(*) FROM ohlc_bars_v2 b
          JOIN symbols s ON s.id = b.symbol_id
          WHERE s.ticker = ws.ticker AND b.provider = 'polygon' AND b.timeframe = 'h1') > 0
    THEN '⚠️  Limited'
    ELSE '❌ No Data'
  END as data_health
FROM watchlist_symbols ws
ORDER BY ws.ticker;

-- ============================================================================
-- 8. Check for Duplicate Bars (Should Be None)
-- ============================================================================

SELECT
  s.ticker,
  b.timeframe,
  b.provider,
  b.ts,
  COUNT(*) as duplicate_count
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.is_forecast = false
GROUP BY s.ticker, b.timeframe, b.provider, b.ts
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, s.ticker
LIMIT 20;

-- ============================================================================
-- 9. Overall Health Summary
-- ============================================================================

SELECT
  'Total Symbols with Data' as metric,
  COUNT(DISTINCT b.symbol_id)::text as value
FROM ohlc_bars_v2 b
WHERE b.provider = 'polygon' AND b.is_forecast = false

UNION ALL

SELECT
  'Total Polygon Bars' as metric,
  COUNT(*)::text as value
FROM ohlc_bars_v2 b
WHERE b.provider = 'polygon' AND b.is_forecast = false

UNION ALL

SELECT
  'Backfill Jobs Total' as metric,
  COUNT(*)::text as value
FROM backfill_jobs

UNION ALL

SELECT
  'Backfill Jobs Complete' as metric,
  COUNT(*)::text as value
FROM backfill_jobs
WHERE status = 'done'

UNION ALL

SELECT
  'Backfill Jobs In Progress' as metric,
  COUNT(*)::text as value
FROM backfill_jobs
WHERE status IN ('running', 'pending')

UNION ALL

SELECT
  'Total Chunks Pending' as metric,
  COUNT(*)::text as value
FROM backfill_chunks
WHERE status = 'pending'

UNION ALL

SELECT
  'Total Chunks Completed' as metric,
  COUNT(*)::text as value
FROM backfill_chunks
WHERE status = 'done'

UNION ALL

SELECT
  'Total Chunks with Errors' as metric,
  COUNT(*)::text as value
FROM backfill_chunks
WHERE status = 'error';

-- ============================================================================
-- 10. Chart Data Query Test (What Your App Requests)
-- ============================================================================

-- This simulates what chart-data-v2 requests for AAPL 1H chart
SELECT
  s.ticker,
  b.timeframe,
  b.provider,
  b.ts,
  b.open,
  b.high,
  b.low,
  b.close,
  b.volume,
  b.is_intraday,
  b.is_forecast,
  b.data_status
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker = 'AAPL'
  AND b.timeframe = 'h1'
  AND b.provider = 'polygon'
  AND b.is_forecast = false
  AND b.ts >= NOW() - INTERVAL '60 days'
ORDER BY b.ts DESC
LIMIT 10;
