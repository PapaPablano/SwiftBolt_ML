-- Specific Health Check for AAPL (Currently Viewing in Your App)
-- This checks what data your chart is actually using

-- ============================================================================
-- 1. Check what AAPL data exists in the database
-- ============================================================================

SELECT
  provider,
  timeframe,
  COUNT(*) as bars,
  MIN(ts)::date as earliest,
  MAX(ts)::date as latest,
  ROUND(EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 86400) as days_covered,
  is_intraday,
  is_forecast
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker = 'AAPL'
GROUP BY provider, timeframe, is_intraday, is_forecast
ORDER BY provider, timeframe;

-- ============================================================================
-- 2. Check AAPL backfill status
-- ============================================================================

SELECT
  job.symbol,
  job.timeframe,
  job.status,
  job.progress,
  job.from_ts::date as start_date,
  job.to_ts::date as end_date,
  (SELECT COUNT(*) FROM backfill_chunks c WHERE c.job_id = job.id) as total_chunks,
  (SELECT COUNT(*) FROM backfill_chunks c WHERE c.job_id = job.id AND c.status = 'done') as done_chunks,
  (SELECT COUNT(*) FROM backfill_chunks c WHERE c.job_id = job.id AND c.status = 'pending') as pending_chunks,
  (SELECT COUNT(*) FROM backfill_chunks c WHERE c.job_id = job.id AND c.status = 'running') as running_chunks,
  (SELECT COUNT(*) FROM backfill_chunks c WHERE c.job_id = job.id AND c.status = 'error') as error_chunks,
  job.created_at,
  job.updated_at
FROM backfill_jobs job
WHERE job.symbol = 'AAPL';

-- ============================================================================
-- 3. Check recent AAPL chunks that have been processed
-- ============================================================================

SELECT
  day::date as processing_date,
  status,
  try_count,
  last_error,
  created_at,
  updated_at
FROM backfill_chunks
WHERE symbol = 'AAPL' AND timeframe = 'h1'
  AND status IN ('done', 'running', 'error')
ORDER BY updated_at DESC
LIMIT 20;

-- ============================================================================
-- 4. Sample AAPL h1 bars (what your chart should show)
-- ============================================================================

SELECT
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider,
  is_intraday,
  data_status
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker = 'AAPL'
  AND timeframe = 'h1'
  AND provider = 'polygon'
  AND is_forecast = false
ORDER BY ts DESC
LIMIT 50;

-- ============================================================================
-- 5. Check if you're seeing OLD data vs NEW data
-- ============================================================================

SELECT
  CASE
    WHEN MAX(ts)::date >= CURRENT_DATE - INTERVAL '7 days' THEN '✅ Recent data available'
    WHEN MAX(ts)::date >= CURRENT_DATE - INTERVAL '30 days' THEN '⚠️  Data is 1-4 weeks old'
    WHEN MAX(ts)::date >= CURRENT_DATE - INTERVAL '365 days' THEN '⚠️  Data is months old'
    ELSE '❌ Data is very old'
  END as data_freshness,
  MAX(ts)::date as latest_date,
  MIN(ts)::date as earliest_date,
  COUNT(*) as total_bars
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker = 'AAPL'
  AND timeframe = 'h1'
  AND provider = 'polygon';

-- ============================================================================
-- 6. Check if chart-data-v2 query returns data
-- ============================================================================

-- This simulates what your chart is requesting
SELECT
  COUNT(*) as bars_returned,
  MIN(b.ts)::date as from_date,
  MAX(b.ts)::date as to_date,
  ARRAY_AGG(DISTINCT b.provider) as providers_used
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker = 'AAPL'
  AND b.timeframe = 'h1'
  AND b.is_forecast = false
  AND b.ts >= NOW() - INTERVAL '60 days';

-- ============================================================================
-- 7. Diagnosis: What's the issue?
-- ============================================================================

SELECT
  CASE
    -- No data at all
    WHEN NOT EXISTS (
      SELECT 1 FROM ohlc_bars_v2 b
      JOIN symbols s ON s.id = b.symbol_id
      WHERE s.ticker = 'AAPL' AND b.timeframe = 'h1' AND b.provider = 'polygon'
    ) THEN '❌ NO POLYGON DATA - Backfill hasnt started or failed'

    -- Has old data only
    WHEN (
      SELECT MAX(ts)::date FROM ohlc_bars_v2 b
      JOIN symbols s ON s.id = b.symbol_id
      WHERE s.ticker = 'AAPL' AND b.timeframe = 'h1' AND b.provider = 'polygon'
    ) < CURRENT_DATE - INTERVAL '30 days'
    THEN '⚠️  ONLY OLD DATA - Backfill in progress, showing historical only'

    -- Has recent data
    WHEN (
      SELECT MAX(ts)::date FROM ohlc_bars_v2 b
      JOIN symbols s ON s.id = b.symbol_id
      WHERE s.ticker = 'AAPL' AND b.timeframe = 'h1' AND b.provider = 'polygon'
    ) >= CURRENT_DATE - INTERVAL '7 days'
    THEN '✅ HEALTHY - Recent data available'

    ELSE '⚠️  CHECK MANUALLY'
  END as diagnosis,

  (SELECT COUNT(*) FROM ohlc_bars_v2 b
   JOIN symbols s ON s.id = b.symbol_id
   WHERE s.ticker = 'AAPL' AND b.timeframe = 'h1' AND b.provider = 'polygon') as total_bars,

  (SELECT progress FROM backfill_jobs WHERE symbol = 'AAPL' AND timeframe = 'h1') as backfill_progress,

  (SELECT status FROM backfill_jobs WHERE symbol = 'AAPL' AND timeframe = 'h1') as backfill_status;
