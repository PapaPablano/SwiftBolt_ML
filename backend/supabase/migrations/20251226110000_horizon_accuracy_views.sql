-- Migration: Enhanced Horizon-Specific Accuracy Views
-- Date: 2024-12-26
-- Description: Adds detailed views for tracking 1D vs 1W forecast accuracy

-- ============================================================================
-- 1. DETAILED HORIZON ACCURACY VIEW
-- Shows separate accuracy stats for Daily (1D) and Weekly (1W) forecasts
-- ============================================================================

CREATE OR REPLACE VIEW v_horizon_accuracy_detail AS
SELECT
    horizon,
    COUNT(*) as total_forecasts,
    SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct_forecasts,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct,
    ROUND(AVG(price_error_pct) * 100, 2) as avg_error_pct,
    ROUND(MAX(price_error_pct) * 100, 2) as max_error_pct,

    -- Accuracy by predicted direction
    ROUND(AVG(CASE WHEN predicted_label = 'bullish' AND direction_correct THEN 1.0
                   WHEN predicted_label = 'bullish' THEN 0.0 END) * 100, 1) as bullish_accuracy_pct,
    ROUND(AVG(CASE WHEN predicted_label = 'bearish' AND direction_correct THEN 1.0
                   WHEN predicted_label = 'bearish' THEN 0.0 END) * 100, 1) as bearish_accuracy_pct,
    ROUND(AVG(CASE WHEN predicted_label = 'neutral' AND direction_correct THEN 1.0
                   WHEN predicted_label = 'neutral' THEN 0.0 END) * 100, 1) as neutral_accuracy_pct,

    -- Model-specific accuracy
    ROUND(AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as rf_accuracy_pct,
    ROUND(AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as gb_accuracy_pct,

    -- Count by predicted direction
    SUM(CASE WHEN predicted_label = 'bullish' THEN 1 ELSE 0 END) as bullish_predictions,
    SUM(CASE WHEN predicted_label = 'bearish' THEN 1 ELSE 0 END) as bearish_predictions,
    SUM(CASE WHEN predicted_label = 'neutral' THEN 1 ELSE 0 END) as neutral_predictions,

    MIN(evaluation_date) as first_evaluation,
    MAX(evaluation_date) as last_evaluation
FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY horizon
ORDER BY
    CASE horizon
        WHEN '1D' THEN 1
        WHEN '1W' THEN 2
        WHEN '1M' THEN 3
        ELSE 4
    END;

COMMENT ON VIEW v_horizon_accuracy_detail IS 'Detailed accuracy breakdown by forecast horizon (1D vs 1W)';

-- ============================================================================
-- 2. ROLLING ACCURACY BY HORIZON
-- Track how accuracy changes over time for each horizon
-- ============================================================================

CREATE OR REPLACE VIEW v_rolling_accuracy_by_horizon AS
SELECT
    horizon,
    DATE(evaluation_date) as eval_date,
    COUNT(*) as forecasts_evaluated,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct,
    ROUND(AVG(price_error_pct) * 100, 2) as avg_error_pct,

    -- 7-day rolling accuracy
    ROUND(
        AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END)
        OVER (
            PARTITION BY horizon
            ORDER BY DATE(evaluation_date)
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) * 100, 1
    ) as accuracy_7d_rolling_pct,

    -- Cumulative accuracy
    ROUND(
        SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END)
        OVER (PARTITION BY horizon ORDER BY DATE(evaluation_date))::NUMERIC /
        NULLIF(COUNT(*) OVER (PARTITION BY horizon ORDER BY DATE(evaluation_date)), 0) * 100, 1
    ) as accuracy_cumulative_pct

FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY horizon, DATE(evaluation_date), direction_correct, price_error_pct, evaluation_date
ORDER BY horizon, eval_date DESC;

COMMENT ON VIEW v_rolling_accuracy_by_horizon IS 'Daily accuracy with 7-day rolling average by horizon';

-- ============================================================================
-- 3. SYMBOL ACCURACY BY HORIZON
-- Which symbols perform best for daily vs weekly predictions?
-- ============================================================================

