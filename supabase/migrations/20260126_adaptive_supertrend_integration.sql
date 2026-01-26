-- Migration: Add AdaptiveSuperTrend integration columns to indicator_values
-- Date: January 26, 2026
-- Purpose: Persist adaptive SuperTrend signals, factors, and performance metrics

-- ============================================================================
-- 1. Extend indicator_values table with adaptive SuperTrend columns
-- ============================================================================

ALTER TABLE IF EXISTS indicator_values
ADD COLUMN IF NOT EXISTS supertrend_factor FLOAT8,
    -- Adaptive ATR multiplier factor (typically 1.0-5.0)
    -- NULL = not computed, use standard fixed factor
    
ADD COLUMN IF NOT EXISTS supertrend_signal_strength FLOAT8,
    -- Signal strength on 0-10 scale
    -- 0-3: weak signal, 3-7: moderate, 7-10: strong
    
ADD COLUMN IF NOT EXISTS supertrend_confidence FLOAT8,
    -- Confidence 0-1 normalized
    -- Based on performance_index, recent_score, distance from ST
    
ADD COLUMN IF NOT EXISTS supertrend_performance_index FLOAT8,
    -- 0-1 score: how well the current adaptive factor is working
    -- Higher = factor performing well in recent history
    
ADD COLUMN IF NOT EXISTS supertrend_distance_pct FLOAT8,
    -- Distance from current price to SuperTrend value in %
    -- Positive = price above ST (bullish), negative = below (bearish)
    
ADD COLUMN IF NOT EXISTS supertrend_trend_duration INT,
    -- Number of bars in current trend
    -- Higher = stronger/more established trend
    
ADD COLUMN IF NOT EXISTS supertrend_metrics JSONB;
    -- Full performance metrics: {sharpe_ratio, sortino_ratio, calmar_ratio, ...}

-- ============================================================================
-- 2. Create indexes for fast queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_indicator_values_symbol_supertrend_factor
ON indicator_values(symbol, supertrend_factor)
WHERE supertrend_factor IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_indicator_values_symbol_confidence
ON indicator_values(symbol, supertrend_confidence DESC)
WHERE supertrend_confidence IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_indicator_values_created_at_supertrend
ON indicator_values(created_at DESC)
WHERE supertrend_factor IS NOT NULL;

-- ============================================================================
-- 3. Extend ml_forecasts table to reference adaptive signals
-- ============================================================================

ALTER TABLE IF EXISTS ml_forecasts
ADD COLUMN IF NOT EXISTS adaptive_supertrend_consensus FLOAT8,
    -- Consensus score (0-1) across multiple timeframes
    -- 0 = all bearish, 1 = all bullish
    
ADD COLUMN IF NOT EXISTS adaptive_supertrend_confidence FLOAT8;
    -- Average confidence across timeframes

-- ============================================================================
-- 4. Create view for latest adaptive signals per symbol
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_supertrend_latest_signals AS
SELECT
    symbol,
    supertrend_factor,
    supertrend_signal_strength,
    supertrend_confidence,
    supertrend_performance_index,
    supertrend_distance_pct,
    supertrend_trend_duration,
    supertrend_metrics,
    created_at,
    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY created_at DESC) as rn
FROM indicator_values
WHERE supertrend_factor IS NOT NULL;

-- ============================================================================
-- 5. Helper function: Get latest adaptive factor for symbol
-- ============================================================================

CREATE OR REPLACE FUNCTION get_latest_adaptive_supertrend_factor(p_symbol TEXT)
RETURNS FLOAT8 AS $$
SELECT supertrend_factor
FROM indicator_values
WHERE symbol = p_symbol
AND supertrend_factor IS NOT NULL
ORDER BY created_at DESC
LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- 6. Helper function: Get latest adaptive signal snapshot
-- ============================================================================

