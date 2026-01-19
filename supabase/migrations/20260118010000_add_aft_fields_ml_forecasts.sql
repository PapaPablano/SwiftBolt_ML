-- Migration: Add AFT ensemble metadata fields to ml_forecasts

ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS model_predictions jsonb,
ADD COLUMN IF NOT EXISTS model_confidences jsonb,
ADD COLUMN IF NOT EXISTS ensemble_method text,
ADD COLUMN IF NOT EXISTS ensemble_weights jsonb,
ADD COLUMN IF NOT EXISTS confidence_source text;

COMMENT ON COLUMN ml_forecasts.model_predictions IS
'Per-model prediction outputs (e.g. {"prophet": 125.3, "xgboost": 125.5})';

COMMENT ON COLUMN ml_forecasts.model_confidences IS
'Per-model confidence scores (0-1) for ensemble transparency.';

COMMENT ON COLUMN ml_forecasts.ensemble_method IS
'Ensemble method used (weighted_vote, stacking, kalman).';

COMMENT ON COLUMN ml_forecasts.ensemble_weights IS
'Per-model weights applied to the ensemble.';

COMMENT ON COLUMN ml_forecasts.confidence_source IS
'Whether confidence is derived from ensemble or single model.';

CREATE INDEX IF NOT EXISTS idx_ml_forecasts_symbol_horizon_run_at
ON ml_forecasts(symbol_id, horizon, run_at DESC);

CREATE INDEX IF NOT EXISTS idx_ml_forecasts_symbol_ensemble_method
ON ml_forecasts(symbol_id, ensemble_method)
WHERE ensemble_method IS NOT NULL;
