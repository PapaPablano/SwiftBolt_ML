-- Add strategy_intent to options_ranks for intent-aware ranking selection
-- long_premium (buyer) vs short_premium (seller) - affects IV/VRP/term-structure scoring
alter table public.options_ranks
  add column if not exists strategy_intent text default 'long_premium'
  check (strategy_intent in ('long_premium', 'short_premium'));

comment on column public.options_ranks.strategy_intent is
  'Strategy intent used when scoring: long_premium (buyer) vs short_premium (seller)';

-- Drop old unique index and recreate with strategy_intent
drop index if exists idx_options_ranks_unique;
create unique index if not exists idx_options_ranks_unique
  on public.options_ranks(underlying_symbol_id, ranking_mode, strategy_intent, expiry, strike, side);

create index if not exists idx_options_ranks_strategy_intent
  on public.options_ranks(strategy_intent);
