-- options_feature_snapshots: persist filtered feature snapshots only (no full chain)
-- For 5/15-min IV rank baselines and term-structure history.
create table if not exists public.options_feature_snapshots (
  id               bigint generated always as identity primary key,
  symbol           text not null,
  ts_utc           timestamptz not null default now(),
  expiry_near_ts   bigint,
  expiry_far_ts    bigint,
  atm_iv_near      double precision,
  atm_iv_far       double precision,
  forward_vol      double precision,
  skew_proxy       double precision,
  vrp              double precision,
  term_structure_regime text,
  low_confidence   boolean default false,
  expected_move_near_pct double precision,
  expected_move_far_pct  double precision,
  created_at       timestamptz not null default now()
);

comment on table public.options_feature_snapshots is
  'Filtered options feature snapshots for IV rank/percentiles and term-structure baselines. No full chain.';

create index if not exists idx_options_feature_snapshots_symbol_ts
  on public.options_feature_snapshots(symbol, ts_utc desc);

alter table public.options_feature_snapshots enable row level security;
