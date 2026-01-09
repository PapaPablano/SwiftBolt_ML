-- Verification Queries for Alpaca Integration
-- Run these after completing all fix steps

-- 1. Check if Alpaca data exists in database
select provider, count(*) as bar_count
from ohlc_bars_v2
group by provider
order by bar_count desc;

-- Expected: Should see 'alpaca' in the list after backfill

-- 2. Check AAPL h1 coverage specifically
select provider, count(*) as bar_count, min(ts) as first_bar, max(ts) as last_bar
from ohlc_bars_v2
where symbol_id = (select id from symbols where ticker = 'AAPL')
  and timeframe = 'h1'
group by provider
order by bar_count desc;

-- Current state: polygon/tradier with only ~9 bars
-- Target state: alpaca with 2000+ bars

-- 3. Check recent job runs
select
  symbol,
  timeframe,
  status,
  rows_written,
  provider,
  created_at,
  finished_at,
  error_message
from job_runs
where symbol = 'AAPL' and timeframe = 'h1'
order by created_at desc
limit 10;

-- Expected: Should see rows with status='success' and provider='alpaca'

-- 4. Check orchestrator health
select
  status,
  count(*) as count,
  round(avg(rows_written), 0) as avg_bars
from job_runs
where created_at > now() - interval '1 hour'
group by status;

-- Expected: Mostly 'success' status

-- 5. Check coverage status
select symbol, timeframe, from_ts, to_ts, last_success_at
from coverage_status
where symbol = 'AAPL'
order by timeframe;

-- Expected: last_success_at should be recent

-- 6. Check cron job status
select jobid, schedule, command, active, jobname, last_run_time
from cron.job
where jobname = 'orchestrator-tick';

-- Expected: active=true, last_run_time should be recent

-- 7. Verify database settings
select
  current_setting('app.supabase_url', true) as url,
  case
    when length(current_setting('app.supabase_service_role_key', true)) > 100 then 'CONFIGURED'
    else 'MISSING'
  end as key_status;

-- Expected: url set correctly, key_status='CONFIGURED'
