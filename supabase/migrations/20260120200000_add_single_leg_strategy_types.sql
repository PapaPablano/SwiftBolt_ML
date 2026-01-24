-- Migration: Add single-leg strategy types
-- Allows tracking individual naked options alongside multi-leg strategies

-- Add new strategy types to the enum
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'long_call';
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'long_put';
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'short_call';
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'short_put';
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'covered_call';
ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS 'cash_secured_put';
