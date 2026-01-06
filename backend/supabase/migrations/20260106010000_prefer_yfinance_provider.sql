-- Update get_chart_data_v2 to prefer Yahoo Finance over Polygon
-- Yahoo Finance has better data quality

DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE);

CREATE OR REPLACE FUNCTION get_chart_data_v2(
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
  RETURN QUERY
  WITH deduplicated AS (
    SELECT 
      o.*,
      ROW_NUMBER() OVER (
        PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday 
        -- Prefer yfinance over polygon for historical data
        ORDER BY 
          CASE 
            WHEN o.provider = 'yfinance' THEN 1
            WHEN o.provider = 'polygon' THEN 2
            ELSE 3
          END,
          o.ts DESC, 
          o.fetched_at DESC NULLS LAST
      ) as rn
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date
      AND o.ts <= p_end_date
      AND (
        -- Historical: completed days before today (prefer yfinance, fallback to polygon)
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('yfinance', 'polygon'))
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
  WHERE d.rn = 1
  ORDER BY d.ts ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS 
'Returns chart data with proper layer separation and deduplication.
Prefers yfinance over polygon for historical data (better quality).
Returns one bar per day: most recent timestamp, prioritizing yfinance provider.';
