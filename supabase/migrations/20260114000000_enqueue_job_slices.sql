create or replace function enqueue_job_slices(
  p_job_def_id uuid,
  p_symbol text,
  p_timeframe text,
  p_job_type text,
  p_slices jsonb,
  p_triggered_by text default 'cron'
)
returns table(inserted_count int) as $$
declare
  v_inserted int;
begin
  perform pg_advisory_xact_lock(hashtext(p_symbol || '|' || p_timeframe));

  with slices as (
    select
      (s->>'slice_from')::timestamptz as slice_from,
      (s->>'slice_to')::timestamptz as slice_to
    from jsonb_array_elements(p_slices) as s
  ),
  ins as (
    insert into job_runs(
      job_def_id,
      symbol,
      timeframe,
      job_type,
      slice_from,
      slice_to,
      status,
      triggered_by
    )
    select
      p_job_def_id,
      p_symbol,
      p_timeframe,
      p_job_type,
      sl.slice_from,
      sl.slice_to,
      'queued',
      p_triggered_by
    from slices sl
    where not exists (
      select 1
      from job_runs jr
      where jr.symbol = p_symbol
        and jr.timeframe = p_timeframe
        and jr.slice_from = sl.slice_from
        and jr.slice_to = sl.slice_to
        and jr.status in ('queued', 'running', 'success')
    )
    returning 1
  )
  select count(*) into v_inserted from ins;

  return query select v_inserted;
end;
$$ language plpgsql;

grant execute on function enqueue_job_slices(uuid, text, text, text, jsonb, text) to anon, authenticated, service_role;
