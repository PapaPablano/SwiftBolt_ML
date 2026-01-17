-- Fix ml_forecasts trigger issue
-- The trigger was referencing updated_at but having issues with PostgREST

-- Drop the existing trigger and function
DROP TRIGGER IF EXISTS trigger_ml_forecasts_updated_at ON ml_forecasts;
DROP FUNCTION IF EXISTS update_ml_forecasts_updated_at();

-- Remove updated_at column as it's causing issues and isn't critical
ALTER TABLE ml_forecasts DROP COLUMN IF EXISTS updated_at;

-- Keep created_at and run_at which are sufficient for tracking
COMMENT ON COLUMN ml_forecasts.created_at IS 'When the forecast record was first created';
COMMENT ON COLUMN ml_forecasts.run_at IS 'When the ML model was last run to generate this forecast';
