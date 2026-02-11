-- Add synthesis_data JSONB to ml_forecasts_intraday for ensemble_result (xgb_prob, components, weights).
-- Evaluator and dashboards can read synthesis_data->'ensemble_result' for audit/debug.
ALTER TABLE public.ml_forecasts_intraday
ADD COLUMN IF NOT EXISTS synthesis_data JSONB;

COMMENT ON COLUMN public.ml_forecasts_intraday.synthesis_data IS
'Optional synthesis context: ensemble_result (label, confidence, xgb_prob, component_predictions, weights), etc.';

CREATE INDEX IF NOT EXISTS idx_ml_forecasts_intraday_synthesis_data
ON public.ml_forecasts_intraday USING GIN (synthesis_data)
WHERE synthesis_data IS NOT NULL;
