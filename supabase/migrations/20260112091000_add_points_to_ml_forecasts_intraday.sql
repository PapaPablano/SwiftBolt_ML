-- Add points series to intraday forecasts for chart rendering parity.
-- Object schema is app-level: each array element is a ForecastPoint (see docs/master_blueprint.md
-- "Canonical Forecast Point Schema (points JSONB)"). Required: ts, value; optional: lower, upper,
-- timeframe, step, ohlc, indicators, confidence, components, weights.

ALTER TABLE ml_forecasts_intraday
ADD COLUMN IF NOT EXISTS points JSONB;
