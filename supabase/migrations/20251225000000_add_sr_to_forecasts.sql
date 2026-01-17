-- Migration: Add Support/Resistance data and quality metrics to ml_forecasts table
-- Date: 2024-12-25
-- Description: Adds columns for S/R levels, density, and forecast quality metrics

-- Add S/R columns to ml_forecasts table
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS sr_levels JSONB,
ADD COLUMN IF NOT EXISTS sr_density INTEGER,
ADD COLUMN IF NOT EXISTS model_agreement DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS quality_issues JSONB,
ADD COLUMN IF NOT EXISTS backtest_metrics JSONB,
ADD COLUMN IF NOT EXISTS training_stats JSONB;

-- Add comments for documentation
COMMENT ON COLUMN ml_forecasts.sr_levels IS
    'Support/Resistance levels dict: {nearest_support, nearest_resistance, support_distance_pct, resistance_distance_pct, all_supports[], all_resistances[]}';
COMMENT ON COLUMN ml_forecasts.sr_density IS
    'Number of S/R levels within 5% of current price (indicates congestion zones)';
COMMENT ON COLUMN ml_forecasts.model_agreement IS
    'Agreement score between RF and GB models (0-1, higher = more agreement)';
COMMENT ON COLUMN ml_forecasts.quality_score IS
    'Overall forecast quality score (0-1)';
COMMENT ON COLUMN ml_forecasts.quality_issues IS
    'Array of quality issues/warnings detected';
COMMENT ON COLUMN ml_forecasts.backtest_metrics IS
    'Walk-forward backtest performance metrics';
COMMENT ON COLUMN ml_forecasts.training_stats IS
    'Model training statistics and metrics';

-- Create index for querying high S/R density zones
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_sr_density
ON ml_forecasts(sr_density)
WHERE sr_density IS NOT NULL AND sr_density >= 3;

-- Create index for quality filtering
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_quality_score
ON ml_forecasts(quality_score DESC)
WHERE quality_score IS NOT NULL;
