-- Adaptive SuperTrend integration columns

ALTER TABLE public.indicator_values
  ADD COLUMN IF NOT EXISTS supertrend_distance_pct double precision,
  ADD COLUMN IF NOT EXISTS supertrend_metrics jsonb;

-- Optional index to speed filtering by adaptive factor
CREATE INDEX IF NOT EXISTS idx_indicator_values_supertrend_factor
  ON public.indicator_values(symbol_id, timeframe, ts)
  WHERE supertrend_factor IS NOT NULL;

-- Extend ml_forecasts with adaptive consensus (idempotent)
ALTER TABLE public.ml_forecasts
  ADD COLUMN IF NOT EXISTS adaptive_supertrend_consensus double precision,
  ADD COLUMN IF NOT EXISTS adaptive_supertrend_confidence double precision;
