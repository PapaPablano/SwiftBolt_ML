ALTER TABLE public.forecast_evaluations
ADD COLUMN IF NOT EXISTS synth_supertrend_component numeric,
ADD COLUMN IF NOT EXISTS synth_polynomial_component numeric,
ADD COLUMN IF NOT EXISTS synth_ml_component numeric,
ADD COLUMN IF NOT EXISTS rf_weight numeric,
ADD COLUMN IF NOT EXISTS gb_weight numeric;

CREATE INDEX IF NOT EXISTS idx_forecast_eval_symbol_horizon_date
ON public.forecast_evaluations(symbol, horizon, evaluation_date DESC);
