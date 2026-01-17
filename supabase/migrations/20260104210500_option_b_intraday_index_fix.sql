-- Fix Option B index for intraday evaluations
-- Use forecast_created_at (forecast creation time) for ordering

-- Drop the prior index attempt if it exists
DROP INDEX IF EXISTS idx_intraday_eval_option_b_created;

-- Create index on forecast_created_at and option_b_outcome
CREATE INDEX IF NOT EXISTS idx_intraday_eval_option_b_created
ON ml_forecast_evaluations_intraday(forecast_created_at, option_b_outcome);
