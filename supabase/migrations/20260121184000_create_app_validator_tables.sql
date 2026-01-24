-- Creates schema support for app-centric validation workflow described in docs/README_APP_VALIDATOR_STRATEGY.md
-- Provides storage for historical validation scores, latest live signals, and optional audit logs

set check_function_bodies = off;

-- Enumerations -------------------------------------------------------------

create type public.validation_score_type as enum ('backtest', 'walkforward');
create type public.validation_signal as enum ('BULLISH', 'BEARISH', 'NEUTRAL');

-- Core validation score snapshots ----------------------------------------

create table public.model_validation_stats (
    id uuid primary key default gen_random_uuid(),
    symbol_id uuid not null references public.symbols on delete cascade,
    validation_type public.validation_score_type not null,
    accuracy numeric not null check (accuracy >= 0 and accuracy <= 1),
    sample_size integer,
    window_start timestamptz,
    window_end timestamptz,
    metrics jsonb,
    created_at timestamptz not null default now()
);

create index model_validation_stats_symbol_validation_type_idx
    on public.model_validation_stats (symbol_id, validation_type, created_at desc);

alter table public.model_validation_stats enable row level security;

create policy "Service role full access"
    on public.model_validation_stats
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');

-- Live prediction snapshots (per timeframe) -------------------------------

create table public.live_predictions (
    id uuid primary key default gen_random_uuid(),
    symbol_id uuid not null references public.symbols on delete cascade,
    timeframe public.timeframe not null,
    signal public.validation_signal not null,
    accuracy_score numeric not null check (accuracy_score >= 0 and accuracy_score <= 1),
    metadata jsonb,
    prediction_time timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index live_predictions_symbol_timeframe_time_idx
    on public.live_predictions (symbol_id, timeframe, prediction_time desc);

alter table public.live_predictions enable row level security;

create policy "Service role full access"
    on public.live_predictions
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');

-- Optional audit log syncing from the app ---------------------------------

create table public.validation_audits (
    id uuid primary key default gen_random_uuid(),
    symbol_id uuid not null references public.symbols on delete cascade,
    user_id uuid,
    confidence_score numeric not null check (confidence_score >= 0 and confidence_score <= 1),
    weights_config jsonb,
    client_state jsonb,
    logged_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index validation_audits_symbol_logged_at_idx
    on public.validation_audits (symbol_id, logged_at desc);

alter table public.validation_audits enable row level security;

create policy "Service role full access"
    on public.validation_audits
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');

-- Helpful view that surfaces most recent scores per symbol -----------------

create view public.latest_model_validation_stats as
select distinct on (symbol_id, validation_type)
    symbol_id,
    validation_type,
    accuracy,
    sample_size,
    window_start,
    window_end,
    metrics,
    created_at as recorded_at
from public.model_validation_stats
order by symbol_id, validation_type, created_at desc;

create view public.latest_live_predictions as
select distinct on (symbol_id, timeframe)
    symbol_id,
    timeframe,
    signal,
    accuracy_score,
    metadata,
    prediction_time
from public.live_predictions
order by symbol_id, timeframe, prediction_time desc;
