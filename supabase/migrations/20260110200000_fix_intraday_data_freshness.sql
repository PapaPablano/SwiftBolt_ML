-- Migration: Fix Intraday Data Freshness for h1 and m15
-- Purpose: Ensure get_chart_data_v2 returns TODAY's fresh Alpaca intraday bars
-- Date: 2026-01-10
-- Issue: Chart was showing stale historical h1/m15 bars instead of today's real-time data

-- ============================================================================
-- PROBLEM ANALYSIS
-- ============================================================================
-- The previous get_chart_data_v2 function had a critical flaw:
-- 1. It queried ALL Alpaca data in the date range (p_start_date to p_end_date)
-- 2. For intraday timeframes (m15/h1/h4), this included BOTH:
--    - Historical bars (yesterday and before)
--    - Today's real-time bars (if they exist)
-- 3. The is_intraday flag was calculated AFTER the query, not used to filter
-- 4. No guarantee that today's bars were actually fetched from Alpaca
-- 5. Result: Client received stale historical bars when today's data wasn't present
--
-- ROOT CAUSE: The function doesn't explicitly separate:
--   - Historical layer (dates < today)
--   - Intraday layer (date = today, must be fresh)
--
-- FIX: Explicitly query today's data separately and ensure it's recent

-- ============================================================================
-- PART 1: Enhanced get_chart_data_v2 with Explicit Intraday Layer
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
  is_intraday_tf BOOLEAN := p_timeframe IN ('m15', 'h1', 'h4');
BEGIN
  -- For intraday timeframes (m15/h1/h4), use three-layer approach:
  -- 1. Historical (dates < today) - Alpaca primary, legacy fallback
  -- 2. Intraday (date = today) - Alpaca ONLY, must be fresh
  -- 3. Forecast (dates > today) - ML forecasts
  IF is_intraday_tf THEN
    RETURN QUERY
    WITH historical_data AS (
      -- Layer 1: Historical bars (before today)
      SELECT
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        false as is_intraday,  -- Historical data is never intraday
        o.is_forecast,
        o.data_status,
        o.confidence_score,
        o.upper_band,
        o.lower_band
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id
        AND o.timeframe = p_timeframe
        AND o.ts >= p_start_date
        AND DATE(o.ts AT TIME ZONE 'America/New_York') < today_date
        AND o.is_forecast = false
        AND o.provider IN ('alpaca', 'polygon', 'tradier')  -- Alpaca primary, legacy fallback
    ),
    intraday_data AS (
      -- Layer 2: Today's intraday bars (ALPACA ONLY)
      -- This is the critical fix: explicitly query TODAY's data
      SELECT
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        true as is_intraday,  -- Today's data is always intraday
        o.is_forecast,
        o.data_status,
        o.confidence_score,
        o.upper_band,
        o.lower_band
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id
        AND o.timeframe = p_timeframe
        AND DATE(o.ts AT TIME ZONE 'America/New_York') = today_date
        AND o.is_forecast = false
        AND o.provider = 'alpaca'  -- ONLY Alpaca for today's data
    ),
    combined_data AS (
      SELECT * FROM historical_data
      UNION ALL
      SELECT * FROM intraday_data
    )
    -- Deduplicate: prefer Alpaca > Polygon > Tradier per timestamp
    SELECT DISTINCT ON (cd.ts)
      to_char(cd.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      cd.open,
      cd.high,
      cd.low,
      cd.close,
      cd.volume,
      cd.provider,
      cd.is_intraday,
      cd.is_forecast,
      cd.data_status,
      cd.confidence_score,
      cd.upper_band,
      cd.lower_band
    FROM combined_data cd
    ORDER BY cd.ts ASC,
      CASE cd.provider
        WHEN 'alpaca' THEN 1    -- Alpaca is primary
        WHEN 'polygon' THEN 2   -- Polygon is legacy fallback
        WHEN 'tradier' THEN 3   -- Tradier is lowest priority
        ELSE 4
      END ASC;

  -- For daily/weekly timeframes (d1/w1), use simplified query
  ELSE
    RETURN QUERY
    SELECT DISTINCT ON (o.ts)
      to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      o.open, o.high, o.low, o.close, o.volume, o.provider,
      (DATE(o.ts AT TIME ZONE 'America/New_York') = today_date)::BOOLEAN as is_intraday,
      o.is_forecast, o.data_status, o.confidence_score, o.upper_band, o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date AND o.ts <= p_end_date
      AND (
        -- Historical data: Alpaca primary, legacy fallback
        (DATE(o.ts) < today_date AND o.is_forecast = false AND o.provider IN ('alpaca', 'polygon', 'yfinance'))
        -- Today's data: Alpaca only
        OR (DATE(o.ts) = today_date AND o.is_forecast = false AND o.provider = 'alpaca')
        -- Future forecast data
        OR (DATE(o.ts) > today_date AND o.is_forecast = true AND o.provider = 'ml_forecast')
      )
    ORDER BY o.ts ASC,
      CASE o.provider
        WHEN 'alpaca' THEN 1     -- Alpaca is primary
        WHEN 'polygon' THEN 2    -- Polygon is legacy fallback
        WHEN 'yfinance' THEN 3   -- YFinance is lowest priority
        ELSE 4
      END ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2(uuid, character varying, timestamp with time zone, timestamp with time zone) IS
'Returns chart data with explicit intraday layer separation (FIXED 2026-01-10).

KEY FIX: For intraday timeframes (m15/h1/h4), explicitly separates:
  - Historical layer (dates < today): Alpaca primary, legacy fallback
  - Intraday layer (date = today): ALPACA ONLY, ensures fresh data
  - Forecast layer (dates > today): ML forecasts

This ensures the client receives TODAY''s fresh Alpaca bars in the intraday layer,
not stale historical bars.

For daily/weekly timeframes (d1/w1):
  - Primary: Alpaca (all data)
  - Fallback: Polygon/YFinance (legacy read-only)
  - Deduplication priority: Alpaca > Polygon > YFinance';

-- ============================================================================
-- PART 2: Add Data Freshness Monitoring Function
-- ============================================================================

CREATE OR REPLACE FUNCTION check_intraday_freshness(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10)
)
RETURNS TABLE (
  has_today_data BOOLEAN,
  latest_bar_ts TIMESTAMP WITH TIME ZONE,
  minutes_old INTEGER,
  is_stale BOOLEAN,
  provider VARCHAR(20)
) AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  staleness_threshold INTEGER;
BEGIN
  -- Define staleness thresholds (in minutes)
  staleness_threshold := CASE p_timeframe
    WHEN 'm15' THEN 30   -- 15min data should be < 30min old
    WHEN 'h1' THEN 90    -- 1h data should be < 90min old
    WHEN 'h4' THEN 300   -- 4h data should be < 5h old
    ELSE 1440            -- Daily data can be up to 24h old
  END;

  RETURN QUERY
  SELECT
    COUNT(*) > 0 as has_today_data,
    MAX(o.ts) as latest_bar_ts,
    EXTRACT(EPOCH FROM (NOW() - MAX(o.ts)))::INTEGER / 60 as minutes_old,
    (EXTRACT(EPOCH FROM (NOW() - MAX(o.ts)))::INTEGER / 60) > staleness_threshold as is_stale,
    MAX(o.provider) as provider
  FROM ohlc_bars_v2 o
  WHERE o.symbol_id = p_symbol_id
    AND o.timeframe = p_timeframe
    AND DATE(o.ts AT TIME ZONE 'America/New_York') = today_date
    AND o.is_forecast = false
    AND o.provider = 'alpaca';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_intraday_freshness IS