CREATE OR REPLACE FUNCTION get_latest_adaptive_supertrend_signal(p_symbol TEXT)
RETURNS TABLE (
    symbol TEXT,
    factor FLOAT8,
    signal_strength FLOAT8,
    confidence FLOAT8,
    performance_index FLOAT8,
    distance_pct FLOAT8,
    trend_duration INT,
    metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
SELECT
    symbol,
    supertrend_factor,
    supertrend_signal_strength,
    supertrend_confidence,
    supertrend_performance_index,
    supertrend_distance_pct,
    supertrend_trend_duration,
    supertrend_metrics,
    created_at
FROM indicator_values
WHERE symbol = p_symbol
AND supertrend_factor IS NOT NULL
ORDER BY created_at DESC
LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- 7. Aggregation view: Factor statistics by symbol
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_supertrend_factor_stats AS
SELECT
    symbol,
    COUNT(*) as signal_count_24h,
    AVG(supertrend_factor) as avg_factor,
    MIN(supertrend_factor) as min_factor,
    MAX(supertrend_factor) as max_factor,
    STDDEV(supertrend_factor) as stddev_factor,
    AVG(supertrend_confidence) as avg_confidence,
    AVG(supertrend_signal_strength) as avg_strength,
    MAX(created_at) as latest_update,
    EXTRACT(HOURS FROM NOW() - MAX(created_at)) as hours_since_update
FROM indicator_values
WHERE supertrend_factor IS NOT NULL
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY signal_count_24h DESC;

-- ============================================================================
-- 8. Aggregation view: Performance metrics by symbol
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_supertrend_performance_stats AS
SELECT
    symbol,
    COUNT(*) as metric_count,
    -- Sharpe Ratio stats
    AVG((supertrend_metrics->'sharpe_ratio')::FLOAT8) as avg_sharpe,
    MAX((supertrend_metrics->'sharpe_ratio')::FLOAT8) as max_sharpe,
    -- Sortino Ratio stats
    AVG((supertrend_metrics->'sortino_ratio')::FLOAT8) as avg_sortino,
    MAX((supertrend_metrics->'sortino_ratio')::FLOAT8) as max_sortino,
    -- Calmar Ratio stats
    AVG((supertrend_metrics->'calmar_ratio')::FLOAT8) as avg_calmar,
    MAX((supertrend_metrics->'calmar_ratio')::FLOAT8) as max_calmar,
    -- Win Rate stats
    AVG((supertrend_metrics->'win_rate')::FLOAT8) as avg_win_rate,
    -- Max Drawdown stats
    MIN((supertrend_metrics->'max_drawdown')::FLOAT8) as min_max_drawdown,  -- Less negative = better
    -- Total Return stats
    AVG((supertrend_metrics->'total_return')::FLOAT8) as avg_total_return,
    MAX((supertrend_metrics->'total_return')::FLOAT8) as max_total_return,
    MAX(created_at) as latest_update
FROM indicator_values
WHERE supertrend_metrics IS NOT NULL
AND created_at > NOW() - INTERVAL '7 days'
GROUP BY symbol
ORDER BY avg_sharpe DESC NULLS LAST;

-- ============================================================================
-- 9. Health check view: Identify stale factors
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_supertrend_staleness_check AS
SELECT
    symbol,
    MAX(created_at) as latest_signal,
    EXTRACT(HOURS FROM NOW() - MAX(created_at)) as hours_since_update,
    COUNT(*) as signals_last_24h,
    CASE
        WHEN EXTRACT(HOURS FROM NOW() - MAX(created_at)) > 48 THEN 'STALE'
        WHEN EXTRACT(HOURS FROM NOW() - MAX(created_at)) > 24 THEN 'WARNING'
        ELSE 'HEALTHY'
    END as staleness_status
FROM indicator_values
WHERE supertrend_factor IS NOT NULL
GROUP BY symbol
HAVING MAX(created_at) > NOW() - INTERVAL '7 days'
ORDER BY hours_since_update DESC;

-- ============================================================================
-- 10. Comparison view: Adaptive vs Fixed Factor performance
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_vs_fixed_comparison AS
WITH adaptive_metrics AS (
    SELECT
        symbol,
        AVG((supertrend_metrics->'sharpe_ratio')::FLOAT8) as adaptive_sharpe,
        AVG((supertrend_metrics->'sortino_ratio')::FLOAT8) as adaptive_sortino,
        AVG((supertrend_metrics->'total_return')::FLOAT8) as adaptive_return,
        COUNT(*) as adaptive_count
    FROM indicator_values
    WHERE supertrend_metrics IS NOT NULL
    AND supertrend_factor IS NOT NULL
    AND created_at > NOW() - INTERVAL '7 days'
    GROUP BY symbol
)
SELECT
    am.symbol,
    am.adaptive_sharpe,
    am.adaptive_sortino,
    am.adaptive_return,
    am.adaptive_count,
    -- Note: Fixed factor metrics would come from comparison table in future
    -- For now, this view provides baseline for adaptive metrics
    CASE
        WHEN am.adaptive_sharpe > 1.5 THEN 'EXCELLENT'
        WHEN am.adaptive_sharpe > 1.0 THEN 'GOOD'
        WHEN am.adaptive_sharpe > 0.5 THEN 'FAIR'
        ELSE 'POOR'
    END as sharpe_rating
FROM adaptive_metrics am
ORDER BY am.adaptive_sharpe DESC NULLS LAST;

-- ============================================================================
-- 11. Alert/notification view: Identify anomalies
-- ============================================================================

CREATE OR REPLACE VIEW adaptive_supertrend_anomalies AS
WITH recent_stats AS (
    SELECT
        symbol,
        AVG(supertrend_factor) as avg_factor,
        STDDEV(supertrend_factor) as stddev_factor,
        AVG(supertrend_confidence) as avg_confidence,
        COUNT(*) as count
    FROM indicator_values
    WHERE supertrend_factor IS NOT NULL
    AND created_at > NOW() - INTERVAL '24 hours'
    GROUP BY symbol
)
SELECT
    symbol,
    avg_factor,
    stddev_factor,
    avg_confidence,
    CASE
        WHEN stddev_factor > avg_factor THEN 'HIGH_VOLATILITY'  -- Factor changing wildly
        WHEN avg_confidence < 0.3 THEN 'LOW_CONFIDENCE'        -- Signals not confident
        WHEN count < 10 THEN 'INSUFFICIENT_DATA'               -- Not enough updates
        ELSE 'NORMAL'
    END as anomaly_type,
    count
FROM recent_stats
WHERE stddev_factor > avg_factor
   OR avg_confidence < 0.3
   OR count < 10
ORDER BY symbol;

-- ============================================================================
-- 12. Grants (adjust as needed for your setup)
-- ============================================================================

-- Allow app_user to read/write indicator_values
GRANT SELECT, INSERT, UPDATE ON indicator_values TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- Allow all users to execute helper functions
GRANT EXECUTE ON FUNCTION get_latest_adaptive_supertrend_factor(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_latest_adaptive_supertrend_signal(TEXT) TO authenticated;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON COLUMN indicator_values.supertrend_factor IS
'Adaptive ATR multiplier factor (typically 1.0-5.0). Result of walk-forward optimization. NULL = not computed.';

COMMENT ON COLUMN indicator_values.supertrend_signal_strength IS
'Signal strength 0-10 scale. 0-3: weak, 3-7: moderate, 7-10: strong.';

COMMENT ON COLUMN indicator_values.supertrend_confidence IS
'Confidence 0-1 normalized. Based on performance_index, recent score, distance from ST.';

COMMENT ON COLUMN indicator_values.supertrend_performance_index IS
'0-1 score: how well the current adaptive factor is working. Higher = better performance in recent history.';

COMMENT ON COLUMN indicator_values.supertrend_metrics IS
'Full performance metrics JSONB: sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown, win_rate, profit_factor, total_return, num_trades, recent_score.';

COMMENT ON VIEW adaptive_supertrend_latest_signals IS
'Latest adaptive SuperTrend signals per symbol with all metrics. Use ROW_NUMBER filtering for single latest per symbol.';

COMMENT ON FUNCTION get_latest_adaptive_supertrend_factor(TEXT) IS
'Retrieve the latest adaptive factor for a given symbol. Returns NULL if no signal computed.';

COMMENT ON FUNCTION get_latest_adaptive_supertrend_signal(TEXT) IS
'Retrieve complete latest signal snapshot for a symbol including all metrics and timestamps.';
