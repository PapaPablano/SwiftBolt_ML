-- SPEC-8: Intraday Backfill Orchestration
-- Server-side backfill with chunked, resumable work units
-- Eliminates UI blocking during intraday data hydration

-- Job header (idempotent per symbol/timeframe/window)
create table if not exists backfill_jobs (
  id uuid primary key default gen_random_uuid(),
  symbol text not null,
  timeframe text not null,          -- '15m'|'1h'|'4h'|'1d'|'1w'
  from_ts timestamptz not null,
  to_ts   timestamptz not null,
  status text not null default 'pending',  -- pending|running|done|error
  progress int not null default 0,         -- 0..100
  error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (symbol, timeframe, from_ts, to_ts)
);

-- Index for status queries
create index if not exists idx_backfill_jobs_status on backfill_jobs(status, created_at);
create index if not exists idx_backfill_jobs_symbol_tf on backfill_jobs(symbol, timeframe);

-- Chunked by calendar day for intraday resilience
create table if not exists backfill_chunks (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references backfill_jobs(id) on delete cascade,
  symbol text not null,
  timeframe text not null,
  day date not null,                              -- chunk boundary
  status text not null default 'pending',         -- pending|running|done|error
  try_count int not null default 0,
  last_error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (job_id, day)
);

-- Index for worker queries
create index if not exists idx_backfill_chunks_status on backfill_chunks(status, day);
create index if not exists idx_backfill_chunks_job on backfill_chunks(job_id, status);

-- Coverage helper (read-only)
create or replace function get_coverage(p_symbol text, p_timeframe text)
returns table(from_ts timestamptz, to_ts timestamptz)
language sql stable as $$
  select min(b.ts) as from_ts, max(b.ts) as to_ts
  from ohlc_bars_v2 b
  join symbols s on s.id = b.symbol_id
  where s.ticker = p_symbol and b.timeframe = p_timeframe;
$$;

-- Claim N chunks using SKIP LOCKED (prevents duplicate workers)
create or replace function claim_backfill_chunks(p_limit int)
returns setof backfill_chunks
language plpgsql as $$
begin
  return query
  with cte as (
    select id from backfill_chunks
    where status = 'pending'
    order by day asc
    for update skip locked
    limit p_limit
  )
  update backfill_chunks b
  set status = 'running', updated_at = now()
  from cte
  where b.id = cte.id
  returning b.*;
end;
$$;

-- Progress roll-up per job
create or replace function update_job_progress()
returns void language plpgsql as $$
begin
  update backfill_jobs j
  set progress = coalesce( (100 * t.done) / nullif(t.total,0), 100 ),
      status = case
        when t.error > 0 then 'error'
        when t.done = t.total then 'done'
        when t.running > 0 or t.pending > 0 then 'running'
        else j.status end,
      updated_at = now()
  from (
    select job_id,
           count(*) filter (where status='done') as done,
           count(*) filter (where status='error') as error,
           count(*) filter (where status='running') as running,
           count(*) filter (where status='pending') as pending,
           count(*) as total
    from backfill_chunks
    group by job_id
  ) t
  where j.id = t.job_id;
end;
$$;

-- Enable RLS for client access
alter table backfill_jobs enable row level security;

-- Simple read policy (clients can see all jobs for now; tighten for multi-tenant later)
create policy backfill_jobs_read on backfill_jobs 
  for select using (true);

-- Add to Realtime publication for progress updates
alter publication supabase_realtime add table backfill_jobs;

-- Trigger to update updated_at on backfill_jobs
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger backfill_jobs_updated_at
  before update on backfill_jobs
  for each row
  execute function update_updated_at_column();

create trigger backfill_chunks_updated_at
  before update on backfill_chunks
  for each row
  execute function update_updated_at_column();

-- Helper to check if coverage exists for a window
create or replace function has_coverage(
  p_symbol text,
  p_timeframe text,
  p_from_ts timestamptz,
  p_to_ts timestamptz
)
returns boolean
language sql stable as $$
  select exists(
    select 1 from ohlc_bars_v2 b
    join symbols s on s.id = b.symbol_id
    where s.ticker = p_symbol
      and b.timeframe = p_timeframe
      and b.ts >= p_from_ts
      and b.ts <= p_to_ts
    limit 1
  ) and (
    select min(b.ts) from ohlc_bars_v2 b
    join symbols s on s.id = b.symbol_id
    where s.ticker = p_symbol and b.timeframe = p_timeframe
  ) <= p_from_ts and (
    select max(b.ts) from ohlc_bars_v2 b
    join symbols s on s.id = b.symbol_id
    where s.ticker = p_symbol and b.timeframe = p_timeframe
  ) >= p_to_ts;
$$;

comment on table backfill_jobs is 'Tracks server-side backfill requests for intraday data';
comment on table backfill_chunks is 'Daily chunks for resumable, parallel backfill processing';
comment on function get_coverage is 'Returns min/max timestamp coverage for a symbol/timeframe';
comment on function claim_backfill_chunks is 'Atomically claims pending chunks for worker processing';
comment on function update_job_progress is 'Rolls up chunk status into job progress percentage';
