-- Add composite indexes for common query patterns
-- Improves performance for chart data queries

-- Index for chart data queries (most common pattern)
CREATE INDEX IF NOT EXISTS idx_ohlc_chart_query 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_forecast = false;

-- Index for date range queries with provider filter
CREATE INDEX IF NOT EXISTS idx_ohlc_provider_range 
ON ohlc_bars_v2 (symbol_id, timeframe, provider, ts)
WHERE is_forecast = false;

-- Index for intraday queries (today's data)
CREATE INDEX IF NOT EXISTS idx_ohlc_intraday 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_intraday = true;

-- Index for forecast queries
CREATE INDEX IF NOT EXISTS idx_ohlc_forecast 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_forecast = true;

-- Index for data status filtering (verified data only)
CREATE INDEX IF NOT EXISTS idx_ohlc_verified 
ON ohlc_bars_v2 (symbol_id, timeframe, ts, data_status)
WHERE data_status = 'verified';

-- Add comments
COMMENT ON INDEX idx_ohlc_chart_query IS 
'Optimizes chart data queries by symbol, timeframe, and date range.';

COMMENT ON INDEX idx_ohlc_provider_range IS 
'Optimizes queries filtering by provider (polygon, tradier, etc).';

COMMENT ON INDEX idx_ohlc_intraday IS 
'Optimizes intraday data queries for real-time updates.';

COMMENT ON INDEX idx_ohlc_forecast IS 
'Optimizes forecast data queries for ML predictions.';
