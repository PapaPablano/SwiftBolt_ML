-- Migration: Add intraday lifecycle functions
-- Handles the transition from intraday (Tradier) to historical (Polygon) data

-- Function: Clean up stale intraday data (older than today)
CREATE OR REPLACE FUNCTION cleanup_stale_intraday()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM ohlc_bars_v2
  WHERE provider = 'tradier'
    AND is_intraday = true
    AND DATE(ts) < CURRENT_DATE;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get the latest historical date for a symbol
-- Used to determine if we need to fetch more Polygon data
CREATE OR REPLACE FUNCTION get_latest_historical_date(p_symbol_id UUID, p_timeframe VARCHAR(10))
RETURNS DATE AS $$
DECLARE
  latest_date DATE;
BEGIN
  SELECT DATE(MAX(ts))
  INTO latest_date
  FROM ohlc_bars_v2
  WHERE symbol_id = p_symbol_id
    AND timeframe = p_timeframe
    AND provider = 'polygon'
    AND is_forecast = false;

  RETURN latest_date;
END;
$$ LANGUAGE plpgsql;

-- Function: Check if historical data is stale (missing yesterday's data)
CREATE OR REPLACE FUNCTION is_historical_stale(p_symbol_id UUID, p_timeframe VARCHAR(10))
RETURNS BOOLEAN AS $$
DECLARE
  latest_date DATE;
  yesterday DATE;
BEGIN
  latest_date := get_latest_historical_date(p_symbol_id, p_timeframe);
  yesterday := CURRENT_DATE - INTERVAL '1 day';

  -- Skip weekends
  IF EXTRACT(DOW FROM yesterday) IN (0, 6) THEN
    -- Find the previous Friday
    IF EXTRACT(DOW FROM yesterday) = 0 THEN
      yesterday := yesterday - INTERVAL '2 days';
    ELSE
      yesterday := yesterday - INTERVAL '1 day';
    END IF;
  END IF;

  RETURN latest_date IS NULL OR latest_date < yesterday;
END;
$$ LANGUAGE plpgsql;

-- Function: Get symbols that need historical sync
CREATE OR REPLACE FUNCTION get_symbols_needing_sync(p_limit INTEGER DEFAULT 100)
RETURNS TABLE (
  symbol_id UUID,
  ticker VARCHAR(20),
  latest_date DATE,
  days_behind INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id as symbol_id,
    s.ticker,
    get_latest_historical_date(s.id, 'd1') as latest_date,
    (CURRENT_DATE - get_latest_historical_date(s.id, 'd1'))::INTEGER as days_behind
  FROM symbols s
  WHERE s.is_active = true
    AND is_historical_stale(s.id, 'd1')
  ORDER BY days_behind DESC NULLS FIRST
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION cleanup_stale_intraday() TO service_role;
GRANT EXECUTE ON FUNCTION get_latest_historical_date(UUID, VARCHAR(10)) TO authenticated;
GRANT EXECUTE ON FUNCTION is_historical_stale(UUID, VARCHAR(10)) TO authenticated;
GRANT EXECUTE ON FUNCTION get_symbols_needing_sync(INTEGER) TO authenticated;

-- Add comments
COMMENT ON FUNCTION cleanup_stale_intraday() IS 'Removes Tradier intraday data older than today';
COMMENT ON FUNCTION get_latest_historical_date(UUID, VARCHAR(10)) IS 'Returns the most recent Polygon historical date for a symbol';
COMMENT ON FUNCTION is_historical_stale(UUID, VARCHAR(10)) IS 'Checks if historical data is missing yesterday (accounting for weekends)';
COMMENT ON FUNCTION get_symbols_needing_sync(INTEGER) IS 'Returns symbols that need Polygon data sync, ordered by staleness';
