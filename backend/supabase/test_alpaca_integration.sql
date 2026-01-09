-- Comprehensive Alpaca Integration Test Suite
-- Run these queries in order to verify everything is working

-- ============================================================================
-- TEST 1: Check Current Job Status
-- ============================================================================
-- This shows what the orchestrator has been doing

select
  status,
  count(*) as count,
  max(created_at) as most_recent
from job_runs
group by status
order by count desc;

-- Expected: Should see mix of queued/running/success
-- If ALL are "queued", dispatch isn't working

-- ============================================================================
-- TEST 2: Check Recent Job Details
-- ============================================================================
-- Look for errors in recent jobs

select
  id,
  symbol,
  timeframe,
  status,
  rows_written,
  provider,
  error_message,
  error_code,
  created_at,
  started_at,
  finished_at
from job_runs
order by created_at desc
limit 10;

-- Look for:
-- - error_message: Should be NULL if working
-- - provider: Should show 'alpaca' (not 'unknown' or NULL)
-- - rows_written: Should be > 0 for successful jobs

-- ============================================================================
-- TEST 3: Check Provider Data Distribution
-- ============================================================================
-- See which providers are actually storing data

select
  provider,
  count(*) as bar_count,
  min(fetched_at) as first_fetch,
  max(fetched_at) as last_fetch
from ohlc_bars_v2
group by provider
order by bar_count desc;

-- Expected after Alpaca is working:
-- - 'alpaca' should appear in the list
-- - 'alpaca' last_fetch should be recent (within last few minutes)

-- ============================================================================
-- TEST 4: Check Specific Symbol Coverage (AAPL)
-- ============================================================================
-- Deep dive into AAPL h1 data (the problem we saw in console)

select
  provider,
  count(*) as bar_count,
  min(ts) as oldest_bar,
  max(ts) as newest_bar,
  count(distinct date(ts)) as days_covered
from ohlc_bars_v2
where symbol_id = (select id from symbols where ticker = 'AAPL')
  and timeframe = 'h1'
group by provider
order by bar_count desc;

-- Current state: Only ~9 bars from polygon/tradier
-- Target state: 2000+ bars from alpaca

-- ============================================================================
-- TEST 5: Check Job Definitions
-- ============================================================================
-- Verify what the orchestrator is trying to fetch

select
  id,
  symbol,
  timeframe,
  job_type,
  window_days,
  priority,
  enabled,
  created_at
from job_definitions
where enabled = true
order by priority desc, created_at desc;

-- Expected: Should see job definitions for your watchlist symbols
-- If NO ROWS: Need to create job definitions (orchestrator has nothing to do)

-- ============================================================================
-- TEST 6: Check Coverage Gaps
-- ============================================================================
-- See what data ranges are missing for AAPL h1

select *
from get_coverage_gaps(
  p_symbol := 'AAPL',
  p_timeframe := 'h1',
  p_window_days := 730
);

-- This shows the gaps the orchestrator is trying to fill
-- If empty: Coverage is complete (good!)
-- If rows: Shows date ranges that need backfilling

-- ============================================================================
-- TEST 7: Check Orchestrator Cron Execution
-- ============================================================================
-- Verify the cron job is actually running

select
  jobid,
  runid,
  status,
  return_message,
  start_time,
  end_time,
  end_time - start_time as duration
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'orchestrator-tick')
order by start_time desc
limit 10;

-- Expected:
-- - status: 'succeeded' (not 'failed')
-- - return_message: Should be NULL or contain success info
-- - Recent executions: Should have entries from last few minutes

-- ============================================================================
-- TEST 8: Check Edge Function Environment
-- ============================================================================
-- This tests if Edge Functions can see the Alpaca credentials
-- Note: You can't directly query env vars, but we can check the fetch-bars worker logs

select
  symbol,
  timeframe,
  provider,
  error_message,
  error_code
from job_runs
where status = 'failed'
  and created_at > now() - interval '10 minutes'
order by created_at desc
limit 5;

-- Look for errors like:
-- - "ALPACA_API_KEY not set" → Credentials not loaded
-- - "Authentication failed" → Wrong credentials
-- - "Invalid symbol" → Alpaca symbol validation issue

-- ============================================================================
-- DIAGNOSTIC: If No Jobs Are Running
-- ============================================================================
-- If all jobs stuck in "queued", manually trigger dispatch

-- Step 1: Trigger orchestrator again
-- select public.run_orchestrator_tick();

-- Step 2: Wait 10 seconds

-- Step 3: Check status again
-- select status, count(*) from job_runs group by status;

-- ============================================================================
-- DIAGNOSTIC: If Jobs Failing with Alpaca Errors
-- ============================================================================
-- Check most recent error messages

select
  error_code,
  error_message,
  count(*) as occurrences
from job_runs
where status = 'failed'
  and created_at > now() - interval '1 hour'
group by error_code, error_message
order by occurrences desc;

-- Common errors and fixes:
-- - "ALPACA_API_KEY not set" → Add to Supabase Edge Function secrets
-- - "401 Unauthorized" → Check API keys are correct
-- - "429 Rate limit" → Normal, will auto-retry
-- - "Invalid symbol" → Symbol not supported by Alpaca

-- ============================================================================
-- SUCCESS CRITERIA
-- ============================================================================
-- Integration is working when:
-- 1. TEST 1: Shows some "success" jobs (not all queued)
-- 2. TEST 2: provider = 'alpaca' in recent jobs
-- 3. TEST 3: 'alpaca' appears with recent last_fetch
-- 4. TEST 4: AAPL h1 shows 100+ bars from alpaca
-- 5. TEST 7: Cron executions show status='succeeded'

-- ============================================================================
-- MANUAL TEST: Trigger Single Job
-- ============================================================================
-- If you want to test Alpaca immediately without waiting for orchestrator

-- This manually calls the orchestrator tick function
-- select public.run_orchestrator_tick();

-- Then check job_runs table after 30 seconds
-- select * from job_runs order by created_at desc limit 5;
