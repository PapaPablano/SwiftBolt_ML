-- SPEC-8: Unified Market Data Orchestrator
-- Creates job_definitions, job_runs, and coverage_status tables

-- Job definitions: templates for periodic and on-demand work
create table if not exists job_definitions (
  id uuid primary key default gen_random_uuid(),
  job_type text check (job_type in ('fetch_intraday','fetch_historical','run_forecast')) not null,
  symbol text not null,
  timeframe text not null, -- '15m'|'1h'|'4h'|'d1'|'w1'
  window_days int not null default 7,
  priority int not null default 100,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(symbol, timeframe, job_type)
);

create index idx_job_definitions_enabled on job_definitions(enabled, priority desc) where enabled = true;
create index idx_job_definitions_symbol_tf on job_definitions(symbol, timeframe);

-- Job runs: each execution slice with realtime progress
create table if not exists job_runs (
  id uuid primary key default gen_random_uuid(),
  job_def_id uuid references job_definitions(id) on delete cascade,
  symbol text not null,
  timeframe text not null,
  job_type text not null,
  slice_from timestamptz,
  slice_to timestamptz,
  status text check (status in ('queued','running','success','failed','cancelled')) not null default 'queued',
  progress_percent numeric default 0,
  rows_written int default 0,
  provider text,
  attempt int not null default 1,
  error_message text,
  error_code text,
  triggered_by text default 'cron', -- 'cron'|'user'|'system'
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Idempotency hash for deduplication
  idx_hash text generated always as (
    md5((symbol||'|'||timeframe||'|'||coalesce(slice_from::text,'')||'|'||coalesce(slice_to::text,'')))
  ) stored
);

create index idx_job_runs_symbol_tf_status on job_runs(symbol, timeframe, status);
create index idx_job_runs_status_created on job_runs(status, created_at desc) where status in ('queued', 'running');
create index idx_job_runs_idx_hash on job_runs(idx_hash);
create index idx_job_runs_created_desc on job_runs(created_at desc);

-- Coverage status: quick read for data completeness
create table if not exists coverage_status (
  symbol text not null,
  timeframe text not null,
  from_ts timestamptz,
  to_ts timestamptz,
  last_success_at timestamptz,
  last_rows_written int default 0,
  last_provider text,
  updated_at timestamptz not null default now(),
  primary key(symbol, timeframe)
);

create index idx_coverage_status_updated on coverage_status(updated_at desc);

-- Enable realtime for job_runs (client subscriptions)
alter publication supabase_realtime add table job_runs;

-- Function to update coverage_status after successful job_run
create or replace function update_coverage_status()
returns trigger as $$
begin
  if NEW.status = 'success' and NEW.rows_written > 0 then
    insert into coverage_status (symbol, timeframe, from_ts, to_ts, last_success_at, last_rows_written, last_provider, updated_at)
    values (NEW.symbol, NEW.timeframe, NEW.slice_from, NEW.slice_to, NEW.finished_at, NEW.rows_written, NEW.provider, now())
    on conflict (symbol, timeframe) do update set
      from_ts = least(coverage_status.from_ts, EXCLUDED.from_ts),
      to_ts = greatest(coverage_status.to_ts, EXCLUDED.to_ts),
      last_success_at = EXCLUDED.last_success_at,
      last_rows_written = EXCLUDED.last_rows_written,
      last_provider = EXCLUDED.last_provider,
      updated_at = now();
  end if;
  return NEW;
end;
$$ language plpgsql;

create trigger trigger_update_coverage_status
after update on job_runs
for each row
when (NEW.status = 'success')
execute function update_coverage_status();

-- Function to get coverage gaps for a symbol/timeframe
create or replace function get_coverage_gaps(
  p_symbol text,
  p_timeframe text,
  p_window_days int default 7
)
returns table(
  gap_from timestamptz,
  gap_to timestamptz,
  gap_hours numeric
) as $$
declare
  v_target_from timestamptz;
  v_target_to timestamptz;
  v_coverage_from timestamptz;
  v_coverage_to timestamptz;
begin
  -- Calculate target window
  v_target_to := now();
  v_target_from := v_target_to - (p_window_days || ' days')::interval;
  
  -- Get current coverage
  select from_ts, to_ts into v_coverage_from, v_coverage_to
  from coverage_status
  where symbol = p_symbol and timeframe = p_timeframe;
  
  -- If no coverage, return full window as gap
  if v_coverage_from is null then
    return query select v_target_from, v_target_to, extract(epoch from (v_target_to - v_target_from))/3600;
    return;
  end if;
  
  -- Check for gaps at start
  if v_coverage_from > v_target_from then
    return query select v_target_from, v_coverage_from, extract(epoch from (v_coverage_from - v_target_from))/3600;
  end if;
  
  -- Check for gaps at end
  if v_coverage_to < v_target_to then
    return query select v_coverage_to, v_target_to, extract(epoch from (v_target_to - v_coverage_to))/3600;
  end if;
