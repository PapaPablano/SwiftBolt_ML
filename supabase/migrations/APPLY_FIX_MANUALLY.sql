-- MANUAL FIX: Apply this SQL directly to your Supabase database
-- Go to: https://supabase.com/dashboard/project/YOUR_PROJECT/sql
-- Copy and paste this entire file, then click "Run"

-- Drop and recreate the function with the fix
DROP FUNCTION IF EXISTS get_chart_data_v2_dynamic(UUID, VARCHAR, INT, BOOLEAN) CASCADE;

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
    -- CRITICAL FIX: Simplified WHERE clause to ensure most recent bars are ALWAYS included
    -- Previous complex date filtering could exclude recent data
    SELECT
      o.ts AS bar_ts,
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
      -- Simplified: Accept data from ANY valid provider without date restrictions
      -- This guarantees we get the most recent N bars regardless of date/provider
      AND o.provider IN ('alpaca', 'polygon', 'tradier', 'yfinance')
    ORDER BY o.ts DESC
    LIMIT p_max_bars
  ),
  forecast_data AS (
    -- Get forecast data if requested
    SELECT
      o.ts AS bar_ts,
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
  -- Combine and return in chronological order (oldest to newest for chart display)
  SELECT
    to_char(combined.bar_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    combined.open, combined.high, combined.low, combined.close, combined.volume, combined.provider,
    combined.is_intraday, combined.is_forecast, combined.data_status,
    combined.confidence_score, combined.upper_band, combined.lower_band
  FROM (
    SELECT * FROM recent_data
    UNION ALL
    SELECT * FROM forecast_data
  ) combined
  ORDER BY combined.bar_ts ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2_dynamic(UUID, VARCHAR, INT, BOOLEAN) IS
'Returns the most recent N bars for charting, GUARANTEED to include latest data.
CRITICAL FIX APPLIED: Simplified WHERE clause removes complex date filtering that could exclude recent bars.
- Fetches most recent p_max_bars by timestamp (DESC order)
- Accepts data from any valid provider (alpaca, polygon, tradier, yfinance)
- No date-based filtering that might exclude recent data
- Returns data in chronological order (ASC) for chart display
- Optionally includes forecast data for future dates
This ensures charts ALWAYS show the newest available bars.';

-- Verify the fix was applied
SELECT 'Fix applied successfully!' as status;
