-- Setup script for Backfill Worker Cron
-- Run this in your Supabase SQL Editor: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql

-- ============================================================================
-- STEP 1: Store Service Role Key in Vault
-- ============================================================================

-- Replace 'YOUR_SERVICE_ROLE_KEY_HERE' with your actual service role key
-- Get it from: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api

INSERT INTO vault.secrets (name, secret)
VALUES ('service_role_key', 'YOUR_SERVICE_ROLE_KEY_HERE')
ON CONFLICT (name) DO UPDATE SET secret = EXCLUDED.secret;

-- Verify the secret was stored (should return 1 row)
SELECT name, created_at, updated_at
FROM vault.secrets
WHERE name = 'service_role_key';

-- ============================================================================
-- STEP 2: Test Vault Access
-- ============================================================================

-- This should return your service role key (only visible to postgres role)
SELECT name, decrypted_secret
FROM vault.decrypted_secrets
WHERE name = 'service_role_key';

-- ============================================================================
-- STEP 3: Check if Cron Job is Active (after running migration)
-- ============================================================================

SELECT * FROM get_backfill_cron_status();

-- ============================================================================
-- STEP 4: Manually Test the Worker
-- ============================================================================

SELECT trigger_backfill_worker();

-- ============================================================================
-- STEP 5: Monitor Backfill Progress
-- ============================================================================

-- Check job status
SELECT
  symbol,
  timeframe,
  status,
  progress,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'pending') as pending,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'running') as running,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'error') as errors,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total
FROM backfill_jobs j
ORDER BY symbol;

-- Check recent chunk processing
SELECT
  symbol,
  timeframe,
  day::text as date,
  status,
  try_count,
  last_error,
  updated_at
FROM backfill_chunks
WHERE status IN ('done', 'error', 'running')
ORDER BY updated_at DESC
LIMIT 20;

-- Check how many bars have been inserted
SELECT
  s.ticker,
  b.timeframe,
  b.provider,
  COUNT(*) as total_bars,
  MIN(b.ts) as earliest,
  MAX(b.ts) as latest,
  ROUND(EXTRACT(EPOCH FROM (MAX(b.ts) - MIN(b.ts))) / 86400) as days_coverage
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE b.provider = 'polygon' AND b.is_forecast = false
GROUP BY s.ticker, b.timeframe, b.provider
ORDER BY s.ticker, b.timeframe;

-- ============================================================================
-- STEP 6: Check Recent Cron Runs
-- ============================================================================

SELECT
  jobid,
  runid,
  job_pid,
  database,
  username,
  command,
  status,
  return_message,
  start_time,
  end_time
FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'backfill-worker-every-minute')
ORDER BY start_time DESC
LIMIT 10;
