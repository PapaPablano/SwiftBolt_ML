-- Migration: Dynamic chart data query that fetches most recent data first
-- Problem: Fixed date ranges can miss recent data if there are gaps in historical data
-- Solution: Fetch from most recent available data backwards, ensuring latest bars always included

CREATE OR REPLACE FUNCTION get_chart_data_v2_dynamic(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_max_bars INT DEFAULT 1000,
  p_include_forecast BOOLEAN DEFAULT true
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
  RETURN QUERY
  WITH recent_data AS (
    -- Get historical + today's data, ordered by most recent first
    SELECT
      o.ts,
      o.open,
      o.high,
      o.low,
      o.close,
      o.volume,
      o.provider,
      o.is_intraday,
      o.is_forecast,
      o.data_status,
      o.confidence_score,
      o.upper_band,
      o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.is_forecast = false
      AND (
        -- Historical: any data before today from valid providers
        (DATE(o.ts) < CURRENT_DATE AND o.provider IN ('polygon', 'alpaca', 'yfinance'))
        OR
        -- Today: intraday data from tradier or alpaca
        (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider IN ('tradier', 'alpaca'))
      )
    ORDER BY o.ts DESC
    LIMIT p_max_bars
  ),
  forecast_data AS (
    -- Get forecast data if requested
    SELECT
      o.ts,
      o.open,
      o.high,
      o.low,
      o.close,
      o.volume,
      o.provider,
      o.is_intraday,
      o.is_forecast,
      o.data_status,
      o.confidence_score,
      o.upper_band,
      o.lower_band
    FROM ohlc_bars_v2 o
    WHERE p_include_forecast = true
      AND o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND DATE(o.ts) > CURRENT_DATE
      AND o.is_forecast = true
      AND o.provider = 'ml_forecast'
    ORDER BY o.ts ASC
    LIMIT 20
  )
  -- Combine and return in chronological order
  SELECT
    to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    open, high, low, close, volume, provider,
    is_intraday, is_forecast, data_status,
    confidence_score, upper_band, lower_band
  FROM (
    SELECT * FROM recent_data
    UNION ALL
    SELECT * FROM forecast_data
  ) combined
  ORDER BY ts ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2_dynamic(UUID, VARCHAR, INT, BOOLEAN) IS
'Returns chart data starting from most recent available data and working backwards.
This ensures the latest bars are always included regardless of historical data gaps.
- Fetches up to p_max_bars of historical + today data (most recent first)
- Optionally includes forecast data (future dates)
- Returns all data in chronological order (oldest to newest)
This approach is resilient to data gaps and always prioritizes recent data.';

-- Update the original function to use the new dynamic approach
CREATE OR REPLACE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP,
  p_end_date TIMESTAMP
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
  v_max_bars INT;
BEGIN
  -- Calculate approximate max bars based on timeframe and date range
  -- This ensures we get enough bars but prioritize recent data
  v_max_bars := CASE p_timeframe
    WHEN 'm15' THEN 2000  -- 15min: ~3 weeks of market hours
    WHEN 'h1' THEN 1500   -- 1h: ~2-3 months of market hours
    WHEN 'h4' THEN 1000   -- 4h: ~6 months
    WHEN 'd1' THEN 2000   -- Daily: ~8 years
    WHEN 'w1' THEN 2000   -- Weekly: ~38 years
    ELSE 1000
  END;

  -- Use the dynamic function which fetches from most recent backwards
  RETURN QUERY
  SELECT * FROM get_chart_data_v2_dynamic(
    p_symbol_id,
    p_timeframe,
    v_max_bars,
    true  -- include forecasts
  )
  WHERE 
    -- Apply date range filter after fetching recent data
    -- This ensures we get recent data even if start_date is far in the past
    ts::timestamp >= GREATEST(
      p_start_date,
      -- Don't go back more than reasonable for each timeframe
      CASE p_timeframe
        WHEN 'm15' THEN NOW() - INTERVAL '60 days'
        WHEN 'h1' THEN NOW() - INTERVAL '180 days'
        WHEN 'h4' THEN NOW() - INTERVAL '365 days'
        WHEN 'd1' THEN NOW() - INTERVAL '3650 days'
        WHEN 'w1' THEN NOW() - INTERVAL '7300 days'
        ELSE NOW() - INTERVAL '730 days'
      END
    )
    AND ts::timestamp <= p_end_date;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2(UUID, VARCHAR, TIMESTAMP, TIMESTAMP) IS
'Returns chart data with intelligent date range handling.
Fetches from most recent data backwards, then applies date range filter.
This ensures latest bars are always included even with large date ranges or data gaps.
Automatically limits lookback period per timeframe to prevent excessive data retrieval.';
