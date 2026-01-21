-- Phase 2 Batch Backfill Validation Queries
-- Run these in Supabase SQL Editor to verify Phase 2 deployment

-- ============================================
-- 1. Verify symbols_array column exists
-- ============================================
SELECT 
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'job_definitions'
  AND column_name IN ('symbols_array', 'batch_number', 'total_batches');

-- Expected: 3 rows showing symbols_array (jsonb), batch_number (integer), total_batches (integer)


-- ============================================
-- 2. Check recent batch jobs created
-- ============================================
SELECT 
  created_at,
  timeframe,
  slice_type,
  jsonb_array_length(symbols_array) AS batch_size,
  batch_number,
  total_batches,
  status,
  provider
FROM job_definitions
WHERE symbols_array IS NOT NULL
  AND created_at > now() - interval '1 hour'
ORDER BY created_at DESC
LIMIT 20;

-- Expected: Batch jobs with batch_size ≈ 50, batch_number/total_batches populated


-- ============================================
-- 3. Batch job statistics
-- ============================================
SELECT 
  timeframe,
  COUNT(*) AS batch_jobs,
  AVG(jsonb_array_length(symbols_array)) AS avg_batch_size,
  MIN(jsonb_array_length(symbols_array)) AS min_batch_size,
  MAX(jsonb_array_length(symbols_array)) AS max_batch_size,
  SUM(jsonb_array_length(symbols_array)) AS total_symbols
FROM job_definitions
WHERE symbols_array IS NOT NULL
  AND created_at > now() - interval '24 hours'
GROUP BY timeframe
ORDER BY timeframe;

-- Expected: avg_batch_size ≈ 50, max_batch_size ≤ 50


-- ============================================
-- 4. Check batch job execution status
-- ============================================
SELECT 
  status,
  COUNT(*) AS jobs,
  AVG(rows_written) AS avg_rows,
  SUM(rows_written) AS total_rows,
  AVG(actual_cost) AS avg_api_calls
FROM job_runs
WHERE created_at > now() - interval '1 hour'
  AND provider = 'alpaca'
GROUP BY status
ORDER BY status;

-- Expected: 
-- - status = 'success' with avg_rows in thousands (2000-5000)
-- - avg_api_calls ≈ 0.02 (1/50 for batch jobs)


-- ============================================
-- 5. Compare Phase 1 vs Phase 2 efficiency
-- ============================================
WITH phase1_jobs AS (
  SELECT 
    COUNT(*) AS job_count,
    SUM(rows_written) AS total_rows,
    'Phase 1 (single-symbol)' AS phase
  FROM job_runs
  WHERE created_at > now() - interval '7 days'
    AND created_at < now() - interval '1 day'
    AND provider = 'alpaca'
    AND status = 'success'
),
phase2_jobs AS (
  SELECT 
    COUNT(*) AS job_count,
    SUM(rows_written) AS total_rows,
    'Phase 2 (batch)' AS phase
  FROM job_runs
  WHERE created_at > now() - interval '1 day'
    AND provider = 'alpaca'
    AND status = 'success'
)
SELECT * FROM phase1_jobs
UNION ALL
SELECT * FROM phase2_jobs;

-- Expected: Phase 2 job_count should be ~50x lower than Phase 1


-- ============================================
-- 6. Monitor batch job progress
-- ============================================
SELECT 
  jr.created_at,
  jr.status,
  jr.symbol,
  jr.timeframe,
  jr.rows_written,
  jr.progress_percent,
  jr.provider,
  jr.actual_cost,
  jr.error_message
FROM job_runs jr
WHERE jr.created_at > now() - interval '30 minutes'
  AND jr.provider = 'alpaca'
ORDER BY jr.created_at DESC
LIMIT 50;

-- Monitor for:
-- - status = 'success' (most jobs)
-- - rows_written > 0
-- - actual_cost ≈ 0.02 (1/50 for batch)
-- - error_message IS NULL


-- ============================================
-- 7. Check API call efficiency
-- ============================================
SELECT 
  DATE_TRUNC('hour', created_at) AS hour,
  COUNT(*) AS jobs_completed,
  SUM(actual_cost) AS total_api_calls,
  SUM(rows_written) AS total_rows,
  ROUND(SUM(actual_cost)::numeric / COUNT(*)::numeric, 3) AS avg_api_calls_per_job
FROM job_runs
WHERE created_at > now() - interval '24 hours'
  AND provider = 'alpaca'
  AND status = 'success'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;

-- Expected: 
-- - avg_api_calls_per_job ≈ 0.02 for batch jobs (vs 1.0 for single-symbol)
-- - total_api_calls well under 200/hour (free tier limit)


-- ============================================
-- 8. Identify any failed batch jobs
-- ============================================
SELECT 
  jr.created_at,
  jr.symbol,
  jr.timeframe,
  jr.error_code,
  jr.error_message,
  jr.attempt
FROM job_runs jr
WHERE jr.created_at > now() - interval '1 hour'
  AND jr.status = 'failed'
  AND jr.provider = 'alpaca'
ORDER BY jr.created_at DESC;

-- Expected: Very few or zero failed jobs


-- ============================================
-- 9. Verify data quality (no duplicates)
-- ============================================
SELECT 
  symbol_id,
  timeframe,
  ts,
  COUNT(*) AS duplicate_count
FROM ohlc_bars_v2
WHERE provider = 'alpaca'
  AND created_at > now() - interval '1 hour'
GROUP BY symbol_id, timeframe, ts
HAVING COUNT(*) > 1
LIMIT 10;

-- Expected: Zero rows (no duplicates)


-- ============================================
-- 10. Overall Phase 2 health check
-- ============================================
SELECT 
  'Batch Jobs Created' AS metric,
  COUNT(*)::text AS value
FROM job_definitions
WHERE symbols_array IS NOT NULL
  AND created_at > now() - interval '24 hours'

UNION ALL

SELECT 
  'Avg Batch Size' AS metric,
  ROUND(AVG(jsonb_array_length(symbols_array)))::text AS value
FROM job_definitions
WHERE symbols_array IS NOT NULL
  AND created_at > now() - interval '24 hours'

UNION ALL

SELECT 
  'Successful Batch Runs' AS metric,
  COUNT(*)::text AS value
FROM job_runs
WHERE created_at > now() - interval '24 hours'
  AND provider = 'alpaca'
  AND status = 'success'

UNION ALL

SELECT 
  'Total Rows Written' AS metric,
  SUM(rows_written)::text AS value
FROM job_runs
WHERE created_at > now() - interval '24 hours'
  AND provider = 'alpaca'
  AND status = 'success'

UNION ALL

SELECT 
  'Total API Calls' AS metric,
  ROUND(SUM(actual_cost))::text AS value
FROM job_runs
WHERE created_at > now() - interval '24 hours'
  AND provider = 'alpaca'
  AND status = 'success'

UNION ALL

SELECT 
  'Efficiency Gain' AS metric,
  ROUND((COUNT(*) / NULLIF(SUM(actual_cost), 0))::numeric, 1)::text || 'x' AS value
FROM job_runs
WHERE created_at > now() - interval '24 hours'
  AND provider = 'alpaca'
  AND status = 'success';

-- Expected:
-- - Batch Jobs Created: ~100-150
-- - Avg Batch Size: ~50
-- - Successful Batch Runs: ~100-150
-- - Total Rows Written: 100,000+
-- - Total API Calls: ~100-150
-- - Efficiency Gain: ~50x
