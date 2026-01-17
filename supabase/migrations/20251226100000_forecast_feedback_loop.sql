-- Migration: ML Forecast Feedback Loop
-- Date: 2024-12-26
-- Description: Adds tables and functions for tracking forecast outcomes and automatic model tuning

-- ============================================================================
-- 1. FORECAST EVALUATIONS TABLE
-- Tracks how accurate each forecast was after the fact
-- ============================================================================

CREATE TABLE IF NOT EXISTS forecast_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    forecast_id UUID REFERENCES ml_forecasts(id) ON DELETE CASCADE,
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,  -- '1D', '1W', '1M'

    -- What we predicted
    predicted_label TEXT NOT NULL,  -- 'bullish', 'neutral', 'bearish'
    predicted_value NUMERIC NOT NULL,  -- Target price
    predicted_confidence NUMERIC NOT NULL,  -- 0-1
    forecast_date TIMESTAMPTZ NOT NULL,  -- When forecast was made

    -- What actually happened
    evaluation_date TIMESTAMPTZ NOT NULL,  -- When we evaluated
    realized_price NUMERIC NOT NULL,  -- Actual price at horizon end
    realized_return NUMERIC NOT NULL,  -- Percent change
    realized_label TEXT NOT NULL,  -- Actual direction

    -- Accuracy metrics
    direction_correct BOOLEAN NOT NULL,  -- Did we get direction right?
    price_error NUMERIC NOT NULL,  -- Absolute price error
    price_error_pct NUMERIC NOT NULL,  -- Percent error

    -- Model breakdown (for weight adjustment)
    rf_prediction TEXT,
    gb_prediction TEXT,
    rf_correct BOOLEAN,
    gb_correct BOOLEAN,
    model_agreement NUMERIC,  -- 0 or 1

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_forecast_eval_symbol ON forecast_evaluations(symbol);
CREATE INDEX IF NOT EXISTS idx_forecast_eval_horizon ON forecast_evaluations(horizon);
CREATE INDEX IF NOT EXISTS idx_forecast_eval_date ON forecast_evaluations(evaluation_date DESC);
CREATE INDEX IF NOT EXISTS idx_forecast_eval_direction ON forecast_evaluations(direction_correct);

COMMENT ON TABLE forecast_evaluations IS 'Tracks forecast accuracy by comparing predictions to actual outcomes';

-- ============================================================================
-- 2. MODEL PERFORMANCE HISTORY TABLE
-- Tracks model accuracy over time for weight adjustment
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_performance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_date DATE NOT NULL,
    horizon TEXT NOT NULL,

    -- Overall accuracy
    total_forecasts INT NOT NULL,
    correct_forecasts INT NOT NULL,
    accuracy NUMERIC NOT NULL,  -- 0-1

    -- Per-model accuracy
    rf_accuracy NUMERIC,
    gb_accuracy NUMERIC,
    ensemble_accuracy NUMERIC,

    -- Current weights (for tracking)
    rf_weight NUMERIC NOT NULL DEFAULT 0.5,
    gb_weight NUMERIC NOT NULL DEFAULT 0.5,

    -- Recommended weights (computed from performance)
    recommended_rf_weight NUMERIC,
    recommended_gb_weight NUMERIC,

    -- Error metrics
    avg_price_error_pct NUMERIC,
    max_price_error_pct NUMERIC,

    -- By direction
    bullish_accuracy NUMERIC,
    bearish_accuracy NUMERIC,
    neutral_accuracy NUMERIC,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(evaluation_date, horizon)
);

