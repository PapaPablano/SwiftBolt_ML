-- Add expected-move dollar columns to options_feature_snapshots
-- expected_move_*_dollar = spot * expected_move_*_pct / 100 (computed when persisting)
alter table public.options_feature_snapshots
  add column if not exists expected_move_near_dollar double precision,
  add column if not exists expected_move_far_dollar double precision;

comment on column public.options_feature_snapshots.expected_move_near_dollar is
  'Expected 1-sigma move near expiry in dollars: spot * expected_move_near_pct / 100';
comment on column public.options_feature_snapshots.expected_move_far_dollar is
  'Expected 1-sigma move far expiry in dollars: spot * expected_move_far_pct / 100';
