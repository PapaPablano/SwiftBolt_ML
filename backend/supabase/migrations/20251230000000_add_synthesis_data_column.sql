-- Migration: Add synthesis_data column to ml_forecasts table
-- Date: 2024-12-30
-- Description: Adds column for 3-layer forecast synthesis metadata

-- Add synthesis_data column to ml_forecasts table
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS synthesis_data JSONB;

-- Add comment for documentation
COMMENT ON COLUMN ml_forecasts.synthesis_data IS
    '3-layer forecast synthesis data: {target, upper_band, lower_band, layers_agreeing, reasoning, key_drivers, supertrend_component, polynomial_component, ml_component}';

-- Create GIN index for querying synthesis_data
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_synthesis_data
ON ml_forecasts USING GIN (synthesis_data)
WHERE synthesis_data IS NOT NULL;
