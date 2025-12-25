-- Migration: Add Support/Resistance data to ml_forecasts table
-- Date: 2024-12-25
-- Description: Adds columns for S/R levels and density to enhance forecast quality

-- Add S/R columns to ml_forecasts table
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS sr_levels JSONB,
ADD COLUMN IF NOT EXISTS sr_density INTEGER;

-- Add comments for documentation
COMMENT ON COLUMN ml_forecasts.sr_levels IS
    'Support/Resistance levels dict: {nearest_support, nearest_resistance, support_distance_pct, resistance_distance_pct, all_supports[], all_resistances[]}';
COMMENT ON COLUMN ml_forecasts.sr_density IS
    'Number of S/R levels within 5% of current price (indicates congestion zones)';

-- Create index for querying high S/R density zones
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_sr_density
ON ml_forecasts(sr_density)
WHERE sr_density IS NOT NULL AND sr_density >= 3;