CREATE OR REPLACE VIEW v_symbol_accuracy_by_horizon AS
SELECT
    symbol,
    horizon,
    COUNT(*) as total_forecasts,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_pct,
    ROUND(AVG(price_error_pct) * 100, 2) as avg_error_pct,

    -- Breakdown by direction
    ROUND(AVG(CASE WHEN predicted_label = 'bullish' AND direction_correct THEN 1.0
                   WHEN predicted_label = 'bullish' THEN 0.0 END) * 100, 1) as bullish_accuracy_pct,
    ROUND(AVG(CASE WHEN predicted_label = 'bearish' AND direction_correct THEN 1.0
                   WHEN predicted_label = 'bearish' THEN 0.0 END) * 100, 1) as bearish_accuracy_pct,

    MAX(evaluation_date) as last_evaluation
FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
GROUP BY symbol, horizon
HAVING COUNT(*) >= 3  -- At least 3 evaluations for meaningful stats
ORDER BY horizon, accuracy_pct DESC;

COMMENT ON VIEW v_symbol_accuracy_by_horizon IS 'Per-symbol accuracy breakdown for each forecast horizon';

-- ============================================================================
-- 4. MODEL WEIGHTS BY HORIZON
-- Track which model performs better for daily vs weekly predictions
-- ============================================================================

CREATE OR REPLACE VIEW v_model_comparison_by_horizon AS
SELECT
    horizon,
    COUNT(*) as total_evaluations,

    -- RF performance
    ROUND(AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as rf_accuracy_pct,
    SUM(CASE WHEN rf_correct THEN 1 ELSE 0 END) as rf_correct_count,

    -- GB performance
    ROUND(AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as gb_accuracy_pct,
    SUM(CASE WHEN gb_correct THEN 1 ELSE 0 END) as gb_correct_count,

    -- Agreement analysis
    ROUND(AVG(model_agreement) * 100, 1) as agreement_pct,
    ROUND(
        AVG(CASE WHEN model_agreement = 1 AND direction_correct THEN 1.0
                 WHEN model_agreement = 1 THEN 0.0 END) * 100, 1
    ) as accuracy_when_agree_pct,
    ROUND(
        AVG(CASE WHEN model_agreement = 0 AND direction_correct THEN 1.0
                 WHEN model_agreement = 0 THEN 0.0 END) * 100, 1
    ) as accuracy_when_disagree_pct,

    -- Recommended weight based on accuracy (normalized)
    ROUND(
        AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) /
        NULLIF(AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) +
               AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END), 0), 3
    ) as recommended_rf_weight,
    ROUND(
        AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END) /
        NULLIF(AVG(CASE WHEN rf_correct THEN 1.0 ELSE 0.0 END) +
               AVG(CASE WHEN gb_correct THEN 1.0 ELSE 0.0 END), 0), 3
    ) as recommended_gb_weight

FROM forecast_evaluations
WHERE evaluation_date >= NOW() - INTERVAL '30 days'
  AND rf_correct IS NOT NULL
  AND gb_correct IS NOT NULL
GROUP BY horizon
ORDER BY horizon;

COMMENT ON VIEW v_model_comparison_by_horizon IS 'RF vs GB performance comparison by forecast horizon';

-- ============================================================================
-- 5. UPDATED RPC: Get horizon-specific dashboard
-- ============================================================================

CREATE OR REPLACE FUNCTION get_horizon_accuracy()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'daily', (
            SELECT row_to_json(t) FROM v_horizon_accuracy_detail t WHERE horizon = '1D'
        ),
        'weekly', (
            SELECT row_to_json(t) FROM v_horizon_accuracy_detail t WHERE horizon = '1W'
        ),
        'model_comparison', (
            SELECT json_agg(row_to_json(t)) FROM v_model_comparison_by_horizon t
        ),
        'top_symbols_daily', (
            SELECT json_agg(row_to_json(t))
            FROM (SELECT * FROM v_symbol_accuracy_by_horizon WHERE horizon = '1D' ORDER BY accuracy_pct DESC LIMIT 5) t
        ),
        'top_symbols_weekly', (
            SELECT json_agg(row_to_json(t))
            FROM (SELECT * FROM v_symbol_accuracy_by_horizon WHERE horizon = '1W' ORDER BY accuracy_pct DESC LIMIT 5) t
        ),
        'current_weights', (
            SELECT json_agg(row_to_json(t)) FROM model_weights t
        ),
        'generated_at', NOW()
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_horizon_accuracy() IS 'Returns detailed accuracy breakdown for daily (1D) vs weekly (1W) forecasts';
