-- Intraday Weight Calibration System
-- Uses 15min and 1hr forecasts to rapidly calibrate layer weights

-- Table for storing intraday forecasts
CREATE TABLE IF NOT EXISTS ml_forecasts_intraday (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    horizon VARCHAR(10) NOT NULL, -- '15m', '1h'
    timeframe VARCHAR(10) NOT NULL, -- 'm15', 'h1'
    overall_label VARCHAR(20),
    confidence NUMERIC(5,4),
    target_price NUMERIC(12,4),
    current_price NUMERIC(12,4),
    -- Component breakdown for weight learning
    supertrend_component NUMERIC(12,4),
    sr_component NUMERIC(12,4),
    ensemble_component NUMERIC(12,4),
    -- Additional metadata
    supertrend_direction VARCHAR(20), -- 'BULLISH', 'BEARISH', 'NEUTRAL'
    ensemble_label VARCHAR(20),
    layers_agreeing INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT unique_intraday_forecast UNIQUE (symbol_id, horizon, created_at)
);

-- Table for storing intraday forecast evaluations
CREATE TABLE IF NOT EXISTS ml_forecast_evaluations_intraday (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID NOT NULL REFERENCES ml_forecasts_intraday(id) ON DELETE CASCADE,
    symbol_id UUID NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    horizon VARCHAR(10) NOT NULL,
    -- Predictions
    predicted_label VARCHAR(20),
    predicted_price NUMERIC(12,4),
    predicted_confidence NUMERIC(5,4),
    -- Actuals
    realized_price NUMERIC(12,4),
    realized_return NUMERIC(8,6),
    realized_label VARCHAR(20),
    -- Accuracy metrics
    direction_correct BOOLEAN,
    price_error NUMERIC(12,4),
    price_error_pct NUMERIC(8,6),
    -- Per-component accuracy for weight learning
    supertrend_direction_correct BOOLEAN,
    sr_containment BOOLEAN, -- Was price within S/R predicted range?
    ensemble_direction_correct BOOLEAN,
    -- Timestamps
    forecast_created_at TIMESTAMPTZ,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add calibration metadata to symbol_model_weights if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'symbol_model_weights' AND column_name = 'calibration_source'
    ) THEN
        ALTER TABLE symbol_model_weights
        ADD COLUMN calibration_source VARCHAR(50) DEFAULT 'daily';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'symbol_model_weights' AND column_name = 'intraday_sample_count'
    ) THEN
        ALTER TABLE symbol_model_weights
        ADD COLUMN intraday_sample_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'symbol_model_weights' AND column_name = 'intraday_accuracy'
    ) THEN
        ALTER TABLE symbol_model_weights
        ADD COLUMN intraday_accuracy NUMERIC(5,4);
    END IF;
