-- Fix duplicate daily bars by selecting only one bar per day
-- For d1 timeframe, we should only return the most recent bar for each date

DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP, TIMESTAMP);

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
BEGIN
  RETURN QUERY
  WITH deduplicated AS (
    SELECT 
      o.*,
      ROW_NUMBER() OVER (
        PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday 
        ORDER BY o.ts DESC, o.fetched_at DESC NULLS LAST
      ) as rn
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date
      AND o.ts <= p_end_date
      AND (
        -- Historical: completed days before today
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider = 'polygon')
        OR
        -- Intraday: today's data from Tradier
        (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
        OR
        -- Forecasts: future dates
        (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
      )
  )
  SELECT 
    to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
    d.open,
    d.high,
    d.low,
    d.close,
    d.volume,
    d.provider,
    d.is_intraday,
    d.is_forecast,
    d.data_status,
    d.confidence_score,
    d.upper_band,
    d.lower_band
  FROM deduplicated d
  WHERE d.rn = 1  -- Only take the most recent bar per day
  ORDER BY d.ts ASC;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining the deduplication logic
COMMENT ON FUNCTION get_chart_data_v2 IS 
'Returns chart data with proper layer separation and deduplication.
For daily (d1) timeframe, only returns one bar per day (the most recent).
This prevents duplicate bars from causing chart rendering issues.';
