-- Migration: Add missing quality metric columns to ml_forecasts table
-- Date: 2024-12-26
-- Description: Adds model_agreement, quality_score, quality_issues, backtest_metrics columns

-- Add missing columns to ml_forecasts table
ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS model_agreement DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS quality_issues JSONB,
ADD COLUMN IF NOT EXISTS backtest_metrics JSONB;

-- Add comments for documentation
COMMENT ON COLUMN ml_forecasts.model_agreement IS
    'Agreement score between RF and GB models (0-1, higher = more agreement)';
COMMENT ON COLUMN ml_forecasts.quality_score IS
    'Overall forecast quality score (0-1)';
COMMENT ON COLUMN ml_forecasts.quality_issues IS
    'Array of quality issues/warnings detected';
COMMENT ON COLUMN ml_forecasts.backtest_metrics IS
    'Walk-forward backtest performance metrics';

-- Create index for quality filtering
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_quality_score
ON ml_forecasts(quality_score DESC)
WHERE quality_score IS NOT NULL;
