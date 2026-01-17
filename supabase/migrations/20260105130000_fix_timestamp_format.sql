-- Fix timestamp format in get_chart_data_v2 to include timezone indicator
-- This fixes Swift ISO8601 parsing errors

-- Drop the existing function first since we're changing the return type
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
  SELECT 
    to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
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
  ORDER BY o.ts ASC;
END;
$$ LANGUAGE plpgsql;