END $$;

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_intraday_forecasts_symbol_expires
ON ml_forecasts_intraday(symbol_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_intraday_forecasts_expires
ON ml_forecasts_intraday(expires_at);

CREATE INDEX IF NOT EXISTS idx_intraday_evals_symbol_horizon
ON ml_forecast_evaluations_intraday(symbol_id, horizon, evaluated_at);

CREATE INDEX IF NOT EXISTS idx_intraday_evals_evaluated_at
ON ml_forecast_evaluations_intraday(evaluated_at);

-- Function to get pending intraday forecasts for evaluation
CREATE OR REPLACE FUNCTION get_pending_intraday_evaluations(p_horizon VARCHAR DEFAULT NULL)
RETURNS TABLE (
    forecast_id UUID,
    symbol_id UUID,
    symbol VARCHAR,
    horizon VARCHAR,
    overall_label VARCHAR,
    target_price NUMERIC,
    current_price NUMERIC,
    supertrend_component NUMERIC,
    sr_component NUMERIC,
    ensemble_component NUMERIC,
    supertrend_direction VARCHAR,
    ensemble_label VARCHAR,
    created_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id AS forecast_id,
        f.symbol_id,
        f.symbol,
        f.horizon,
        f.overall_label,
        f.target_price,
        f.current_price,
        f.supertrend_component,
        f.sr_component,
        f.ensemble_component,
        f.supertrend_direction,
        f.ensemble_label,
        f.created_at,
        f.expires_at
    FROM ml_forecasts_intraday f
    WHERE f.expires_at <= NOW()
    AND NOT EXISTS (
        SELECT 1 FROM ml_forecast_evaluations_intraday e
        WHERE e.forecast_id = f.id
    )
    AND (p_horizon IS NULL OR f.horizon = p_horizon)
    ORDER BY f.expires_at ASC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function to get intraday evaluation stats for weight calibration
CREATE OR REPLACE FUNCTION get_intraday_calibration_data(
    p_symbol_id UUID,
    p_lookback_hours INTEGER DEFAULT 72
)
RETURNS TABLE (
    horizon VARCHAR,
    total_forecasts BIGINT,
    direction_accuracy NUMERIC,
    avg_price_error_pct NUMERIC,
    supertrend_accuracy NUMERIC,
    sr_containment_rate NUMERIC,
    ensemble_accuracy NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.horizon,
        COUNT(*)::BIGINT AS total_forecasts,
        AVG(CASE WHEN e.direction_correct THEN 1.0 ELSE 0.0 END)::NUMERIC AS direction_accuracy,
        AVG(ABS(e.price_error_pct))::NUMERIC AS avg_price_error_pct,
        AVG(CASE WHEN e.supertrend_direction_correct THEN 1.0 ELSE 0.0 END)::NUMERIC AS supertrend_accuracy,
        AVG(CASE WHEN e.sr_containment THEN 1.0 ELSE 0.0 END)::NUMERIC AS sr_containment_rate,
        AVG(CASE WHEN e.ensemble_direction_correct THEN 1.0 ELSE 0.0 END)::NUMERIC AS ensemble_accuracy
    FROM ml_forecast_evaluations_intraday e
    WHERE e.symbol_id = p_symbol_id
    AND e.evaluated_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
    GROUP BY e.horizon;
END;
$$ LANGUAGE plpgsql;

-- Function to get raw evaluation data for weight optimization
CREATE OR REPLACE FUNCTION get_intraday_evaluations_for_calibration(
    p_symbol_id UUID,
    p_lookback_hours INTEGER DEFAULT 72
)
RETURNS TABLE (
    forecast_id UUID,
    horizon VARCHAR,
    predicted_price NUMERIC,
    realized_price NUMERIC,
    price_error_pct NUMERIC,
    direction_correct BOOLEAN,
    supertrend_component NUMERIC,
    sr_component NUMERIC,
    ensemble_component NUMERIC,
    supertrend_direction_correct BOOLEAN,
    sr_containment BOOLEAN,
    ensemble_direction_correct BOOLEAN,
    evaluated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.forecast_id,
        e.horizon,
        e.predicted_price,
        e.realized_price,
        e.price_error_pct,
        e.direction_correct,
        f.supertrend_component,
        f.sr_component,
        f.ensemble_component,
        e.supertrend_direction_correct,
        e.sr_containment,
        e.ensemble_direction_correct,
        e.evaluated_at
    FROM ml_forecast_evaluations_intraday e
    JOIN ml_forecasts_intraday f ON e.forecast_id = f.id
    WHERE e.symbol_id = p_symbol_id
    AND e.evaluated_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
    ORDER BY e.evaluated_at ASC;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old intraday data (keep 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_intraday_data()
RETURNS void AS $$
BEGIN
    -- Delete old evaluations first (FK constraint)
    DELETE FROM ml_forecast_evaluations_intraday
    WHERE evaluated_at < NOW() - INTERVAL '7 days';

    -- Delete old forecasts
    DELETE FROM ml_forecasts_intraday
    WHERE created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE ml_forecasts_intraday IS 'Short-term forecasts (15m, 1h) for weight calibration';
COMMENT ON TABLE ml_forecast_evaluations_intraday IS 'Evaluation results for intraday forecasts';