CREATE INDEX IF NOT EXISTS idx_model_perf_date ON model_performance_history(evaluation_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_perf_horizon ON model_performance_history(horizon);

COMMENT ON TABLE model_performance_history IS 'Daily summary of model performance for weight optimization';

-- ============================================================================
-- 3. ACTIVE MODEL WEIGHTS TABLE
-- Stores current model weights (updated by feedback loop)
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon TEXT NOT NULL UNIQUE,
    rf_weight NUMERIC NOT NULL DEFAULT 0.5,
    gb_weight NUMERIC NOT NULL DEFAULT 0.5,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    update_reason TEXT,  -- 'initial', 'performance_adjustment', 'manual_override'

    -- Performance that triggered update
    rf_accuracy_30d NUMERIC,
    gb_accuracy_30d NUMERIC,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize default weights
INSERT INTO model_weights (horizon, rf_weight, gb_weight, update_reason)
VALUES
    ('1D', 0.5, 0.5, 'initial'),
    ('1W', 0.5, 0.5, 'initial'),
    ('1M', 0.5, 0.5, 'initial')
ON CONFLICT (horizon) DO NOTHING;

COMMENT ON TABLE model_weights IS 'Current ensemble weights, automatically adjusted based on performance';

-- ============================================================================
-- 4. FUNCTIONS FOR EVALUATION
-- ============================================================================

-- Function to get forecasts pending evaluation
CREATE OR REPLACE FUNCTION get_pending_evaluations(p_horizon TEXT DEFAULT '1D')
RETURNS TABLE (
    forecast_id UUID,
    symbol_id UUID,
    symbol TEXT,
    horizon TEXT,
    overall_label TEXT,
    confidence NUMERIC,
    points JSONB,
    created_at TIMESTAMPTZ,
    evaluation_due TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id as forecast_id,
        f.symbol_id,
        s.ticker as symbol,
        f.horizon,
        f.overall_label,
        f.confidence,
        f.points,
        f.created_at,
        CASE
            WHEN f.horizon = '1D' THEN f.created_at + INTERVAL '1 day'
            WHEN f.horizon = '1W' THEN f.created_at + INTERVAL '5 days'
            WHEN f.horizon = '1M' THEN f.created_at + INTERVAL '20 days'
            ELSE f.created_at + INTERVAL '1 day'
        END as evaluation_due
    FROM ml_forecasts f
    JOIN symbols s ON f.symbol_id = s.id
    WHERE f.horizon = p_horizon
    AND f.created_at < NOW() - (
        CASE
            WHEN f.horizon = '1D' THEN INTERVAL '1 day'
            WHEN f.horizon = '1W' THEN INTERVAL '5 days'
            WHEN f.horizon = '1M' THEN INTERVAL '20 days'
            ELSE INTERVAL '1 day'
        END
    )
    AND NOT EXISTS (
        SELECT 1 FROM forecast_evaluations e
        WHERE e.forecast_id = f.id
    )
    ORDER BY f.created_at ASC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

-- Function to compute and update model weights based on 30-day performance
CREATE OR REPLACE FUNCTION update_model_weights()
RETURNS TABLE (
    horizon TEXT,
    old_rf_weight NUMERIC,
    old_gb_weight NUMERIC,
    new_rf_weight NUMERIC,
    new_gb_weight NUMERIC,
    rf_accuracy NUMERIC,
    gb_accuracy NUMERIC
) AS $$
DECLARE
    rec RECORD;
    min_samples INT := 20;  -- Minimum evaluations needed
    smoothing NUMERIC := 0.3;  -- Weight adjustment smoothing factor
BEGIN
    FOR rec IN
        SELECT DISTINCT e.horizon
        FROM forecast_evaluations e
        WHERE e.evaluation_date >= NOW() - INTERVAL '30 days'
    LOOP
        -- Calculate 30-day accuracy per model
        WITH model_stats AS (
            SELECT
                e.horizon,
                COUNT(*) as total,
                AVG(CASE WHEN e.rf_correct THEN 1.0 ELSE 0.0 END) as rf_acc,
                AVG(CASE WHEN e.gb_correct THEN 1.0 ELSE 0.0 END) as gb_acc
            FROM forecast_evaluations e
            WHERE e.horizon = rec.horizon
            AND e.evaluation_date >= NOW() - INTERVAL '30 days'
            AND e.rf_correct IS NOT NULL
            AND e.gb_correct IS NOT NULL
            GROUP BY e.horizon
            HAVING COUNT(*) >= min_samples
        )
        UPDATE model_weights w
        SET
            rf_weight = ROUND(
                w.rf_weight * (1 - smoothing) +
                (ms.rf_acc / NULLIF(ms.rf_acc + ms.gb_acc, 0)) * smoothing,
                3
            ),
            gb_weight = ROUND(
                w.gb_weight * (1 - smoothing) +
                (ms.gb_acc / NULLIF(ms.rf_acc + ms.gb_acc, 0)) * smoothing,
                3
            ),
            rf_accuracy_30d = ms.rf_acc,
            gb_accuracy_30d = ms.gb_acc,
            last_updated = NOW(),
            update_reason = 'performance_adjustment'
        FROM model_stats ms
        WHERE w.horizon = rec.horizon
        AND w.horizon = ms.horizon
        RETURNING
            w.horizon,
            w.rf_weight as old_rf,
            w.gb_weight as old_gb,
            w.rf_weight as new_rf,
            w.gb_weight as new_gb,
            ms.rf_acc,
            ms.gb_acc
        INTO horizon, old_rf_weight, old_gb_weight, new_rf_weight, new_gb_weight, rf_accuracy, gb_accuracy;

        IF FOUND THEN
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to get current model weights
CREATE OR REPLACE FUNCTION get_model_weights(p_horizon TEXT)
RETURNS TABLE (rf_weight NUMERIC, gb_weight NUMERIC) AS $$
BEGIN
    RETURN QUERY
    SELECT w.rf_weight, w.gb_weight
    FROM model_weights w
    WHERE w.horizon = p_horizon;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. DASHBOARD VIEWS
-- ============================================================================

-- View: Recent forecast accuracy summary
CREATE OR REPLACE VIEW v_forecast_accuracy_summary AS
SELECT
    horizon,
    COUNT(*) as total_evaluations,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct,
    ROUND(AVG(price_error_pct), 2) as avg_error_pct,
    ROUND(AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as rf_accuracy_pct,
    ROUND(AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as gb_accuracy_pct,
    MAX(evaluation_date) as last_evaluation
FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY horizon
ORDER BY horizon;

-- View: Accuracy by symbol (last 30 days)
CREATE OR REPLACE VIEW v_symbol_accuracy AS
SELECT
    symbol,
    horizon,
    COUNT(*) as forecasts,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct,
    ROUND(AVG(price_error_pct), 2) as avg_error_pct
FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY symbol, horizon
ORDER BY accuracy_pct DESC;

-- View: Model weights with performance
CREATE OR REPLACE VIEW v_model_weights_dashboard AS
SELECT
    w.horizon,
    ROUND(w.rf_weight * 100, 1) as rf_weight_pct,
    ROUND(w.gb_weight * 100, 1) as gb_weight_pct,
    ROUND(w.rf_accuracy_30d * 100, 1) as rf_accuracy_30d_pct,
    ROUND(w.gb_accuracy_30d * 100, 1) as gb_accuracy_30d_pct,
    w.last_updated,
    w.update_reason
FROM model_weights w
ORDER BY w.horizon;

-- View: Daily accuracy trend
CREATE OR REPLACE VIEW v_daily_accuracy_trend AS
SELECT
    DATE(evaluation_date) as eval_date,
    horizon,
    COUNT(*) as forecasts,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct
FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY DATE(evaluation_date), horizon
ORDER BY eval_date DESC, horizon;

-- ============================================================================
-- 6. RPC FUNCTIONS FOR SUPABASE DASHBOARD
-- ============================================================================

-- RPC: Get ML performance dashboard data
CREATE OR REPLACE FUNCTION get_ml_dashboard()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'accuracy_summary', (SELECT json_agg(row_to_json(t)) FROM v_forecast_accuracy_summary t),
        'model_weights', (SELECT json_agg(row_to_json(t)) FROM v_model_weights_dashboard t),
        'daily_trend', (SELECT json_agg(row_to_json(t)) FROM v_daily_accuracy_trend t LIMIT 30),
        'top_symbols', (
            SELECT json_agg(row_to_json(t))
            FROM (SELECT * FROM v_symbol_accuracy ORDER BY accuracy_pct DESC LIMIT 10) t
        ),
        'worst_symbols', (
            SELECT json_agg(row_to_json(t))
            FROM (SELECT * FROM v_symbol_accuracy ORDER BY accuracy_pct ASC LIMIT 10) t
        ),
        'pending_evaluations', (
            SELECT COUNT(*) FROM get_pending_evaluations('1D')
        ),
        'last_updated', NOW()
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- RPC: Trigger model weight update
CREATE OR REPLACE FUNCTION trigger_weight_update()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_agg(row_to_json(t))
    FROM update_model_weights() t
    INTO result;

    RETURN json_build_object(
        'updated', result IS NOT NULL,
        'weights', result,
        'timestamp', NOW()
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_ml_dashboard() IS 'Returns comprehensive ML performance dashboard data';
COMMENT ON FUNCTION trigger_weight_update() IS 'Recalculates and updates model weights based on recent performance';
