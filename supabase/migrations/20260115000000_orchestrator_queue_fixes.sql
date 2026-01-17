create or replace function public.reset_stale_running_jobs(
  p_max_age_minutes int default 60,
  p_max_attempts int default 5
)
returns table(reset_count int)
language plpgsql
as $$
declare
  v_reset int;
  v_failed int;
begin
  with stale as (
    select jr.id, jr.attempt
    from public.job_runs jr
    where jr.status = 'running'
      and coalesce(jr.started_at, jr.updated_at, jr.created_at) < now() - make_interval(mins => p_max_age_minutes)
    for update skip locked
  ),
  to_fail as (
    update public.job_runs jr
    set
      status = 'failed',
      error_message = 'Stale running job exceeded max attempts',
      error_code = 'STALE_RUNNING',
      finished_at = now(),
      updated_at = now()
    from stale s
    where jr.id = s.id
      and s.attempt >= p_max_attempts
    returning 1
  ),
  to_reset as (
    update public.job_runs jr
    set
      status = 'queued',
      attempt = jr.attempt + 1,
      error_message = null,
      error_code = null,
      started_at = null,
      updated_at = now()
    from stale s
    where jr.id = s.id
      and s.attempt < p_max_attempts
    returning 1
  )
  select count(*) into v_failed from to_fail;

  select count(*) into v_reset from to_reset;

  return query select (coalesce(v_reset, 0) + coalesce(v_failed, 0));
end;
$$;

grant execute on function public.reset_stale_running_jobs(int, int) to anon, authenticated, service_role;

create or replace function public.claim_queued_job()
returns table(
  job_run_id uuid,
  symbol text,
  timeframe text,
  job_type text,
  slice_from timestamptz,
  slice_to timestamptz
)
language plpgsql
as $$
declare
  v_job_run record;
begin
  select
    jr.id as job_run_id,
    jr.symbol,
    jr.timeframe,
    jr.job_type,
    jr.slice_from,
    jr.slice_to
  into v_job_run
  from public.job_runs jr
  left join public.job_definitions jd
    on jd.id = jr.job_def_id
  where jr.status = 'queued'
  order by
    case jr.timeframe
      when 'm15' then 1
      when 'h1' then 2
      when 'h4' then 3
      when 'd1' then 4
      when 'w1' then 5
      else 6
    end asc,
    coalesce(jr.slice_to, jr.created_at) desc,
    coalesce(jd.priority, 0) desc,
    jr.created_at desc
  limit 1
  for update skip locked;

  if v_job_run.job_run_id is null then
    return;
  end if;

  update public.job_runs
  set
    status = 'running',
    started_at = now(),
    updated_at = now()
  where id = v_job_run.job_run_id;

  return query
  select
    v_job_run.job_run_id,
    v_job_run.symbol,
    v_job_run.timeframe,
    v_job_run.job_type,
    v_job_run.slice_from,
    v_job_run.slice_to;
end;
$$;

grant execute on function public.claim_queued_job() to anon, authenticated, service_role;