end;
$$ language plpgsql;

-- Function to claim a queued job (advisory lock pattern)
create or replace function claim_queued_job(p_job_type text default null)
returns table(
  job_run_id uuid,
  symbol text,
  timeframe text,
  job_type text,
  slice_from timestamptz,
  slice_to timestamptz
) as $$
declare
  v_lock_key bigint;
  v_job_run record;
begin
  -- Find highest priority queued job
  select * into v_job_run
  from job_runs jr
  left join job_definitions jd on jr.job_def_id = jd.id
  where jr.status = 'queued'
    and (p_job_type is null or jr.job_type = p_job_type)
  order by coalesce(jd.priority, 100) desc, jr.created_at asc
  limit 1
  for update skip locked;
  
  if not found then
    return;
  end if;
  
  -- Try advisory lock (hash of symbol|timeframe|job_type)
  v_lock_key := ('x' || substr(md5(v_job_run.symbol || '|' || v_job_run.timeframe || '|' || v_job_run.job_type), 1, 15))::bit(60)::bigint;
  
  if not pg_try_advisory_xact_lock(v_lock_key) then
    return; -- Another worker has this job
  end if;
  
  -- Claim the job
  update job_runs
  set status = 'running',
      started_at = now(),
      updated_at = now()
  where id = v_job_run.id;
  
  return query select v_job_run.id, v_job_run.symbol, v_job_run.timeframe, 
                      v_job_run.job_type, v_job_run.slice_from, v_job_run.slice_to;
end;
$$ language plpgsql;

-- Function to check if a job slice already exists (idempotency)
create or replace function job_slice_exists(
  p_symbol text,
  p_timeframe text,
  p_slice_from timestamptz,
  p_slice_to timestamptz
)
returns boolean as $$
declare
  v_hash text;
begin
  v_hash := md5(p_symbol || '|' || p_timeframe || '|' || coalesce(p_slice_from::text, '') || '|' || coalesce(p_slice_to::text, ''));
  
  return exists(
    select 1 from job_runs
    where idx_hash = v_hash
      and status in ('queued', 'running', 'success')
  );
end;
$$ language plpgsql;

-- Seed some default job definitions for watchlist symbols
-- (This can be customized based on your watchlist)
insert into job_definitions (job_type, symbol, timeframe, window_days, priority, enabled)
values
  -- Intraday jobs (high priority)
  ('fetch_intraday', 'AAPL', '15m', 5, 200, true),
  ('fetch_intraday', 'AAPL', '1h', 5, 190, true),
  ('fetch_intraday', 'NVDA', '15m', 5, 200, true),
  ('fetch_intraday', 'NVDA', '1h', 5, 190, true),
  ('fetch_intraday', 'TSLA', '15m', 5, 200, true),
  ('fetch_intraday', 'TSLA', '1h', 5, 190, true),
  
  -- Daily jobs (medium priority)
  ('fetch_historical', 'AAPL', 'd1', 365, 100, true),
  ('fetch_historical', 'NVDA', 'd1', 365, 100, true),
  ('fetch_historical', 'TSLA', 'd1', 365, 100, true),
  
  -- Forecast jobs (lower priority, run after data ready)
  ('run_forecast', 'AAPL', 'd1', 90, 50, true),
  ('run_forecast', 'NVDA', 'd1', 90, 50, true),
  ('run_forecast', 'TSLA', 'd1', 90, 50, true)
on conflict (symbol, timeframe, job_type) do nothing;

-- Grant permissions
grant select, insert, update on job_definitions to anon, authenticated;
grant select on job_runs to anon, authenticated;
grant select on coverage_status to anon, authenticated;

comment on table job_definitions is 'Templates for periodic and on-demand data jobs';
comment on table job_runs is 'Individual job execution slices with realtime progress tracking';
comment on table coverage_status is 'Quick lookup for data completeness per symbol/timeframe';
comment on function get_coverage_gaps is 'Returns time gaps in coverage for a symbol/timeframe';
comment on function claim_queued_job is 'Claims next queued job with advisory lock (orchestrator use)';
comment on function job_slice_exists is 'Checks if a job slice already exists (idempotency check)';
