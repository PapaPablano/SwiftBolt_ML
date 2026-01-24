-- Migration: Fix ml_forecasts unique constraint to include timeframe
-- Date: 2026-01-24
-- Description: Updates the unique constraint from (symbol_id, horizon) to (symbol_id, timeframe, horizon)
--              to support multiple timeframes per symbol/horizon combination

-- Step 1: Drop old unique constraint (if exists)
DO $$ 
BEGIN
    -- Drop the constraint if it exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'ml_forecasts_symbol_id_horizon_key'
    ) THEN
        ALTER TABLE ml_forecasts DROP CONSTRAINT ml_forecasts_symbol_id_horizon_key;
        RAISE NOTICE 'Dropped constraint: ml_forecasts_symbol_id_horizon_key';
    END IF;

    -- Drop the old unique index if it exists
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'ux_ml_forecasts_symbol_horizon'
    ) THEN
        DROP INDEX IF EXISTS ux_ml_forecasts_symbol_horizon;
        RAISE NOTICE 'Dropped index: ux_ml_forecasts_symbol_horizon';
    END IF;
END $$;

-- Step 2: Ensure timeframe column exists (should already exist from 20260121000000)
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS timeframe TEXT;

-- Step 3: Set default timeframe for any existing rows that don't have it
-- Use 'd1' as default for daily forecasts
UPDATE ml_forecasts
SET timeframe = 'd1'
WHERE timeframe IS NULL;

-- Step 4: Make timeframe NOT NULL now that all rows have a value
ALTER TABLE ml_forecasts
ALTER COLUMN timeframe SET NOT NULL;

-- Step 5: Create new unique constraint on (symbol_id, timeframe, horizon)
CREATE UNIQUE INDEX IF NOT EXISTS ux_ml_forecasts_symbol_timeframe_horizon
ON ml_forecasts(symbol_id, timeframe, horizon);

-- Verification query to check the index was created
-- SELECT 
--     indexname, 
--     indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'ml_forecasts' 
--     AND indexname LIKE 'ux_%';
