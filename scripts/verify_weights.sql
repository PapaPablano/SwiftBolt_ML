-- ============================================================
-- Verify Model Weights and Calibration System
-- ============================================================
-- Run these queries in Supabase SQL editor to verify your
-- symbol_model_weights table and intraday calibration system

-- ============================================================
-- 1. CHECK WEIGHT STRUCTURE FOR ALL SYMBOLS
-- ============================================================
SELECT 
    s.ticker,
    smw.horizon,
    smw.calibration_source,
    smw.intraday_sample_count,
    smw.intraday_accuracy,
    smw.last_updated,
    -- Extract layer weights from JSONB
    (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric AS supertrend_weight,
    (smw.synth_weights->'layer_weights'->>'sr_component')::numeric AS sr_weight,
    (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS ensemble_weight,
    -- Calculate sum to verify they add up to ~1.0
    (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric +
    (smw.synth_weights->'layer_weights'->>'sr_component')::numeric +
    (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS weight_sum,
    -- Check if structure is valid
    CASE 
        WHEN smw.synth_weights ? 'layer_weights' THEN '✅ Valid'
        ELSE '❌ Missing layer_weights'
    END AS structure_status
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
ORDER BY s.ticker, smw.horizon;


-- ============================================================
-- 2. VERIFY WEIGHT SUMS (Should be close to 1.0)
-- ============================================================
WITH weight_analysis AS (
    SELECT 
        s.ticker,
        smw.horizon,
        (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric +
        (smw.synth_weights->'layer_weights'->>'sr_component')::numeric +
        (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS weight_sum
    FROM symbol_model_weights smw
    JOIN symbols s ON s.id = smw.symbol_id
)
SELECT 
    ticker,
    horizon,
    weight_sum,
    CASE 
        WHEN ABS(weight_sum - 1.0) <= 0.01 THEN '✅ OK'
        ELSE '⚠️ Off by ' || ROUND(ABS(weight_sum - 1.0)::numeric, 4)::text
    END AS validation_status
FROM weight_analysis
ORDER BY ABS(weight_sum - 1.0) DESC;


-- ============================================================
-- 3. CHECK INTRADAY CALIBRATION DATA FOR SPECIFIC SYMBOL
-- ============================================================
-- Replace 'AAPL' with your symbol
SELECT * FROM get_intraday_calibration_data(
    (SELECT id FROM symbols WHERE ticker = 'AAPL'),
    72  -- lookback hours
);


-- ============================================================
-- 4. VIEW RECENT EVALUATIONS WITH COMPONENT ACCURACY
-- ============================================================
SELECT 
    s.ticker,
    e.horizon,
    e.evaluated_at,
    e.direction_correct,
    ROUND(e.price_error_pct::numeric, 4) AS price_error_pct,
    e.supertrend_direction_correct AS st_correct,
    e.sr_containment AS sr_contained,
    e.ensemble_direction_correct AS ensemble_correct
FROM ml_forecast_evaluations_intraday e
JOIN symbols s ON s.id = e.symbol_id
WHERE e.evaluated_at >= NOW() - INTERVAL '24 hours'
ORDER BY e.evaluated_at DESC
LIMIT 50;


-- ============================================================
-- 5. COMPONENT ACCURACY SUMMARY BY SYMBOL
-- ============================================================
SELECT 
    s.ticker,
    e.horizon,
    COUNT(*) AS total_evaluations,
    ROUND(AVG(CASE WHEN e.direction_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS direction_accuracy,
    ROUND(AVG(ABS(e.price_error_pct))::numeric, 4) AS avg_price_error,
    ROUND(AVG(CASE WHEN e.supertrend_direction_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS st_accuracy,
    ROUND(AVG(CASE WHEN e.sr_containment THEN 1.0 ELSE 0.0 END)::numeric, 4) AS sr_containment_rate,
    ROUND(AVG(CASE WHEN e.ensemble_direction_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS ensemble_accuracy
FROM ml_forecast_evaluations_intraday e
JOIN symbols s ON s.id = e.symbol_id
WHERE e.evaluated_at >= NOW() - INTERVAL '72 hours'
GROUP BY s.ticker, e.horizon
ORDER BY s.ticker, e.horizon;


-- ============================================================
-- 6. CHECK FOR PENDING FORECASTS AWAITING EVALUATION
-- ============================================================
SELECT * FROM get_pending_intraday_evaluations();


-- ============================================================
-- 7. WEIGHT UPDATE HISTORY (Check freshness)
-- ============================================================
SELECT 
    s.ticker,
    smw.horizon,
    smw.calibration_source,
    smw.intraday_sample_count,
    smw.last_updated,
    NOW() - smw.last_updated AS age,
    CASE 
        WHEN NOW() - smw.last_updated < INTERVAL '24 hours' THEN '✅ Fresh'
        WHEN NOW() - smw.last_updated < INTERVAL '7 days' THEN '⚠️ Stale'
        ELSE '❌ Very Stale'
    END AS freshness
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
ORDER BY smw.last_updated DESC;


-- ============================================================
-- 8. DETAILED WEIGHT BREAKDOWN FOR SPECIFIC SYMBOL
-- ============================================================
-- Replace 'NVDA' with your symbol
WITH symbol_weights AS (
    SELECT 
        smw.horizon,
        smw.synth_weights,
        smw.calibration_source,
        smw.intraday_sample_count,
        smw.intraday_accuracy,
        smw.last_updated
    FROM symbol_model_weights smw
    JOIN symbols s ON s.id = smw.symbol_id
    WHERE s.ticker = 'NVDA'
)
SELECT 
    horizon,
    calibration_source,
    intraday_sample_count,
    ROUND(intraday_accuracy::numeric, 4) AS intraday_accuracy,
    last_updated,
    jsonb_pretty(synth_weights) AS weights_json
FROM symbol_weights;


-- ============================================================
-- 9. IDENTIFY WEIGHTS WITH STRUCTURAL ISSUES
-- ============================================================
SELECT 
    s.ticker,
    smw.horizon,
    CASE 
        WHEN NOT (smw.synth_weights ? 'layer_weights') THEN 'Missing layer_weights key'
        WHEN NOT (smw.synth_weights->'layer_weights' ? 'supertrend_component') THEN 'Missing supertrend_component'
        WHEN NOT (smw.synth_weights->'layer_weights' ? 'sr_component') THEN 'Missing sr_component'
        WHEN NOT (smw.synth_weights->'layer_weights' ? 'ensemble_component') THEN 'Missing ensemble_component'
        ELSE 'Unknown issue'
    END AS issue_description
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
WHERE 
    NOT (smw.synth_weights ? 'layer_weights')
    OR NOT (smw.synth_weights->'layer_weights' ? 'supertrend_component')
    OR NOT (smw.synth_weights->'layer_weights' ? 'sr_component')
    OR NOT (smw.synth_weights->'layer_weights' ? 'ensemble_component');


-- ============================================================
-- 10. CALIBRATION EFFECTIVENESS ANALYSIS
-- ============================================================
-- Compare accuracy before and after calibration updates
WITH evaluation_windows AS (
    SELECT 
        s.ticker,
        e.horizon,
        e.evaluated_at,
        e.direction_correct,
        e.price_error_pct,
        smw.last_updated AS weight_update_time,
        CASE 
            WHEN e.evaluated_at > smw.last_updated THEN 'After Update'
            ELSE 'Before Update'
        END AS window_period
    FROM ml_forecast_evaluations_intraday e
    JOIN symbols s ON s.id = e.symbol_id
    LEFT JOIN symbol_model_weights smw 
        ON smw.symbol_id = e.symbol_id 
        AND smw.horizon = e.horizon
    WHERE e.evaluated_at >= NOW() - INTERVAL '7 days'
)
SELECT 
    ticker,
    horizon,
    window_period,
    COUNT(*) AS evaluations,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) AS accuracy,
    ROUND(AVG(ABS(price_error_pct))::numeric, 4) AS avg_error
FROM evaluation_windows
GROUP BY ticker, horizon, window_period
ORDER BY ticker, horizon, window_period;


-- ============================================================
-- 11. SYSTEM HEALTH DASHBOARD
-- ============================================================
SELECT 
    'Total Symbols with Weights' AS metric,
    COUNT(DISTINCT symbol_id)::text AS value
FROM symbol_model_weights

UNION ALL

SELECT 
    'Total Weight Entries' AS metric,
    COUNT(*)::text AS value
FROM symbol_model_weights

UNION ALL

SELECT 
    'Evaluations (Last 24h)' AS metric,
    COUNT(*)::text AS value
FROM ml_forecast_evaluations_intraday
WHERE evaluated_at >= NOW() - INTERVAL '24 hours'

UNION ALL

SELECT 
    'Pending Evaluations' AS metric,
    COUNT(*)::text AS value
FROM ml_forecasts_intraday f
WHERE f.expires_at <= NOW()
    AND NOT EXISTS (
        SELECT 1 FROM ml_forecast_evaluations_intraday e
        WHERE e.forecast_id = f.id
    )

UNION ALL

SELECT 
    'Intraday Calibrated Weights' AS metric,
    COUNT(*)::text AS value
FROM symbol_model_weights
WHERE calibration_source = 'intraday'
    AND intraday_sample_count > 0

UNION ALL

SELECT 
    'Avg Intraday Accuracy' AS metric,
    ROUND(AVG(intraday_accuracy)::numeric, 4)::text AS value
FROM symbol_model_weights
WHERE intraday_accuracy IS NOT NULL;


-- ============================================================
-- 12. WEIGHT COMPONENT DISTRIBUTION
-- ============================================================
WITH weight_components AS (
    SELECT 
        s.ticker,
        smw.horizon,
        (smw.synth_weights->'layer_weights'->>'supertrend_component')::numeric AS st,
        (smw.synth_weights->'layer_weights'->>'sr_component')::numeric AS sr,
        (smw.synth_weights->'layer_weights'->>'ensemble_component')::numeric AS ensemble
    FROM symbol_model_weights smw
    JOIN symbols s ON s.id = smw.symbol_id
)
SELECT 
    'SuperTrend' AS component,
    ROUND(MIN(st)::numeric, 4) AS min_weight,
    ROUND(AVG(st)::numeric, 4) AS avg_weight,
    ROUND(MAX(st)::numeric, 4) AS max_weight
FROM weight_components

UNION ALL

SELECT 
    'Support/Resistance' AS component,
    ROUND(MIN(sr)::numeric, 4) AS min_weight,
    ROUND(AVG(sr)::numeric, 4) AS avg_weight,
    ROUND(MAX(sr)::numeric, 4) AS max_weight
FROM weight_components

UNION ALL

SELECT 
    'Ensemble' AS component,
    ROUND(MIN(ensemble)::numeric, 4) AS min_weight,
    ROUND(AVG(ensemble)::numeric, 4) AS avg_weight,
    ROUND(MAX(ensemble)::numeric, 4) AS max_weight
FROM weight_components;
