-- AdaptiveSuperTrend Supabase Schema Setup
-- Run this in Supabase SQL Editor
-- Database: Your SwiftBolt_ML Supabase project

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- ============================================================================
-- FACTOR CACHE TABLE
-- ============================================================================
-- Stores optimized SuperTrend factors for each symbol/timeframe

CREATE TABLE IF NOT EXISTS adaptive_supertrend_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Identifiers
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  
  -- Optimal factor and metrics
  optimal_factor FLOAT NOT NULL,
  metrics JSONB,  -- Full PerformanceMetrics as JSON
  
  -- Individual metrics (for quick filtering)
  sharpe_ratio FLOAT,
  sortino_ratio FLOAT,
  calmar_ratio FLOAT,
  max_drawdown FLOAT,
  win_rate FLOAT,
  profit_factor FLOAT,
  total_return FLOAT,
  num_trades INT,
  recent_score FLOAT,
  
  -- Metadata
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  ttl_hours INT DEFAULT 24,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  -- Unique constraint: one entry per symbol/timeframe
  CONSTRAINT unique_symbol_timeframe UNIQUE (symbol, timeframe)
);

-- Indexes for common queries
CREATE INDEX idx_cache_symbol_timeframe ON adaptive_supertrend_cache(symbol, timeframe);
CREATE INDEX idx_cache_updated_at ON adaptive_supertrend_cache(updated_at DESC);
CREATE INDEX idx_cache_symbol ON adaptive_supertrend_cache(symbol);
CREATE INDEX idx_cache_timeframe ON adaptive_supertrend_cache(timeframe);
CREATE INDEX idx_cache_sharpe ON adaptive_supertrend_cache(sharpe_ratio DESC);

-- TTL cleanup trigger (deletes entries older than TTL)
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM adaptive_supertrend_cache
  WHERE NOW() - updated_at > (ttl_hours || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- Add comment
COMMENT ON TABLE adaptive_supertrend_cache IS 'Caches optimal SuperTrend factors (ATR multipliers) for each symbol/timeframe';

-- ============================================================================
-- SUPERTREND SIGNALS TABLE
-- ============================================================================
-- Stores generated SuperTrend signals for analysis and backtesting

CREATE TABLE IF NOT EXISTS supertrend_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Timestamp & identifiers
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  portfolio_id TEXT,
  
  -- Signal data
  trend INT,  -- 1 = bullish, 0 = bearish, -1 = unknown
  supertrend_value FLOAT NOT NULL,
  factor FLOAT NOT NULL,
  signal_strength FLOAT,  -- 0-10 scale
  confidence FLOAT,       -- 0-1 normalized
  distance_pct FLOAT,     -- Distance from price in %
  trend_duration INT,     -- Consecutive bars in trend
  performance_index FLOAT,
  
  -- Metrics (optional, if calculated)
  metrics JSONB,
  
  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  source TEXT DEFAULT 'adaptive_supertrend',
  
  -- Index for common queries
  PRIMARY KEY (id)
);

