-- Add Alpaca as a supported data provider
-- Alpaca provides high-quality market data with 7+ years of history
-- Documentation: https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data

-- Update get_chart_data_v2 to include Alpaca in provider preference order
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
        -- Provider preference order: alpaca > yfinance > polygon > tradier
        -- Alpaca has best data quality and coverage
        ORDER BY 
          CASE 
            WHEN o.provider = 'alpaca' THEN 1
            WHEN o.provider = 'yfinance' THEN 2
            WHEN o.provider = 'polygon' THEN 3
            WHEN o.provider = 'tradier' THEN 4
            ELSE 5
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
        -- Historical: completed days before today (prefer alpaca, fallback to yfinance/polygon)
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('alpaca', 'yfinance', 'polygon'))
        OR
        -- Intraday: today's data from Alpaca or Tradier
        (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider IN ('alpaca', 'tradier'))
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
Provider preference: alpaca > yfinance > polygon for historical data.
Alpaca provides high-quality data with excellent coverage and reliability.
Returns one bar per day: most recent timestamp, prioritizing alpaca provider.';

-- Add index on provider column for better query performance
CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_provider 
ON ohlc_bars_v2(provider, symbol_id, timeframe, ts);

-- Add comment documenting Alpaca integration
COMMENT ON TABLE ohlc_bars_v2 IS 
'OHLC bars with multi-provider support and layer separation.
Supported providers:
- alpaca: Primary provider for historical and real-time data (preferred)
- yfinance: Free historical data (fallback)
- polygon: Historical data via Massive API (fallback)
- tradier: Real-time intraday data
- ml_forecast: ML-generated forecasts';
