-- Create technical indicators cache table
-- Cache TTL: 5 minutes (manually managed via cached_at timestamp)

CREATE TABLE IF NOT EXISTS technical_indicators_cache (
  cache_key TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  data JSONB NOT NULL,
  cached_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_ti_cache_symbol_timeframe
ON technical_indicators_cache(symbol, timeframe);

CREATE INDEX IF NOT EXISTS idx_ti_cache_cached_at
ON technical_indicators_cache(cached_at);

-- Set up auto-cleanup of old cache entries (older than 1 hour)
-- This helps keep the table small
CREATE OR REPLACE FUNCTION cleanup_ti_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM technical_indicators_cache
  WHERE cached_at < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- Optional: Schedule cleanup (requires pg_cron extension)
-- SELECT cron.schedule('cleanup_ti_cache', '0 * * * *', 'SELECT cleanup_ti_cache()');

COMMENT ON TABLE technical_indicators_cache IS 'Cache for technical indicators. TTL: 5 minutes. Useful for fast repeated requests.';
COMMENT ON COLUMN technical_indicators_cache.cache_key IS 'Unique key: SYMBOL_TIMEFRAME (e.g., AAPL_d1)';
COMMENT ON COLUMN technical_indicators_cache.data IS 'Full technical indicators response as JSON';
COMMENT ON COLUMN technical_indicators_cache.cached_at IS 'When this cache entry was last updated';
