-- Migration: Simplify get_chart_data_v2 - Unified Approach for All Timeframes
-- Purpose: Remove intraday/historical distinction, treat all timeframes uniformly
-- Date: 2026-01-10
-- Rationale: With Alpaca, all timeframes use the same API - no need for special handling

-- ============================================================================
-- PROBLEM: Current function has complex branching logic for intraday vs daily
-- SOLUTION: Single unified query that works for ALL timeframes (m15, h1, h4, d1, w1)
-- ============================================================================

DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, TEXT, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, CHARACTER VARYING, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, timeframe, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;

CREATE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP WITH TIME ZONE,
  p_end_date TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
  ts TEXT,
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  provider VARCHAR(20),
  is_intraday BOOLEAN,
  is_forecast BOOLEAN,
  data_status VARCHAR(20),
  confidence_score DECIMAL(3, 2),
  upper_band DECIMAL(10, 4),
  lower_band DECIMAL(10, 4)
) AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
BEGIN
  -- UNIFIED QUERY: Works for ALL timeframes (m15, h1, h4, d1, w1)
  -- No special branching - Alpaca treats all timeframes the same way
  RETURN QUERY
  SELECT DISTINCT ON (o.ts)
    to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
    o.open,
    o.high,
    o.low,
    o.close,
    o.volume,
    o.provider,
    -- is_intraday flag: true if bar is from today (for client-side layer separation)
    (DATE(o.ts AT TIME ZONE 'America/New_York') = today_date)::BOOLEAN as is_intraday,
    o.is_forecast,
    o.data_status,
    o.confidence_score,
    o.upper_band,
    o.lower_band
  FROM ohlc_bars_v2 o
  WHERE o.symbol_id = p_symbol_id
    AND o.timeframe = p_timeframe
    AND o.ts >= p_start_date
    AND o.ts <= p_end_date
    AND (
      -- Historical + Today's data: Alpaca primary, legacy fallback
      (o.is_forecast = false AND o.provider IN ('alpaca', 'polygon', 'yfinance', 'tradier'))
      -- Future forecast data
      OR (o.is_forecast = true AND o.provider = 'ml_forecast')
    )
  ORDER BY o.ts ASC,
    -- Provider preference: Alpaca > Polygon > YFinance > Tradier
    CASE o.provider
      WHEN 'alpaca' THEN 1
      WHEN 'polygon' THEN 2
      WHEN 'yfinance' THEN 3
      WHEN 'tradier' THEN 4
      ELSE 5
    END ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2(uuid, character varying, timestamp with time zone, timestamp with time zone) IS
'Unified chart data query for ALL timeframes (SIMPLIFIED 2026-01-10).

KEY CHANGES:
- Removed intraday/historical branching logic
- Single query path for all timeframes (m15, h1, h4, d1, w1)
- is_intraday flag computed dynamically (today = true, else false)
- Alpaca is primary provider for all timeframes
- Legacy providers (polygon, yfinance, tradier) available as fallback

RATIONALE:
With Alpaca API, all timeframes work the same way - just different timeframe parameter.
No need for special "intraday" handling or separate query paths.

USAGE:
  SELECT * FROM get_chart_data_v2(
    (SELECT id FROM symbols WHERE ticker = ''AAPL''),
    ''m15'',  -- or ''h1'', ''h4'', ''d1'', ''w1''
    NOW() - INTERVAL ''7 days'',
    NOW() + INTERVAL ''1 day''
  );
';

-- ============================================================================
-- Verify the function was created successfully
-- ============================================================================
DO $$
DECLARE
  function_exists BOOLEAN;
BEGIN
  SELECT EXISTS(
    SELECT 1 FROM pg_proc
    WHERE proname = 'get_chart_data_v2'
  ) INTO function_exists;

  IF function_exists THEN
    RAISE NOTICE '✅ get_chart_data_v2() simplified successfully - unified for all timeframes';
  ELSE
    RAISE WARNING '❌ Function creation failed';
  END IF;
END $$;
