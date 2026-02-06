-- options_expiration_cache: per-symbol cached expiries for the 5-min ranker
-- Stores Unix seconds (BIGINT) to match /options-chain?expiration=TS usage.
create table if not exists public.options_expiration_cache (
  symbol           text primary key,
  expirations_ts   bigint[] not null default '{}',
  expiry_near_ts   bigint not null,
  expiry_far_ts    bigint not null,
  source           text not null default 'tradier',
  updated_at       timestamptz not null default now(),

  constraint options_expiry_near_positive check (expiry_near_ts > 0),
  constraint options_expiry_far_positive  check (expiry_far_ts > 0),
  constraint options_expiry_order_ok      check (expiry_far_ts >= expiry_near_ts)
);

comment on table public.options_expiration_cache is
  'Per-symbol option expirations cache for 5-min ranker. Stores Unix seconds for direct Edge /options-chain expiration param.';

create index if not exists idx_options_expiration_cache_updated_at
  on public.options_expiration_cache(updated_at);

-- Safe default: block anon/auth reads+writes unless you later add policies.
alter table public.options_expiration_cache enable row level security;
