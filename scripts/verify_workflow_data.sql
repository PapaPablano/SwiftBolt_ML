-- ============================================================================
-- WORKFLOW DATA VERIFICATION QUERIES
-- ============================================================================
-- Purpose: Verify data flow from GitHub Actions workflows through to forecasts
-- Sequence: Technical Indicators → ML Outputs → Forecasts
-- ============================================================================

-- ============================================================================
-- PART 1: TECHNICAL INDICATORS VERIFICATION
-- ============================================================================
-- Verifies that indicator_values are being populated by workflows
-- Source: intraday-ingestion.yml, ml-orchestration.yml

-- 1.1: Check latest indicator snapshots per symbol/timeframe
SELECT 
    s.ticker as symbol,
    iv.timeframe,
    COUNT(*) as indicator_count,
    MAX(iv.ts) as latest_bar_time,
    MAX(iv.created_at) as latest_computation,
    EXTRACT(EPOCH FROM (NOW() - MAX(iv.created_at)))/3600 as hours_since_update,
    -- Sample latest values
    (array_agg(iv.rsi ORDER BY iv.ts DESC))[1] as latest_rsi,
    (array_agg(iv.macd ORDER BY iv.ts DESC))[1] as latest_macd,
    (array_agg(iv.supertrend_trend ORDER BY iv.ts DESC))[1] as latest_supertrend_trend,
    (array_agg(iv.adx ORDER BY iv.ts DESC))[1] as latest_adx
FROM indicator_values iv
JOIN symbols s ON s.id = iv.symbol_id
WHERE iv.created_at > NOW() - INTERVAL '48 hours'
GROUP BY s.ticker, iv.timeframe
ORDER BY s.ticker, 
    CASE iv.timeframe 
        WHEN 'm15' THEN 1 
        WHEN 'h1' THEN 2 
        WHEN 'h4' THEN 3 
        WHEN 'd1' THEN 4 
        WHEN 'w1' THEN 5 
    END;

-- 1.2: Verify indicator completeness (check for NULL values)
SELECT 
    s.ticker as symbol,
    iv.timeframe,
    COUNT(*) as total_rows,
    COUNT(iv.rsi) as has_rsi,
    COUNT(iv.macd) as has_macd,
    COUNT(iv.supertrend_value) as has_supertrend,
    COUNT(iv.adx) as has_adx,
    COUNT(iv.atr_14) as has_atr,
    COUNT(iv.bb_upper) as has_bollinger,
    -- Calculate completeness percentage
    ROUND(100.0 * COUNT(iv.rsi) / NULLIF(COUNT(*), 0), 1) as rsi_pct,
    ROUND(100.0 * COUNT(iv.supertrend_value) / NULLIF(COUNT(*), 0), 1) as supertrend_pct
FROM indicator_values iv
JOIN symbols s ON s.id = iv.symbol_id
WHERE iv.created_at > NOW() - INTERVAL '24 hours'
GROUP BY s.ticker, iv.timeframe
ORDER BY s.ticker, iv.timeframe;

-- 1.3: Check for adaptive SuperTrend indicators (if enabled)
SELECT 
    s.ticker as symbol,
    iv.timeframe,
    COUNT(*) as total_rows,
    COUNT(iv.supertrend_factor) as has_adaptive_factor,
    COUNT(iv.supertrend_performance_index) as has_performance_index,
    COUNT(iv.supertrend_signal_strength) as has_signal_strength,
    COUNT(iv.signal_confidence) as has_signal_confidence,
    AVG(iv.supertrend_factor) as avg_factor,
    AVG(iv.supertrend_performance_index) as avg_performance_index,
    AVG(iv.signal_confidence) as avg_signal_confidence,
    MAX(iv.created_at) as latest_update
FROM indicator_values iv
JOIN symbols s ON s.id = iv.symbol_id
WHERE iv.created_at > NOW() - INTERVAL '24 hours'
  AND iv.supertrend_factor IS NOT NULL
GROUP BY s.ticker, iv.timeframe
ORDER BY s.ticker, iv.timeframe;