-- Indexes
CREATE INDEX idx_signals_symbol_timeframe_ts ON supertrend_signals(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_signals_symbol_ts ON supertrend_signals(symbol, timestamp DESC);
CREATE INDEX idx_signals_portfolio_ts ON supertrend_signals(portfolio_id, timestamp DESC);
CREATE INDEX idx_signals_trend ON supertrend_signals(trend);
CREATE INDEX idx_signals_strength ON supertrend_signals(signal_strength DESC);
CREATE INDEX idx_signals_created_at ON supertrend_signals(created_at DESC);

-- Partial index for recent bullish signals
CREATE INDEX idx_signals_bullish_recent ON supertrend_signals(symbol, timestamp DESC) 
WHERE trend = 1 AND timestamp > NOW() - INTERVAL '7 days';

-- Full-text search on symbol
CREATE INDEX idx_signals_symbol_gin ON supertrend_signals USING GIN(to_tsvector('english', symbol));

COMMENT ON TABLE supertrend_signals IS 'Stores generated SuperTrend signals for monitoring and ML training';

-- ============================================================================
-- FACTOR HISTORY VIEW
-- ============================================================================
-- Historical view of factor optimization trends

CREATE VIEW factor_history AS
SELECT 
  symbol,
  timeframe,
  optimal_factor,
  sharpe_ratio,
  sortino_ratio,
  calmar_ratio,
  win_rate,
  profit_factor,
  updated_at,
  ROW_NUMBER() OVER (PARTITION BY symbol, timeframe ORDER BY updated_at DESC) as recency_rank
FROM adaptive_supertrend_cache
ORDER BY updated_at DESC;

COMMENT ON VIEW factor_history IS 'Historical view of optimal factors for trend analysis';

-- ============================================================================
-- SIGNAL STATISTICS VIEW
-- ============================================================================
-- Recent signal statistics by symbol

CREATE VIEW signal_stats_24h AS
SELECT 
  symbol,
  timeframe,
  COUNT(*) as signal_count,
  SUM(CASE WHEN trend = 1 THEN 1 ELSE 0 END) as bullish_count,
  SUM(CASE WHEN trend = 0 THEN 1 ELSE 0 END) as bearish_count,
  AVG(signal_strength) as avg_strength,
  MAX(signal_strength) as max_strength,
  AVG(confidence) as avg_confidence,
  MIN(timestamp) as first_signal,
  MAX(timestamp) as latest_signal
FROM supertrend_signals
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY symbol, timeframe;

COMMENT ON VIEW signal_stats_24h IS 'Signal statistics for last 24 hours';

-- ============================================================================
-- FACTOR COMPARISON VIEW
-- ============================================================================
-- Compare factors across symbols/timeframes

CREATE VIEW factor_comparison AS
SELECT 
  symbol,
  timeframe,
  optimal_factor,
  sharpe_ratio,
  sortino_ratio,
  calmar_ratio,
  max_drawdown,
  win_rate,
  profit_factor,
  CASE 
    WHEN sharpe_ratio > 1.5 THEN 'Excellent'
    WHEN sharpe_ratio > 1.0 THEN 'Good'
    WHEN sharpe_ratio > 0.5 THEN 'Fair'
    ELSE 'Poor'
  END as performance_rating,
  updated_at
FROM adaptive_supertrend_cache
ORDER BY sharpe_ratio DESC;

COMMENT ON VIEW factor_comparison IS 'Comparison of factors across all symbols with performance ratings';

-- ============================================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- ============================================================================

-- Get latest factor for a symbol/timeframe
CREATE OR REPLACE FUNCTION get_latest_factor(p_symbol TEXT, p_timeframe TEXT)
RETURNS TABLE(
  optimal_factor FLOAT,
  sharpe_ratio FLOAT,
  updated_at TIMESTAMP
) AS $$
SELECT 
  optimal_factor,
  sharpe_ratio,
  updated_at
FROM adaptive_supertrend_cache
WHERE symbol = p_symbol AND timeframe = p_timeframe
LIMIT 1;
$$ LANGUAGE SQL;

-- Get best performing factors
CREATE OR REPLACE FUNCTION get_best_factors(p_limit INT DEFAULT 10)
RETURNS TABLE(
  symbol TEXT,
  timeframe TEXT,
  optimal_factor FLOAT,
  sharpe_ratio FLOAT,
  sortino_ratio FLOAT,
  calmar_ratio FLOAT
) AS $$
SELECT 
  symbol,
  timeframe,
  optimal_factor,
  sharpe_ratio,
  sortino_ratio,
  calmar_ratio
FROM adaptive_supertrend_cache
ORDER BY sharpe_ratio DESC
LIMIT p_limit;
$$ LANGUAGE SQL;

-- Get signal statistics for a symbol
CREATE OR REPLACE FUNCTION get_signal_stats(p_symbol TEXT, p_hours INT DEFAULT 24)
RETURNS TABLE(
  timeframe TEXT,
  signal_count BIGINT,
  avg_strength FLOAT,
  bullish_pct FLOAT,
  latest_signal TIMESTAMP
) AS $$
SELECT 
  timeframe,
  COUNT(*) as signal_count,
  AVG(signal_strength) as avg_strength,
  (SUM(CASE WHEN trend = 1 THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) as bullish_pct,
  MAX(timestamp) as latest_signal
FROM supertrend_signals
WHERE symbol = p_symbol AND timestamp > NOW() - (p_hours || ' hours')::INTERVAL
GROUP BY timeframe;
$$ LANGUAGE SQL;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) - Optional
-- ============================================================================
-- Uncomment if you want to restrict access

-- ALTER TABLE adaptive_supertrend_cache ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE supertrend_signals ENABLE ROW LEVEL SECURITY;

-- -- Allow service role full access
-- CREATE POLICY service_role_cache ON adaptive_supertrend_cache
--   FOR ALL
--   USING (auth.role() = 'service_role')
--   WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- INITIAL GRANTS (if using specific roles)
-- ============================================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON adaptive_supertrend_cache TO authenticated;
-- GRANT SELECT, INSERT ON supertrend_signals TO authenticated;

-- ============================================================================
-- NOTES FOR MAINTENANCE
-- ============================================================================
-- 
-- 1. TTL Cleanup:
--    Run periodically: SELECT cleanup_expired_cache();
--    Or set up cron job in pg_cron extension
--
-- 2. Statistics:
--    ANALYZE adaptive_supertrend_cache;
--    ANALYZE supertrend_signals;
--
-- 3. Partitioning (for large signal volumes):
--    Consider partitioning supertrend_signals by timestamp for better performance
--
-- 4. Backups:
--    Enable automated backups in Supabase dashboard
--
-- 5. Monitoring:
--    Watch for slow queries using pg_stat_statements extension
--

COMMENT ON SCHEMA public IS 'AdaptiveSuperTrend schema for SwiftBolt_ML platform - v1.0';
