-- Migration: Denormalized view for latest forecast summary

CREATE OR REPLACE VIEW latest_forecast_summary AS
SELECT
  f.symbol_id,
  s.ticker,
  f.horizon,
  f.overall_label,
  f.confidence,
  f.run_at,
  f.points
FROM ml_forecasts f
JOIN symbols s ON s.id = f.symbol_id
WHERE f.run_at = (
  SELECT MAX(f2.run_at)
  FROM ml_forecasts f2
  WHERE f2.symbol_id = f.symbol_id
);

CREATE INDEX IF NOT EXISTS idx_latest_forecast_summary_symbol
ON ml_forecasts(symbol_id, run_at DESC);
