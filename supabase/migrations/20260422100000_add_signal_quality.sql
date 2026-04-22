-- Add signal quality score columns to forecast tables
ALTER TABLE ml_forecasts ADD COLUMN IF NOT EXISTS signal_quality INTEGER;
ALTER TABLE ml_forecasts ADD COLUMN IF NOT EXISTS calibration_label VARCHAR(20);
ALTER TABLE ml_forecasts ADD COLUMN IF NOT EXISTS accuracy_pct NUMERIC(5,2);

ALTER TABLE ml_forecasts_intraday ADD COLUMN IF NOT EXISTS signal_quality INTEGER;
ALTER TABLE ml_forecasts_intraday ADD COLUMN IF NOT EXISTS calibration_label VARCHAR(20);
ALTER TABLE ml_forecasts_intraday ADD COLUMN IF NOT EXISTS accuracy_pct NUMERIC(5,2);
