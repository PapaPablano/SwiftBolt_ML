-- Migration: Add Enhanced Ensemble Fields to ml_forecasts
-- Date: 2026-01-03
-- Description: Adds model_agreement, ensemble_type, and training_stats for 5-model ensemble

-- ============================================================================
-- 1. ADD ENHANCED ENSEMBLE COLUMNS TO ml_forecasts
-- ============================================================================

DO $$
BEGIN
    -- Ensemble type (RF+GB for basic, Enhanced5 for 5-model)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'ensemble_type') THEN
        ALTER TABLE ml_forecasts ADD COLUMN ensemble_type VARCHAR(20) DEFAULT 'RF+GB';
    END IF;

    -- Model agreement (0-1, how much models agree on direction)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'model_agreement') THEN
        ALTER TABLE ml_forecasts ADD COLUMN model_agreement NUMERIC(4, 3);
    END IF;

    -- Training stats (JSON with weights, component predictions, etc.)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'training_stats') THEN
        ALTER TABLE ml_forecasts ADD COLUMN training_stats JSONB DEFAULT '{}'::jsonb;
    END IF;

    -- Number of models used
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'n_models') THEN
        ALTER TABLE ml_forecasts ADD COLUMN n_models INTEGER DEFAULT 2;
    END IF;

    -- Forecast return (expected % return)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'forecast_return') THEN
        ALTER TABLE ml_forecasts ADD COLUMN forecast_return NUMERIC(6, 4);
    END IF;

    -- Forecast volatility
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'forecast_volatility') THEN
        ALTER TABLE ml_forecasts ADD COLUMN forecast_volatility NUMERIC(6, 4);
    END IF;

    -- Confidence interval lower bound
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'ci_lower') THEN
        ALTER TABLE ml_forecasts ADD COLUMN ci_lower NUMERIC(6, 4);
    END IF;

    -- Confidence interval upper bound
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'ci_upper') THEN
        ALTER TABLE ml_forecasts ADD COLUMN ci_upper NUMERIC(6, 4);
    END IF;
END $$;

-- ============================================================================
-- 2. INDEX FOR ENSEMBLE QUERIES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_ml_forecasts_ensemble_type
    ON ml_forecasts(ensemble_type);

CREATE INDEX IF NOT EXISTS idx_ml_forecasts_model_agreement
    ON ml_forecasts(model_agreement DESC NULLS LAST);

-- ============================================================================
-- 3. FUNCTION TO GET LATEST FORECAST FOR OPTIONS RANKING
-- ============================================================================

CREATE OR REPLACE FUNCTION get_forecast_for_options(
    p_symbol TEXT,
    p_horizon TEXT DEFAULT '1D'
)
RETURNS TABLE (
    forecast_id UUID,
    overall_label TEXT,
    confidence NUMERIC,
    ensemble_type VARCHAR,
    model_agreement NUMERIC,
    forecast_return NUMERIC,
    forecast_volatility NUMERIC,
    n_models INTEGER,
    forecast_age_hours NUMERIC,
    is_fresh BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id as forecast_id,
        f.overall_label,
        f.confidence,
        f.ensemble_type,
        f.model_agreement,
        f.forecast_return,
        f.forecast_volatility,
        f.n_models,
        EXTRACT(EPOCH FROM (NOW() - f.run_at)) / 3600 as forecast_age_hours,
        (NOW() - f.run_at) < INTERVAL '24 hours' as is_fresh
    FROM ml_forecasts f
    JOIN symbols s ON f.symbol_id = s.id
    WHERE s.ticker = p_symbol
      AND f.horizon = p_horizon
    ORDER BY f.run_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 4. COMMENTS
-- ============================================================================

COMMENT ON COLUMN ml_forecasts.ensemble_type IS 'Ensemble architecture: RF+GB (basic) or Enhanced5 (5-model)';
COMMENT ON COLUMN ml_forecasts.model_agreement IS 'How much models agree on prediction (0-1)';
COMMENT ON COLUMN ml_forecasts.training_stats IS 'JSON with model weights, component predictions, training time';
COMMENT ON COLUMN ml_forecasts.n_models IS 'Number of models in the ensemble';
COMMENT ON COLUMN ml_forecasts.forecast_return IS 'Expected return as decimal (e.g., 0.015 = 1.5%)';
COMMENT ON COLUMN ml_forecasts.forecast_volatility IS 'Forecast volatility as decimal';
COMMENT ON COLUMN ml_forecasts.ci_lower IS 'Lower bound of 95% confidence interval';
COMMENT ON COLUMN ml_forecasts.ci_upper IS 'Upper bound of 95% confidence interval';
COMMENT ON FUNCTION get_forecast_for_options IS 'Get latest forecast for a symbol to use in options ranking';