-- ============================================================================
-- PART 2: ML OUTPUTS VERIFICATION
-- ============================================================================
-- Verifies ML model outputs before they become forecasts
-- Checks: model predictions, evaluations, and quality metrics

-- 2.1: Check recent ML forecast evaluations (feedback loop)
SELECT 
    s.ticker as symbol,
    fe.horizon,
    fe.evaluation_date,
    fe.predicted_label,
    fe.realized_label,
    fe.direction_correct,
    fe.price_error,
    fe.price_error_pct,
    fe.predicted_confidence,
    fe.model_agreement,
    EXTRACT(EPOCH FROM (NOW() - fe.created_at))/3600 as hours_since_eval
FROM forecast_evaluations fe
JOIN symbols s ON s.id = fe.symbol_id
WHERE fe.created_at > NOW() - INTERVAL '7 days'
ORDER BY fe.created_at DESC
LIMIT 50;

-- 2.2: Check ML forecast evaluation summary by symbol
SELECT 
    s.ticker as symbol,
    fe.horizon,
    COUNT(*) as eval_count,
    ROUND(AVG(CASE WHEN fe.direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as directional_accuracy_pct,
    ROUND(AVG(fe.price_error_pct) * 100, 2) as avg_price_error_pct,
    AVG(fe.predicted_confidence) as avg_confidence,
    MAX(fe.evaluation_date) as latest_eval_date
FROM forecast_evaluations fe
JOIN symbols s ON s.id = fe.symbol_id
WHERE fe.created_at > NOW() - INTERVAL '30 days'
GROUP BY s.ticker, fe.horizon
ORDER BY s.ticker, fe.horizon;

-- 2.3: Check intraday forecast evaluations (for weight calibration)
SELECT 
    fe.symbol,
    fe.horizon,
    COUNT(*) as eval_count,
    ROUND(AVG(CASE WHEN fe.direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as directional_accuracy_pct,
    ROUND(AVG(fe.price_error_pct) * 100, 2) as avg_price_error_pct,
    MAX(fe.evaluation_date) as latest_eval,
    EXTRACT(EPOCH FROM (NOW() - MAX(fe.created_at)))/3600 as hours_since_last_eval
FROM forecast_evaluations fe
WHERE fe.created_at > NOW() - INTERVAL '7 days'
  AND fe.horizon IN ('15m', '1h', '4h', '8h')
GROUP BY fe.symbol, fe.horizon
ORDER BY fe.symbol, fe.horizon;

-- 2.4: Check model weight calibrations
SELECT 
    s.ticker as symbol,
    smw.horizon,
    smw.synth_weights->'layer_weights' as layer_weights,
    smw.calibration_source,
    smw.intraday_sample_count,
    smw.intraday_accuracy,
    smw.last_updated,
    EXTRACT(EPOCH FROM (NOW() - smw.last_updated))/3600 as hours_since_update
FROM symbol_model_weights smw
JOIN symbols s ON s.id = smw.symbol_id
WHERE smw.last_updated > NOW() - INTERVAL '7 days'
ORDER BY smw.last_updated DESC;

-- ============================================================================
-- PART 3: FORECASTS VERIFICATION
-- ============================================================================
-- Verifies final forecast outputs from workflows
-- Source: ml-orchestration.yml (nightly), intraday-forecast.yml

-- 3.1: Check latest forecasts per symbol/horizon
SELECT 
    s.ticker as symbol,
    mf.timeframe,
    mf.horizon,
    mf.overall_label as direction,
    ROUND(mf.confidence::numeric, 3) as confidence,
    mf.forecast_return,
    mf.model_agreement,
    mf.run_at,
    EXTRACT(EPOCH FROM (NOW() - mf.run_at))/3600 as hours_since_forecast,
    -- Check if forecast is stale (>25 hours for daily, >2 hours for intraday)
    CASE 
        WHEN mf.timeframe IN ('m15', 'h1') AND (NOW() - mf.run_at) > INTERVAL '2 hours' THEN 'STALE'
        WHEN mf.timeframe IN ('h4', 'd1') AND (NOW() - mf.run_at) > INTERVAL '25 hours' THEN 'STALE'
        ELSE 'FRESH'
    END as freshness_status
FROM ml_forecasts mf
JOIN symbols s ON s.id = mf.symbol_id
WHERE mf.run_at > NOW() - INTERVAL '48 hours'
ORDER BY s.ticker, mf.timeframe, mf.horizon;

-- 3.2: Forecast coverage check (which symbols have forecasts?)
SELECT 
    s.ticker as symbol,
    COUNT(DISTINCT mf.horizon) as horizon_count,
    array_agg(DISTINCT mf.horizon ORDER BY mf.horizon) as horizons_covered,
    array_agg(DISTINCT mf.timeframe ORDER BY mf.timeframe) as timeframes_covered,
    MAX(mf.run_at) as latest_forecast,
    EXTRACT(EPOCH FROM (NOW() - MAX(mf.run_at)))/3600 as hours_since_latest
FROM symbols s
LEFT JOIN ml_forecasts mf ON mf.symbol_id = s.id 
    AND mf.run_at > NOW() - INTERVAL '48 hours'
WHERE s.ticker IN (
    SELECT DISTINCT ticker 
    FROM watchlist_items wi 
    JOIN symbols s2 ON s2.id = wi.symbol_id
)
GROUP BY s.ticker
ORDER BY hours_since_latest NULLS LAST, s.ticker;

-- 3.3: Forecast quality metrics
SELECT 
    s.ticker as symbol,
    mf.horizon,
    mf.overall_label as direction,
    mf.confidence,
    mf.quality_score,
    mf.model_agreement,
    jsonb_array_length(mf.quality_issues) as issue_count,
    mf.quality_issues,
    mf.run_at
FROM ml_forecasts mf
JOIN symbols s ON s.id = mf.symbol_id
WHERE mf.run_at > NOW() - INTERVAL '24 hours'
  AND (mf.quality_score < 0.7 OR jsonb_array_length(mf.quality_issues) > 0)
ORDER BY mf.quality_score NULLS LAST, s.ticker;

-- 3.4: Intraday forecasts check (separate table)
SELECT 
    symbol,
    timeframe,
    horizon,
    overall_label as direction,
    ROUND(confidence::numeric, 3) as confidence,
    target_price,
    current_price,
    ROUND(((target_price - current_price) / NULLIF(current_price, 0))::numeric, 4) as implied_return,
    layers_agreeing,
    created_at,
    expires_at,
    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_since_forecast,
    CASE WHEN expires_at < NOW() THEN 'EXPIRED' ELSE 'ACTIVE' END as status
FROM ml_forecasts_intraday
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 50;

-- ============================================================================
-- PART 4: WORKFLOW HEALTH CHECK
-- ============================================================================
-- Cross-checks to verify complete data flow

-- 4.1: End-to-end check: Indicators → Forecasts
WITH latest_indicators AS (
    SELECT 
        s.ticker,
        iv.timeframe,
        MAX(iv.created_at) as latest_indicator_time
    FROM indicator_values iv
    JOIN symbols s ON s.id = iv.symbol_id
    WHERE iv.created_at > NOW() - INTERVAL '48 hours'
    GROUP BY s.ticker, iv.timeframe
),
latest_forecasts AS (
    SELECT 
        s.ticker,
        mf.timeframe,
        MAX(mf.run_at) as latest_forecast_time
    FROM ml_forecasts mf
    JOIN symbols s ON s.id = mf.symbol_id
    WHERE mf.run_at > NOW() - INTERVAL '48 hours'
    GROUP BY s.ticker, mf.timeframe
)
SELECT 
    COALESCE(li.ticker, lf.ticker) as symbol,
    COALESCE(li.timeframe, lf.timeframe) as timeframe,
    li.latest_indicator_time,
    lf.latest_forecast_time,
    EXTRACT(EPOCH FROM (lf.latest_forecast_time - li.latest_indicator_time))/60 as forecast_lag_minutes,
    CASE 
        WHEN li.latest_indicator_time IS NULL THEN 'MISSING_INDICATORS'
        WHEN lf.latest_forecast_time IS NULL THEN 'MISSING_FORECAST'
        WHEN lf.latest_forecast_time < li.latest_indicator_time THEN 'FORECAST_STALE'
        ELSE 'OK'
    END as pipeline_status
FROM latest_indicators li
FULL OUTER JOIN latest_forecasts lf 
    ON li.ticker = lf.ticker AND li.timeframe = lf.timeframe
ORDER BY pipeline_status DESC, symbol, timeframe;

-- 4.2: Data freshness summary
SELECT 
    'Indicators' as data_type,
    COUNT(DISTINCT symbol_id) as symbol_count,
    MAX(created_at) as latest_update,
    EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_since_latest
FROM indicator_values
WHERE created_at > NOW() - INTERVAL '48 hours'
UNION ALL
SELECT 
    'ML Forecasts' as data_type,
    COUNT(DISTINCT symbol_id) as symbol_count,
    MAX(run_at) as latest_update,
    EXTRACT(EPOCH FROM (NOW() - MAX(run_at)))/3600 as hours_since_latest
FROM ml_forecasts
WHERE run_at > NOW() - INTERVAL '48 hours'
UNION ALL
SELECT 
    'Intraday Forecasts' as data_type,
    COUNT(DISTINCT symbol) as symbol_count,
    MAX(created_at) as latest_update,
    EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_since_latest
FROM ml_forecasts_intraday
WHERE created_at > NOW() - INTERVAL '48 hours'
UNION ALL
SELECT 
    'Forecast Evaluations' as data_type,
    COUNT(DISTINCT symbol_id) as symbol_count,
    MAX(created_at) as latest_update,
    EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))/3600 as hours_since_latest
FROM forecast_evaluations
WHERE created_at > NOW() - INTERVAL '7 days';

-- 4.3: Workflow execution timeline (last 24 hours)
WITH workflow_events AS (
    SELECT 'Indicator Computation' as event_type, created_at as event_time
    FROM indicator_values
    WHERE created_at > NOW() - INTERVAL '24 hours'
    UNION ALL
    SELECT 'ML Forecast Generated' as event_type, run_at as event_time
    FROM ml_forecasts
    WHERE run_at > NOW() - INTERVAL '24 hours'
    UNION ALL
    SELECT 'Intraday Forecast Generated' as event_type, created_at as event_time
    FROM ml_forecasts_intraday
    WHERE created_at > NOW() - INTERVAL '24 hours'
    UNION ALL
    SELECT 'Forecast Evaluated' as event_type, created_at as event_time
    FROM forecast_evaluations
    WHERE created_at > NOW() - INTERVAL '24 hours'
)
SELECT 
    event_type,
    COUNT(*) as event_count,
    MIN(event_time) as first_event,
    MAX(event_time) as last_event,
    EXTRACT(EPOCH FROM (MAX(event_time) - MIN(event_time)))/3600 as duration_hours
FROM workflow_events
GROUP BY event_type
ORDER BY MAX(event_time) DESC;

-- ============================================================================
-- USAGE INSTRUCTIONS
-- ============================================================================
-- Run these queries in sequence to verify your workflow data pipeline:
--
-- 1. Part 1 (Technical Indicators): Verify indicators are being computed
-- 2. Part 2 (ML Outputs): Check model evaluations and calibrations
-- 3. Part 3 (Forecasts): Verify final forecast outputs
-- 4. Part 4 (Health Check): Cross-check complete pipeline
--
-- Expected workflow sequence:
-- - Intraday Ingestion (every 15 min during market hours) → indicator_values
-- - Intraday Forecast (every 15 min) → ml_forecasts_intraday
-- - ML Orchestration (nightly 22:00 CST) → ml_forecasts, forecast_evaluations
-- - Weight calibration → symbol_weight_overrides
--
-- Freshness expectations:
-- - Indicators (m15, h1): < 2 hours old during market hours
-- - Indicators (d1): < 25 hours old
-- - Forecasts (intraday): < 2 hours old during market hours
-- - Forecasts (daily): < 25 hours old
-- - Evaluations: < 7 days old
-- ============================================================================