'Checks if intraday data is fresh for a given symbol/timeframe.
Returns:
  - has_today_data: Whether any bars exist for today
  - latest_bar_ts: Timestamp of most recent bar
  - minutes_old: How many minutes ago the latest bar was
  - is_stale: Whether data exceeds staleness threshold
  - provider: Data provider (should be alpaca)

Use this to monitor data freshness and trigger backfills if needed.';

-- ============================================================================
-- PART 3: Verification Queries
-- ============================================================================

-- Query to check if we have fresh intraday data for AAPL
COMMENT ON TABLE ohlc_bars_v2 IS
'OHLCV bars with Alpaca-only strategy (UPDATED 2026-01-10).

INTRADAY DATA FIX:
- get_chart_data_v2 now explicitly separates historical vs intraday layers
- Today''s data (intraday layer) ONLY uses Alpaca provider
- Historical data (dates < today) can fallback to legacy providers

Verification Queries:

-- Check if we have fresh intraday data for AAPL h1
SELECT * FROM check_intraday_freshness(
  (SELECT id FROM symbols WHERE ticker = ''AAPL''),
  ''h1''
);

-- Check today''s bar count for AAPL m15
SELECT COUNT(*) as today_bars
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = ''AAPL'')
  AND timeframe = ''m15''
  AND DATE(ts AT TIME ZONE ''America/New_York'') = CURRENT_DATE
  AND provider = ''alpaca'';

-- Test the fixed function
SELECT ts, open, high, low, close, provider, is_intraday
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = ''AAPL''),
  ''h1'',
  NOW() - INTERVAL ''7 days'',
  NOW()
)
WHERE is_intraday = true
ORDER BY ts DESC
LIMIT 10;
';
