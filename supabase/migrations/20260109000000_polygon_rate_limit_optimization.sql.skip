-- Polygon Rate Limit Optimization
-- Implements distributed token bucket for provider rate limiting
-- Prevents 429 errors by coordinating requests across all workers

-- 1. Rate buckets table (distributed token bucket)
create table if not exists rate_buckets (
  provider text primary key,
  capacity int not null,
  refill_per_min int not null,
  tokens numeric not null,
  updated_at timestamptz not null default now()
);

-- Seed initial providers
insert into rate_buckets(provider, capacity, refill_per_min, tokens)
values 
  ('polygon', 5, 5, 5),      -- Polygon free tier: 5 req/min
  ('massive', 5, 5, 5),       -- Alias for Polygon (same backend)
  ('tradier', 120, 120, 120), -- Tradier: 120 req/min
  ('yahoo', 2000, 2000, 2000), -- Yahoo: ~2000 req/min (generous estimate)
  ('finnhub', 60, 60, 60)     -- Finnhub free: 60 req/min
on conflict (provider) do nothing;

-- 2. Atomic token acquisition function
create or replace function take_token(p_provider text, p_cost numeric default 1)
returns boolean
language plpgsql as $$
declare
  v_capacity int;
  v_refill_per_min int;
  v_tokens numeric;
  v_updated_at timestamptz;
  v_new_tokens numeric;
begin
  -- Lock row for update and refill tokens
  select 
    capacity,
    refill_per_min,
    tokens,
    updated_at
  into 
    v_capacity,
    v_refill_per_min,
    v_tokens,
    v_updated_at
  from rate_buckets
  where provider = p_provider
  for update;

  if not found then
    raise exception 'Provider % not found in rate_buckets', p_provider;
  end if;

  -- Calculate refilled tokens based on time elapsed
  v_new_tokens := least(
    v_capacity::numeric,
    v_tokens + (extract(epoch from (now() - v_updated_at)) / 60.0) * v_refill_per_min
  );

  -- Check if we have enough tokens
  if v_new_tokens >= p_cost then
    -- Deduct tokens and update timestamp
    update rate_buckets
    set 
      tokens = v_new_tokens - p_cost,
      updated_at = now()
    where provider = p_provider;
    
    return true;
  else
    -- Not enough tokens, just update the refilled amount
    update rate_buckets
    set 
      tokens = v_new_tokens,
      updated_at = now()
    where provider = p_provider;
    
    return false;
  end if;
end$$;

-- 3. Provider checkpoints for resumable fetches
create table if not exists provider_checkpoints (
  provider text not null,
  symbol text not null,
  timeframe text not null,
  last_ts timestamptz,
  bars_written int default 0,
  updated_at timestamptz default now(),
  primary key (provider, symbol, timeframe)
);

create index if not exists idx_provider_checkpoints_updated 
  on provider_checkpoints(provider, updated_at desc);

-- 4. Helper function to get token availability
create or replace function get_token_status(p_provider text)
returns table(
  provider text,
  available_tokens numeric,
  capacity int,
  refill_rate int,
  seconds_until_full numeric
) language plpgsql as $$
declare
  v_capacity int;
  v_refill_per_min int;
  v_tokens numeric;
  v_updated_at timestamptz;
  v_current_tokens numeric;
begin
  select 
    rb.capacity,
    rb.refill_per_min,
    rb.tokens,
    rb.updated_at
  into 
    v_capacity,
    v_refill_per_min,
    v_tokens,
    v_updated_at
  from rate_buckets rb
  where rb.provider = p_provider;

  if not found then
    return;
  end if;

  -- Calculate current tokens with refill
  v_current_tokens := least(
    v_capacity::numeric,
    v_tokens + (extract(epoch from (now() - v_updated_at)) / 60.0) * v_refill_per_min
  );

  return query select 
    p_provider,
    v_current_tokens,
    v_capacity,
    v_refill_per_min,
    case 
      when v_current_tokens >= v_capacity then 0
      else ((v_capacity - v_current_tokens) / v_refill_per_min) * 60
    end as seconds_until_full;
end$$;

-- 5. Add expected_cost to job_runs for observability
alter table job_runs 
  add column if not exists expected_cost numeric default 1,
  add column if not exists actual_cost numeric default 0;

create index if not exists idx_job_runs_provider_cost 
  on job_runs(provider, expected_cost) 
  where status = 'success';

comment on column job_runs.expected_cost is 'Estimated API calls needed for this job';
comment on column job_runs.actual_cost is 'Actual API calls made (including retries)';
