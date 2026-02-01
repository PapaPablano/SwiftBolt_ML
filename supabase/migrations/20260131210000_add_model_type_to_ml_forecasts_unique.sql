-- Migration: Add model_type to ml_forecasts unique constraint
-- Date: 2026-01-31
-- Description: Changes unique constraint from (symbol_id, timeframe, horizon) to
--              (symbol_id, timeframe, horizon, model_type) so multiple model types
--              (xgboost, tabpfn) can coexist per symbol/horizon for side-by-side comparison.
--
-- Prerequisite: 20260131180000_add_model_type_to_ml_forecasts.sql (adds model_type column)

-- Step 1: Drop existing unique constraint (by name) if present (e.g. from Supabase dashboard)
ALTER TABLE ml_forecasts
DROP CONSTRAINT IF EXISTS ml_forecasts_symbol_timeframe_horizon_unique;

-- Step 2: Drop the unique index if it exists (from 20260124000000 migration)
DROP INDEX IF EXISTS ux_ml_forecasts_symbol_timeframe_horizon;

-- Step 3: Ensure model_type is NOT NULL with default for any stragglers
UPDATE ml_forecasts SET model_type = 'xgboost' WHERE model_type IS NULL;
ALTER TABLE ml_forecasts ALTER COLUMN model_type SET DEFAULT 'xgboost';

-- Step 4: Create new unique index including model_type
CREATE UNIQUE INDEX IF NOT EXISTS ux_ml_forecasts_symbol_timeframe_horizon_model_type
ON ml_forecasts(symbol_id, timeframe, horizon, model_type);

COMMENT ON INDEX ux_ml_forecasts_symbol_timeframe_horizon_model_type IS
    'One forecast row per (symbol, timeframe, horizon, model_type) - allows xgboost and tabpfn to coexist';
