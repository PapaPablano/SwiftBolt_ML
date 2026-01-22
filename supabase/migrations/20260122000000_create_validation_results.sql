-- Creates validation_results table for storing unified validation predictions
-- This table stores the output of UnifiedValidator for dashboard display

set check_function_bodies = off;

-- Create validation_results table
create table if not exists public.validation_results (
    id uuid primary key default gen_random_uuid(),
    symbol_id uuid not null references public.symbols(id) on delete cascade,
    symbol varchar(20) not null,  -- Denormalized for easy querying
    direction varchar(20) not null check (direction in ('BULLISH', 'BEARISH', 'NEUTRAL')),
    
    -- Unified confidence score (0-1)
    unified_confidence numeric not null check (unified_confidence >= 0 and unified_confidence <= 1),
    
    -- Component scores
    backtesting_score numeric not null check (backtesting_score >= 0 and backtesting_score <= 1),
    walkforward_score numeric not null check (walkforward_score >= 0 and walkforward_score <= 1),
    live_score numeric not null check (live_score >= 0 and live_score <= 1),
    
    -- Drift analysis
    drift_detected boolean not null default false,
    drift_magnitude numeric not null default 0 check (drift_magnitude >= 0 and drift_magnitude <= 1),
    drift_severity varchar(20) not null default 'none' 
        check (drift_severity in ('none', 'minor', 'moderate', 'severe', 'critical')),
    drift_explanation text,
    
    -- Multi-timeframe reconciliation
    timeframe_conflict boolean not null default false,
    consensus_direction varchar(20) not null,
    conflict_explanation text,
    
    -- Recommendations
    recommendation text not null,
    retraining_trigger boolean not null default false,
    retraining_reason text,
    
    -- Metadata
    created_at timestamptz not null default now()
);

-- Indexes for efficient querying
create index if not exists validation_results_symbol_created_at_idx 
    on public.validation_results (symbol, created_at desc);

create index if not exists validation_results_drift_detected_idx 
    on public.validation_results (drift_detected, drift_severity, created_at desc) 
    where drift_detected = true;

create index if not exists validation_results_retraining_trigger_idx 
    on public.validation_results (retraining_trigger, created_at desc) 
    where retraining_trigger = true;

-- Enable RLS
alter table public.validation_results enable row level security;

-- Service role full access
create policy "Service role full access"
    on public.validation_results
    for all
    using (auth.role() = 'service_role')
    with check (auth.role() = 'service_role');

-- Authenticated users can read
create policy "Authenticated users can read validation results"
    on public.validation_results
    for select
    using (auth.role() = 'authenticated');

-- Create view for latest validation per symbol
create or replace view public.latest_validation_results as
select distinct on (symbol)
    symbol,
    direction,
    unified_confidence,
    backtesting_score,
    walkforward_score,
    live_score,
    drift_detected,
    drift_magnitude,
    drift_severity,
    drift_explanation,
    timeframe_conflict,
    consensus_direction,
    recommendation,
    retraining_trigger,
    created_at
from public.validation_results
order by symbol, created_at desc;

-- Grant permissions
grant select on public.latest_validation_results to authenticated, anon;
