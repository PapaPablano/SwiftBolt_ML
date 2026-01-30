-- Performance fix for enqueue_job_slices: speeds up NOT EXISTS lookup
-- Reduces lock hold time under concurrent load (fixes 500 + ~8s response time)
-- The NOT EXISTS checks (symbol, timeframe, slice_from, slice_to, status)

create index if not exists idx_job_runs_enqueue_dedup
  on public.job_runs (symbol, timeframe, slice_from, slice_to)
  where status in ('queued', 'running', 'success');
