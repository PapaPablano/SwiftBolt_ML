-- Add points series to intraday forecasts for chart rendering parity

ALTER TABLE ml_forecasts_intraday
ADD COLUMN IF NOT EXISTS points JSONB;
