-- Advanced S/R Features Migration
-- Phase 1: Volume-based strength metrics
-- Phase 2: Hold probability predictions
-- Phase 3: Polynomial regression features
--
-- This migration adds columns to support the advanced S/R integration strategy
-- for improved ML forecasting accuracy.

-- ============================================================================
-- Phase 1: Volume-Based S/R Strength Columns
-- ============================================================================

-- Add volume strength columns to sr_levels table
ALTER TABLE sr_levels
ADD COLUMN IF NOT EXISTS support_volume_strength NUMERIC(5, 2),
ADD COLUMN IF NOT EXISTS resistance_volume_strength NUMERIC(5, 2),
ADD COLUMN IF NOT EXISTS support_touches_count INTEGER,
ADD COLUMN IF NOT EXISTS resistance_touches_count INTEGER,
ADD COLUMN IF NOT EXISTS support_strength_score NUMERIC(5, 2),
ADD COLUMN IF NOT EXISTS resistance_strength_score NUMERIC(5, 2);

-- Add comments for documentation
COMMENT ON COLUMN sr_levels.support_volume_strength IS
    'Volume-weighted strength of nearest support (0-100)';
COMMENT ON COLUMN sr_levels.resistance_volume_strength IS
    'Volume-weighted strength of nearest resistance (0-100)';
COMMENT ON COLUMN sr_levels.support_touches_count IS
    'Number of times price touched the support level';
COMMENT ON COLUMN sr_levels.resistance_touches_count IS
    'Number of times price touched the resistance level';
COMMENT ON COLUMN sr_levels.support_strength_score IS
    'Composite strength score combining volume, touches, and distance (0-100)';
COMMENT ON COLUMN sr_levels.resistance_strength_score IS
    'Composite strength score combining volume, touches, and distance (0-100)';

-- ============================================================================
-- Phase 2: S/R Hold Probability Columns
-- ============================================================================

ALTER TABLE sr_levels
ADD COLUMN IF NOT EXISTS support_hold_probability NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS resistance_hold_probability NUMERIC(5, 4);

COMMENT ON COLUMN sr_levels.support_hold_probability IS
    'ML-predicted probability (0-1) that support level will hold';
COMMENT ON COLUMN sr_levels.resistance_hold_probability IS
    'ML-predicted probability (0-1) that resistance level will hold';

-- ============================================================================
-- Phase 3: Polynomial S/R Regression Columns
-- ============================================================================

ALTER TABLE sr_levels
ADD COLUMN IF NOT EXISTS polynomial_support NUMERIC(20, 6),
ADD COLUMN IF NOT EXISTS polynomial_resistance NUMERIC(20, 6),
ADD COLUMN IF NOT EXISTS support_slope NUMERIC(10, 6),
ADD COLUMN IF NOT EXISTS resistance_slope NUMERIC(10, 6);

COMMENT ON COLUMN sr_levels.polynomial_support IS
    'Dynamic support level from polynomial regression at current bar';
COMMENT ON COLUMN sr_levels.polynomial_resistance IS
    'Dynamic resistance level from polynomial regression at current bar';
COMMENT ON COLUMN sr_levels.support_slope IS
    'Trend direction of support (positive=rising, negative=falling)';
COMMENT ON COLUMN sr_levels.resistance_slope IS
    'Trend direction of resistance (positive=rising, negative=falling)';

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Index for querying by strength scores
CREATE INDEX IF NOT EXISTS idx_sr_levels_support_strength
    ON sr_levels (support_strength_score DESC)
    WHERE support_strength_score IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sr_levels_resistance_strength
    ON sr_levels (resistance_strength_score DESC)
    WHERE resistance_strength_score IS NOT NULL;

-- Index for querying by hold probability
CREATE INDEX IF NOT EXISTS idx_sr_levels_support_hold_prob
    ON sr_levels (support_hold_probability DESC)
    WHERE support_hold_probability IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sr_levels_resistance_hold_prob
    ON sr_levels (resistance_hold_probability DESC)
    WHERE resistance_hold_probability IS NOT NULL;

-- ============================================================================
-- Add columns to ml_forecasts table for S/R probability metadata
-- ============================================================================

ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS support_hold_probability NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS resistance_hold_probability NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS support_strength_score NUMERIC(5, 2),
ADD COLUMN IF NOT EXISTS resistance_strength_score NUMERIC(5, 2);

COMMENT ON COLUMN ml_forecasts.support_hold_probability IS
    'ML-predicted probability that support will hold (from forecast job)';
COMMENT ON COLUMN ml_forecasts.resistance_hold_probability IS
    'ML-predicted probability that resistance will hold (from forecast job)';
COMMENT ON COLUMN ml_forecasts.support_strength_score IS
    'Composite support strength score used for confidence adjustment';
COMMENT ON COLUMN ml_forecasts.resistance_strength_score IS
    'Composite resistance strength score used for confidence adjustment';
