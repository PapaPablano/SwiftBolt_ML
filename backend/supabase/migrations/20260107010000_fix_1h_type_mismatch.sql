-- Migration: Fix 1h aggregation type mismatch in get_chart_data_v2
-- Problem: intraday_bars uses DOUBLE PRECISION, but RETURNS TABLE declares DECIMAL(10,4)
-- The 1h aggregation must explicitly cast to match the return signature

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
DECLARE
  v_is_intraday_tf BOOLEAN;
BEGIN
  -- Determine if this is an intraday timeframe request
  v_is_intraday_tf := p_timeframe IN ('15m', '1h', '4h');

  IF v_is_intraday_tf THEN
    -- Query intraday_bars table for 15m/1h/4h timeframes
    IF p_timeframe = '15m' THEN
      -- Direct 15m bars
      RETURN QUERY
      SELECT 
        to_char(ib.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
        ib.open::DECIMAL(10,4) AS open,
        ib.high::DECIMAL(10,4) AS high,
        ib.low::DECIMAL(10,4) AS low,
        ib.close::DECIMAL(10,4) AS close,
        ib.volume::BIGINT AS volume,
        'tradier'::VARCHAR(20) AS provider,
        true AS is_intraday,
        false AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM intraday_bars ib
      WHERE ib.symbol_id = p_symbol_id
        AND ib.timeframe = '15m'
        AND ib.ts >= p_start_date
        AND ib.ts <= p_end_date
      ORDER BY ib.ts ASC;
      
    ELSIF p_timeframe = '1h' THEN
      -- Aggregate 15m bars to 1h with explicit type casts
      RETURN QUERY
      WITH hourly_agg AS (
        SELECT 
          date_trunc('hour', ib.ts) AS hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1]::DOUBLE PRECISION AS open,
          MAX(ib.high)::DOUBLE PRECISION AS high,
          MIN(ib.low)::DOUBLE PRECISION AS low,
          (array_agg(ib.close ORDER BY ib.ts DESC))[1]::DOUBLE PRECISION AS close,
          SUM(ib.volume)::BIGINT AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id
          AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date
          AND ib.ts <= p_end_date
        GROUP BY date_trunc('hour', ib.ts)
      )
      SELECT 
        to_char(ha.hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT AS ts,
        ha.open::DECIMAL(10,4) AS open,
        ha.high::DECIMAL(10,4) AS high,
        ha.low::DECIMAL(10,4) AS low,
        ha.close::DECIMAL(10,4) AS close,
        ha.volume::BIGINT AS volume,
        'tradier'::VARCHAR(20) AS provider,
        true::BOOLEAN AS is_intraday,
        false::BOOLEAN AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM hourly_agg ha
      ORDER BY ha.hour_ts ASC;
      
    ELSIF p_timeframe = '4h' THEN
      -- Aggregate 15m bars to 4h with explicit type casts
      RETURN QUERY
      WITH four_hour_agg AS (
        SELECT 
          date_trunc('day', ib.ts) + 
            (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours') AS four_hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1]::DOUBLE PRECISION AS open,
          MAX(ib.high)::DOUBLE PRECISION AS high,
          MIN(ib.low)::DOUBLE PRECISION AS low,
          (array_agg(ib.close ORDER BY ib.ts DESC))[1]::DOUBLE PRECISION AS close,
          SUM(ib.volume)::BIGINT AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id
          AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date
          AND ib.ts <= p_end_date
        GROUP BY date_trunc('day', ib.ts) + 
          (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours')
      )
      SELECT 
        to_char(fha.four_hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT AS ts,
        fha.open::DECIMAL(10,4) AS open,
        fha.high::DECIMAL(10,4) AS high,
        fha.low::DECIMAL(10,4) AS low,
        fha.close::DECIMAL(10,4) AS close,
        fha.volume::BIGINT AS volume,
        'tradier'::VARCHAR(20) AS provider,
        true::BOOLEAN AS is_intraday,
        false::BOOLEAN AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM four_hour_agg fha
      ORDER BY fha.four_hour_ts ASC;
    END IF;
    
  ELSE
    -- Query ohlc_bars_v2 for daily/weekly timeframes (original logic)
    RETURN QUERY
    WITH deduplicated AS (
      SELECT 
        o.*,
        ROW_NUMBER() OVER (
          PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday 
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
          -- Intraday: today's data from Tradier (aggregated daily)
          (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
          OR
          -- Forecasts: future dates
          (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
        )
    )
    SELECT 
      to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT AS ts,
      d.open::DECIMAL(10,4) AS open,
      d.high::DECIMAL(10,4) AS high,
      d.low::DECIMAL(10,4) AS low,
      d.close::DECIMAL(10,4) AS close,
      d.volume::BIGINT AS volume,
      d.provider::VARCHAR(20) AS provider,
      d.is_intraday::BOOLEAN AS is_intraday,
      d.is_forecast::BOOLEAN AS is_forecast,
      d.data_status::VARCHAR(20) AS data_status,
      d.confidence_score::DECIMAL(3,2) AS confidence_score,
      d.upper_band::DECIMAL(10,4) AS upper_band,
      d.lower_band::DECIMAL(10,4) AS lower_band
    FROM deduplicated d
    WHERE d.rn = 1
    ORDER BY d.ts ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS 
'Returns chart data with proper timeframe routing and explicit type casting:
- 15m/1h/4h: Queries intraday_bars table, aggregates as needed, casts DOUBLE PRECISION → DECIMAL(10,4)
- 1d/1w: Queries ohlc_bars_v2 with layer separation (yfinance > polygon > tradier > ml_forecast)';
