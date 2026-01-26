-- Add SuperTrend AI feature columns to indicator_values
-- Generated: 2026-01-26

ALTER TABLE public.indicator_values
  ADD COLUMN IF NOT EXISTS supertrend_performance_index DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS supertrend_signal_strength INTEGER,
  ADD COLUMN IF NOT EXISTS signal_confidence INTEGER,
  ADD COLUMN IF NOT EXISTS supertrend_confidence_norm DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS supertrend_distance_norm DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS perf_ama DOUBLE PRECISION;

-- Optional index to speed high-confidence SuperTrend scans
CREATE INDEX IF NOT EXISTS idx_indicator_supertrend_signals
  ON public.indicator_values(symbol_id, timeframe, ts)
  WHERE signal_confidence > 7;
