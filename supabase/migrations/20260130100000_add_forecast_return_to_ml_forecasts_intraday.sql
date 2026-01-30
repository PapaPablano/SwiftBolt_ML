-- Add forecast_return to ml_forecasts_intraday (expected by ML pipeline and timeframe_consensus).
-- Fixes: column ml_forecasts_intraday.forecast_return does not exist
ALTER TABLE public.ml_forecasts_intraday
  ADD COLUMN IF NOT EXISTS forecast_return DOUBLE PRECISION;

COMMENT ON COLUMN public.ml_forecasts_intraday.forecast_return IS 'Expected return as decimal (e.g., 0.015 = 1.5%) for intraday horizon';
