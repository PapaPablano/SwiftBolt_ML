-- SPEC-8 Operations Queries
-- Copy/paste these into Supabase SQL Editor for monitoring

-- ============================================================================
-- TOP FAILURES (Last 60 minutes)
-- ============================================================================
-- Shows most common errors to help identify systemic issues
select 
  error_code, 
  left(error_message, 120) as msg, 
  count(*) as failure_count
from job_runs 
where status = 'failed' 
  and created_at > now() - interval '60 min'
group by error_code, left(error_message, 120)
order by failure_count desc 
limit 10;

-- ============================================================================
-- PER-SYMBOL COVERAGE STATUS
-- ============================================================================
-- Shows data coverage for each symbol/timeframe combination
select 
  symbol, 
  timeframe, 
  from_ts, 
  to_ts, 
  last_success_at,
  last_provider,
  last_rows_written
from coverage_status
order by last_success_at desc nulls last
limit 20;

-- ============================================================================
-- JOB QUEUE HEALTH
-- ============================================================================
-- Overview of job statuses in the last hour
select 
  status,
  count(*) as job_count,
  round(avg(extract(epoch from (finished_at - started_at))), 2) as avg_duration_sec,
  max(created_at) as most_recent
from job_runs
where created_at > now() - interval '60 min'
group by status
order by 
  case status
    when 'running' then 1
    when 'queued' then 2
    when 'failed' then 3
    when 'success' then 4
    else 5
  end;

-- ============================================================================
-- ACTIVE JOBS (Currently Running)
-- ============================================================================
-- Shows jobs that are currently in progress
select 
  id,
  symbol,
  timeframe,
  job_type,
  slice_from,
  slice_to,
  progress_percent,
  rows_written,
  provider,
  started_at,
  extract(epoch from (now() - started_at)) as running_for_sec
from job_runs
where status = 'running'
order by started_at desc;

-- ============================================================================
-- QUEUED JOBS (Waiting to Execute)
-- ============================================================================
-- Shows jobs waiting to be picked up by orchestrator
select 
  id,
  symbol,
  timeframe,
  job_type,
  slice_from,
  slice_to,
  attempt,
  created_at,
  extract(epoch from (now() - created_at)) as queued_for_sec
from job_runs
where status = 'queued'
order by created_at asc
limit 20;

-- ============================================================================
-- RECENT SUCCESSFUL JOBS
-- ============================================================================
-- Shows recently completed jobs with performance metrics
select 
  symbol,
  timeframe,
  slice_from,
  slice_to,
  rows_written,
  provider,
  extract(epoch from (finished_at - started_at)) as duration_sec,
  finished_at
from job_runs
where status = 'success'
  and finished_at > now() - interval '60 min'
order by finished_at desc
limit 20;

-- ============================================================================
-- PROVIDER PERFORMANCE
-- ============================================================================
-- Compare success rates and performance across providers
select 
  provider,
  count(*) filter (where status = 'success') as success_count,
  count(*) filter (where status = 'failed') as failed_count,
  round(100.0 * count(*) filter (where status = 'success') / count(*), 2) as success_rate_pct,
  round(avg(rows_written) filter (where status = 'success'), 0) as avg_rows,
  round(avg(extract(epoch from (finished_at - started_at))) filter (where status = 'success'), 2) as avg_duration_sec
from job_runs
where created_at > now() - interval '24 hours'
  and provider is not null
group by provider
order by success_count desc;

-- ============================================================================
-- SYMBOL ACTIVITY (Last 24 Hours)
-- ============================================================================
-- Shows which symbols are being actively hydrated
select 
  symbol,
  timeframe,
  count(*) as total_jobs,
  count(*) filter (where status = 'success') as success,
  count(*) filter (where status = 'failed') as failed,
  count(*) filter (where status = 'running') as running,
  count(*) filter (where status = 'queued') as queued,
  max(created_at) as last_job_at
from job_runs
where created_at > now() - interval '24 hours'
group by symbol, timeframe
order by last_job_at desc
limit 20;

-- ============================================================================
-- CRON JOB STATUS
-- ============================================================================
-- Verify pg_cron job is active and check recent runs
select 
  jobid, 
  jobname,
  schedule, 
  active,
  nodename
from cron.job 
where jobname = 'orchestrator-tick';

-- Check recent cron executions
select 
  jobid,
  runid,
  status,
  return_message,
  start_time,
  end_time,
  extract(epoch from (end_time - start_time)) as duration_sec
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'orchestrator-tick')
order by start_time desc
limit 10;

-- ============================================================================
-- DATA FRESHNESS CHECK
-- ============================================================================
-- Verify data is landing in ohlc_bars_v2
select 
  symbol,
  timeframe,
  count(*) as bar_count,
  min(ts) as oldest_bar,
  max(ts) as newest_bar,
  extract(epoch from (now() - max(ts))) / 3600 as hours_since_last_bar
from ohlc_bars_v2
where ts > now() - interval '7 days'
group by symbol, timeframe
order by newest_bar desc
limit 20;

-- ============================================================================
-- STUCK JOBS (Running > 10 minutes)
-- ============================================================================
-- Identify jobs that may be hung
select 
  id,
  symbol,
  timeframe,
  job_type,
  started_at,
  extract(epoch from (now() - started_at)) / 60 as running_for_min,
  progress_percent,
  provider
from job_runs
where status = 'running'
  and started_at < now() - interval '10 minutes'
order by started_at asc;

-- ============================================================================
-- RETRY ANALYSIS
-- ============================================================================
-- Shows jobs that required multiple attempts
select 
  symbol,
  timeframe,
  attempt,
  count(*) as job_count,
  count(*) filter (where status = 'success') as eventually_succeeded,
  count(*) filter (where status = 'failed') as still_failed
from job_runs
where attempt > 1
  and created_at > now() - interval '24 hours'
group by symbol, timeframe, attempt
order by attempt desc, job_count desc;

-- ============================================================================
-- HOURLY THROUGHPUT
-- ============================================================================
-- Jobs completed per hour (last 24 hours)
select 
  date_trunc('hour', finished_at) as hour,
  count(*) as jobs_completed,
  sum(rows_written) as total_rows_written,
  round(avg(extract(epoch from (finished_at - started_at))), 2) as avg_duration_sec
from job_runs
where status = 'success'
  and finished_at > now() - interval '24 hours'
group by date_trunc('hour', finished_at)
order by hour desc;

-- ============================================================================
-- QUICK HEALTH CHECK (All-in-One)
-- ============================================================================
-- Single query for overall system health
select 
  'Total Jobs (24h)' as metric,
  count(*)::text as value
from job_runs
where created_at > now() - interval '24 hours'

union all

select 
  'Success Rate (24h)',
  round(100.0 * count(*) filter (where status = 'success') / count(*), 2)::text || '%'
from job_runs
where created_at > now() - interval '24 hours'

union all

select 
  'Active Jobs',
  count(*)::text
from job_runs
where status in ('running', 'queued')

union all

select 
  'Failed Jobs (1h)',
  count(*)::text
from job_runs
where status = 'failed'
  and created_at > now() - interval '60 min'

union all

select 
  'Symbols Covered',
  count(distinct symbol)::text
from coverage_status

union all

select 
  'Cron Job Active',
  case when active then 'YES' else 'NO' end
from cron.job
where jobname = 'orchestrator-tick'

union all

select 
  'Last Cron Run',
  to_char(max(start_time), 'YYYY-MM-DD HH24:MI:SS')
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'orchestrator-tick');
