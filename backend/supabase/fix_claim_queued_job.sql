-- Fix for claim_queued_job() function - Column Ambiguity Bug
-- This fixes the "column reference 'symbol' is ambiguous" error (code 42702)
-- that's preventing jobs from being dispatched to workers

-- Drop the existing function first
DROP FUNCTION IF EXISTS public.claim_queued_job();

-- Create the corrected version with properly qualified column names
CREATE OR REPLACE FUNCTION public.claim_queued_job()
RETURNS TABLE(
  job_run_id uuid,
  symbol text,
  timeframe text,
  job_type text,
  slice_from timestamp with time zone,
  slice_to timestamp with time zone
)
LANGUAGE plpgsql
AS $function$
declare
  v_job_run record;
begin
  -- FIX: Explicitly qualify all column names with table name to avoid ambiguity
  select
    job_runs.id,
    job_runs.symbol,
    job_runs.timeframe,
    job_runs.job_type,
    job_runs.slice_from,
    job_runs.slice_to
  into v_job_run
  from job_runs
  where job_runs.status = 'queued'
  order by job_runs.created_at asc
  limit 1
  for update skip locked;

  -- If no job found, return empty
  if v_job_run is null then
    return;
  end if;

  -- Mark job as running
  update job_runs
  set
    status = 'running',
    started_at = now()
  where job_runs.id = v_job_run.id;

  -- Return the claimed job details
  return query
  select
    v_job_run.id,
    v_job_run.symbol,
    v_job_run.timeframe,
    v_job_run.job_type,
    v_job_run.slice_from,
    v_job_run.slice_to;
end;
$function$;

-- Add helpful comment
COMMENT ON FUNCTION public.claim_queued_job() IS
'Claims the oldest queued job and marks it as running. Uses FOR UPDATE SKIP LOCKED for concurrency safety. Returns job details or empty if no jobs available.';

-- Verify the function was created successfully
SELECT
  proname as function_name,
  pg_get_functiondef(oid) as definition
FROM pg_proc
WHERE proname = 'claim_queued_job'
  AND pronamespace = 'public'::regnamespace;
