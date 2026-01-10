-- Migration: Fix get_chart_data_v2 to include Alpaca provider for intraday data
-- The function was hardcoded to only query 'polygon' provider, but we're now using Alpaca
-- Date: 2026-01-10

-- ============================================================================
-- Update get_chart_data_v2 to include Alpaca provider for intraday data
-- ============================================================================

DROP FUNCTION IF EXISTS get_chart_data_v2 CASCADE;

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
BEGIN
  -- For intraday timeframes (m15/h1/h4), query ohlc_bars_v2 from all valid providers
  IF p_timeframe IN ('m15', 'h1', 'h4') THEN
    RETURN QUERY
    WITH combined_data AS (
      -- Historical intraday from Alpaca or Polygon (ohlc_bars_v2)
      -- Include ALL data_status values (verified, live, provisional)
      -- Accept both 'alpaca' and 'polygon' providers for flexibility
      SELECT
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN as is_intraday,
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
        AND o.provider IN ('alpaca', 'polygon', 'tradier')  -- Accept all valid intraday providers
        AND o.is_forecast = false

      UNION ALL

      -- Today's real-time data from Tradier (intraday_bars) - only for m15
      SELECT
        ib.ts,
        ib.open::DECIMAL(10,4),
        ib.high::DECIMAL(10,4),
        ib.low::DECIMAL(10,4),
        ib.close::DECIMAL(10,4),
        ib.volume::BIGINT,
        'tradier'::VARCHAR(20) as provider,
        true::BOOLEAN as is_intraday,
        false::BOOLEAN as is_forecast,
        'live'::VARCHAR(20) as data_status,
        NULL::DECIMAL(3,2) as confidence_score,
        NULL::DECIMAL(10,4) as upper_band,
        NULL::DECIMAL(10,4) as lower_band
      FROM intraday_bars ib
      WHERE ib.symbol_id = p_symbol_id
        AND ib.timeframe = '15m'
        AND ib.ts >= p_start_date
        AND ib.ts <= p_end_date
        AND DATE(ib.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE
        AND p_timeframe = 'm15'
    )
    -- Deduplicate: prefer Polygon > Alpaca > Tradier per timestamp using DISTINCT ON
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
        WHEN 'polygon' THEN 1
        WHEN 'alpaca' THEN 2
        WHEN 'tradier' THEN 3
        ELSE 4
      END ASC;

  -- For daily/weekly timeframes (d1/w1), use DISTINCT ON for deduplication
  ELSE
    RETURN QUERY
    SELECT DISTINCT ON (o.ts)
      to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      o.open, o.high, o.low, o.close, o.volume, o.provider,
      o.is_intraday, o.is_forecast, o.data_status, o.confidence_score, o.upper_band, o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date AND o.ts <= p_end_date
      AND (
        -- Historical data from verified providers
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('polygon', 'alpaca', 'yfinance'))
        -- Today's intraday data
        OR (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider IN ('polygon', 'alpaca', 'tradier'))
        -- Future forecast data
        OR (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
      )
    ORDER BY o.ts ASC,
      CASE o.provider
        WHEN 'polygon' THEN 1
        WHEN 'alpaca' THEN 2
        WHEN 'yfinance' THEN 3
        ELSE 4
      END ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS
'Returns chart data with proper data source routing including Polygon, Alpaca, and Yahoo Finance.
Uses DISTINCT ON for efficient deduplication (avoids PostgREST 1000-row limit issues).
For intraday timeframes (m15/h1/h4):
  - Historical data: Queries ohlc_bars_v2 WHERE provider IN (polygon, alpaca, tradier)
  - Today data: Queries intraday_bars (Tradier real-time)
  - Deduplication priority: Polygon > Alpaca > Tradier
For daily/weekly timeframes (d1/w1):
  - Deduplication priority: Polygon > Alpaca > YFinance
Properly classifies is_intraday based on DATE(ts) = CURRENT_DATE.';
