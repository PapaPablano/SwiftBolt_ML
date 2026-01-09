-- Add missing orchestrator database functions
-- These are required for the orchestrator Edge Function to process jobs

-- Function to check if a job slice already exists (idempotency)
create or replace function job_slice_exists(
  p_symbol text,
  p_timeframe text,
  p_slice_from timestamptz,
  p_slice_to timestamptz
)
returns boolean as $$
declare
  v_exists boolean;
begin
  select exists(
    select 1 from job_runs
    where symbol = p_symbol
      and timeframe = p_timeframe
      and slice_from = p_slice_from
      and slice_to = p_slice_to
      and status in ('queued', 'running', 'success')
  ) into v_exists;
  
  return v_exists;
end;
$$ language plpgsql;

-- Function to claim the next queued job atomically
create or replace function claim_queued_job()
returns table(
  job_run_id uuid,
  symbol text,
  timeframe text,
  job_type text,
  slice_from timestamptz,
  slice_to timestamptz
) as $$
declare
  v_job_run record;
begin
  -- Find and lock the next queued job (FIFO by created_at)
  select id, symbol, timeframe, job_type, slice_from, slice_to
  into v_job_run
  from job_runs
  where status = 'queued'
  order by created_at asc
  limit 1
  for update skip locked;
  
  -- If no job found, return empty
  if v_job_run.id is null then
    return;
  end if;
  
  -- Mark job as running
  update job_runs
  set 
    status = 'running',
    started_at = now(),
    updated_at = now()
  where id = v_job_run.id;
  
  -- Return the claimed job
  return query
  select 
    v_job_run.id as job_run_id,
    v_job_run.symbol,
    v_job_run.timeframe,
    v_job_run.job_type,
    v_job_run.slice_from,
    v_job_run.slice_to;
end;
$$ language plpgsql;

-- Grant execute permissions
grant execute on function job_slice_exists(text, text, timestamptz, timestamptz) to anon, authenticated, service_role;
grant execute on function claim_queued_job() to anon, authenticated, service_role;
