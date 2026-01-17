-- Migration: Add ML Model Audit Trail
-- Tracks model versions and forecast changes over time for debugging and improvement

-- ============================================================================
-- ML Model Versions Table
-- ============================================================================
-- Stores snapshots of model configurations and performance metrics
CREATE TABLE IF NOT EXISTS ml_model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    model_type VARCHAR(50) NOT NULL,  -- 'ensemble', 'supertrend', 'sr', 'baseline'
    horizon VARCHAR(10),  -- '1D', '1W', '1M', etc.
    version_hash VARCHAR(64),  -- Hash of model parameters for deduplication
    parameters JSONB DEFAULT '{}'::jsonb,
    training_stats JSONB DEFAULT '{}'::jsonb,
    performance_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_model_versions_symbol
    ON ml_model_versions(symbol_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_type
    ON ml_model_versions(model_type);
CREATE INDEX IF NOT EXISTS idx_model_versions_created
    ON ml_model_versions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_versions_hash
    ON ml_model_versions(version_hash);

-- ============================================================================
-- ML Forecast Changes Table
-- ============================================================================
-- Tracks changes to forecasts (e.g., confidence adjustments, label changes)
CREATE TABLE IF NOT EXISTS ml_forecast_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID REFERENCES ml_forecasts(id) ON DELETE CASCADE,
    field_name VARCHAR(50) NOT NULL,  -- 'confidence', 'label', 'target', etc.
    old_value JSONB,
    new_value JSONB,
    change_reason VARCHAR(255),  -- 'calibration', 'staleness_penalty', etc.
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_forecast_changes_forecast
    ON ml_forecast_changes(forecast_id);
CREATE INDEX IF NOT EXISTS idx_forecast_changes_field
    ON ml_forecast_changes(field_name);
CREATE INDEX IF NOT EXISTS idx_forecast_changes_time
    ON ml_forecast_changes(changed_at DESC);

-- ============================================================================
-- ML Confidence Calibration Table
-- ============================================================================
-- Stores calibration factors for adjusting confidence scores
CREATE TABLE IF NOT EXISTS ml_confidence_calibration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon VARCHAR(10) NOT NULL,  -- '1D', '1W', '1M', etc.
    bucket_low DECIMAL(3, 2) NOT NULL,  -- 0.40, 0.50, etc.
    bucket_high DECIMAL(3, 2) NOT NULL,  -- 0.50, 0.60, etc.
    predicted_confidence DECIMAL(5, 4),  -- Average predicted
    actual_accuracy DECIMAL(5, 4),  -- Actual hit rate
    adjustment_factor DECIMAL(4, 3) DEFAULT 1.000,
    n_samples INTEGER DEFAULT 0,
    is_calibrated BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(horizon, bucket_low, bucket_high)
);

CREATE INDEX IF NOT EXISTS idx_calibration_horizon
    ON ml_confidence_calibration(horizon);

-- ============================================================================
-- ML Data Quality Log
-- ============================================================================
-- Logs data quality issues found by the validator
CREATE TABLE IF NOT EXISTS ml_data_quality_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    check_date DATE NOT NULL DEFAULT CURRENT_DATE,
    issues JSONB DEFAULT '[]'::jsonb,  -- Array of issue descriptions
    rows_flagged INTEGER DEFAULT 0,
    rows_removed INTEGER DEFAULT 0,
    quality_score DECIMAL(4, 3),  -- 0-1 score
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_quality_symbol
    ON ml_data_quality_log(symbol_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_date
    ON ml_data_quality_log(check_date DESC);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to log a model version
CREATE OR REPLACE FUNCTION log_model_version(
    p_symbol_id UUID,
    p_model_type VARCHAR,
    p_horizon VARCHAR,
    p_parameters JSONB,
    p_training_stats JSONB,
    p_performance_metrics JSONB
) RETURNS UUID AS $$
DECLARE
    v_hash VARCHAR(64);
    v_id UUID;
BEGIN
    -- Generate hash from parameters
    v_hash := encode(sha256(p_parameters::text::bytea), 'hex');

    INSERT INTO ml_model_versions (
        symbol_id, model_type, horizon, version_hash,
        parameters, training_stats, performance_metrics
    ) VALUES (
        p_symbol_id, p_model_type, p_horizon, v_hash,
        p_parameters, p_training_stats, p_performance_metrics
    )
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function to log a forecast change
CREATE OR REPLACE FUNCTION log_forecast_change(
    p_forecast_id UUID,
    p_field_name VARCHAR,
    p_old_value JSONB,
    p_new_value JSONB,
    p_reason VARCHAR
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO ml_forecast_changes (
        forecast_id, field_name, old_value, new_value, change_reason
    ) VALUES (
        p_forecast_id, p_field_name, p_old_value, p_new_value, p_reason
    )
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get model version history for a symbol
CREATE OR REPLACE FUNCTION get_model_history(
    p_symbol_id UUID,
    p_model_type VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    id UUID,
    model_type VARCHAR,
    horizon VARCHAR,
    version_hash VARCHAR,
    training_accuracy DECIMAL,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mv.id,
        mv.model_type,
        mv.horizon,
        mv.version_hash,
        (mv.training_stats->>'accuracy')::DECIMAL AS training_accuracy,
        mv.created_at
    FROM ml_model_versions mv
    WHERE mv.symbol_id = p_symbol_id
      AND (p_model_type IS NULL OR mv.model_type = p_model_type)
    ORDER BY mv.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE ml_model_versions IS
    'Audit trail for ML model versions and configurations';
COMMENT ON TABLE ml_forecast_changes IS
    'Log of changes made to forecasts (calibration, penalties, etc.)';
COMMENT ON TABLE ml_confidence_calibration IS
    'Calibration factors for adjusting confidence scores by bucket';
COMMENT ON TABLE ml_data_quality_log IS
    'Log of data quality issues found during validation';
