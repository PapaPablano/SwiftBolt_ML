-- SPEC-8: Unified Market Data Orchestrator (Consolidated)
-- Creates job_definitions, job_runs, coverage_status tables with pg_cron and Realtime

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

create index if not exists idx_job_definitions_enabled on job_definitions(enabled, priority desc) where enabled = true;
create index if not exists idx_job_definitions_symbol_tf on job_definitions(symbol, timeframe);

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
  idx_hash text
);

create index if not exists idx_job_runs_symbol_tf_status on job_runs(symbol, timeframe, status);
create index if not exists idx_job_runs_status_created on job_runs(status, created_at desc) where status in ('queued', 'running');
create index if not exists idx_job_runs_idx_hash on job_runs(idx_hash);
create index if not exists idx_job_runs_created_desc on job_runs(created_at desc);

-- Coverage status: quick read for data completeness
create table if not exists coverage_status (
  symbol text not null,
  timeframe text not null,
  from_ts timestamptz,
  to_ts timestamptz,
  last_success_at timestamptz,
  last_rows_written int,
  last_provider text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(symbol, timeframe)
);

create index if not exists idx_coverage_status_updated on coverage_status(updated_at desc);

-- Enable realtime for job_runs (client subscriptions)
do $$
begin
  if not exists (
    select 1 from pg_publication_tables 
    where pubname = 'supabase_realtime' and tablename = 'job_runs'
  ) then
    alter publication supabase_realtime add table job_runs;
  end if;
end $$;

-- Enable RLS on job_runs
alter table job_runs enable row level security;

-- RLS policies for job_runs
drop policy if exists "Allow authenticated users to read job_runs" on job_runs;
create policy "Allow authenticated users to read job_runs"
  on job_runs for select using (true);

drop policy if exists "Allow anon users to read job_runs" on job_runs;
create policy "Allow anon users to read job_runs"
  on job_runs for select using (true);

-- Grant permissions
grant select on job_runs to anon, authenticated;
grant select, insert, update, delete on job_definitions to anon, authenticated, service_role;
grant select, insert, update, delete on job_runs to anon, authenticated, service_role;
grant select, insert, update, delete on coverage_status to anon, authenticated, service_role;

-- Trigger to populate idx_hash on insert/update
create or replace function set_job_run_idx_hash()
returns trigger as $$
begin
  NEW.idx_hash := md5(
    NEW.symbol || '|' || 
    NEW.timeframe || '|' || 
    coalesce(to_char(NEW.slice_from, 'YYYY-MM-DD HH24:MI:SS'), '') || '|' || 
    coalesce(to_char(NEW.slice_to, 'YYYY-MM-DD HH24:MI:SS'), '')
  );
  return NEW;
end;
$$ language plpgsql;

drop trigger if exists trigger_set_idx_hash on job_runs;
create trigger trigger_set_idx_hash
before insert or update on job_runs
for each row
execute function set_job_run_idx_hash();

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

drop trigger if exists trigger_update_coverage_status on job_runs;
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
  v_target_to := now();
  v_target_from := v_target_to - (p_window_days || ' days')::interval;

  select from_ts, to_ts into v_coverage_from, v_coverage_to
  from coverage_status
  where symbol = p_symbol and timeframe = p_timeframe;

  if v_coverage_from is null or v_coverage_to is null then
    return query select v_target_from, v_target_to, extract(epoch from (v_target_to - v_target_from)) / 3600.0;
    return;
  end if;

  if v_coverage_from > v_target_from then
    return query select v_target_from, v_coverage_from, extract(epoch from (v_coverage_from - v_target_from)) / 3600.0;
  end if;

  if v_coverage_to < v_target_to then
    return query select v_coverage_to, v_target_to, extract(epoch from (v_target_to - v_coverage_to)) / 3600.0;
  end if;

  return;
end;
$$ language plpgsql;

-- pg_cron setup (extension already exists from previous migration)
-- Create cron job to call orchestrator every minute
do $outer$
begin
  -- Delete existing job if it exists
  perform cron.unschedule('orchestrator-tick');
exception when others then
  -- Job doesn't exist, continue
end $outer$;

do $outer$
begin
  perform cron.schedule(
    'orchestrator-tick',
    '* * * * *',
    $inner$
    select net.http_post(
      url := current_setting('app.supabase_url', true) || '/functions/v1/orchestrator?action=tick',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || current_setting('app.supabase_service_role_key', true),
        'Content-Type', 'application/json'
      ),
      body := '{}'::jsonb
    ) as request_id;
    $inner$
  );
exception when others then
  raise notice 'Cron job already exists or error: %', SQLERRM;
end $outer$;
