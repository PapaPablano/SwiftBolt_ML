-- Quick check of current job status
-- Run this to see if jobs are being processed

-- 1. Job status distribution
select
  status,
  count(*) as count,
  max(created_at) as most_recent
from job_runs
group by status
order by count desc;

-- 2. Recent running/success jobs (last 5 minutes)
select
  id,
  symbol,
  timeframe,
  status,
  rows_written,
  provider,
  created_at,
  started_at,
  finished_at
from job_runs
where created_at > now() - interval '5 minutes'
  and status in ('running', 'success')
order by created_at desc
limit 10;

-- 3. Check if any jobs have ALPACA data yet
select
  provider,
  count(*) as bar_count,
  max(fetched_at) as most_recent
from ohlc_bars_v2
where fetched_at > now() - interval '10 minutes'
group by provider;
