-- Migration: Fix intraday layer classification in get_chart_data_v2
-- Problem: All m15/h1/h4 bars are marked is_intraday=true, causing historical data to appear in wrong layer
-- Solution: Set is_intraday based on DATE(ts) = CURRENT_DATE

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
  IF p_timeframe IN ('m15', 'h1', 'h4') THEN
    IF p_timeframe = 'm15' THEN
      RETURN QUERY
      SELECT to_char(ib.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
        ib.open::DECIMAL(10,4), ib.high::DECIMAL(10,4), ib.low::DECIMAL(10,4), ib.close::DECIMAL(10,4),
        ib.volume::BIGINT, 'tradier'::VARCHAR(20), 
        (DATE(ib.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN,  -- Fix: dynamic is_intraday
        false::BOOLEAN, 'verified'::VARCHAR(20),
        NULL::DECIMAL(3,2), NULL::DECIMAL(10,4), NULL::DECIMAL(10,4)
      FROM intraday_bars ib
      WHERE ib.symbol_id = p_symbol_id AND ib.timeframe = '15m'
        AND ib.ts >= p_start_date AND ib.ts <= p_end_date
      ORDER BY ib.ts ASC;
    ELSIF p_timeframe = 'h1' THEN
      RETURN QUERY
      WITH hourly_agg AS (
        SELECT date_trunc('hour', ib.ts) AS hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1] AS open, MAX(ib.high) AS high,
          MIN(ib.low) AS low, (array_agg(ib.close ORDER BY ib.ts DESC))[1] AS close,
          SUM(ib.volume)::BIGINT AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date AND ib.ts <= p_end_date
        GROUP BY date_trunc('hour', ib.ts)
      )
      SELECT to_char(ha.hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
        ha.open::DECIMAL(10,4), ha.high::DECIMAL(10,4), ha.low::DECIMAL(10,4), ha.close::DECIMAL(10,4),
        ha.volume, 'tradier'::VARCHAR(20), 
        (DATE(ha.hour_ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN,  -- Fix: dynamic is_intraday
        false::BOOLEAN, 'verified'::VARCHAR(20),
        NULL::DECIMAL(3,2), NULL::DECIMAL(10,4), NULL::DECIMAL(10,4)
      FROM hourly_agg ha ORDER BY ha.hour_ts ASC;
    ELSIF p_timeframe = 'h4' THEN
      RETURN QUERY
      WITH four_hour_agg AS (
        SELECT date_trunc('day', ib.ts) + (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours') AS four_hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1] AS open, MAX(ib.high) AS high,
          MIN(ib.low) AS low, (array_agg(ib.close ORDER BY ib.ts DESC))[1] AS close,
          SUM(ib.volume)::BIGINT AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date AND ib.ts <= p_end_date
        GROUP BY date_trunc('day', ib.ts) + (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours')
      )
      SELECT to_char(fha.four_hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
        fha.open::DECIMAL(10,4), fha.high::DECIMAL(10,4), fha.low::DECIMAL(10,4), fha.close::DECIMAL(10,4),
        fha.volume, 'tradier'::VARCHAR(20), 
        (DATE(fha.four_hour_ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN,  -- Fix: dynamic is_intraday
        false::BOOLEAN, 'verified'::VARCHAR(20),
        NULL::DECIMAL(3,2), NULL::DECIMAL(10,4), NULL::DECIMAL(10,4)
      FROM four_hour_agg fha ORDER BY fha.four_hour_ts ASC;
    END IF;
  ELSE
    RETURN QUERY
    WITH deduplicated AS (
      SELECT o.*, ROW_NUMBER() OVER (
        PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday
        ORDER BY CASE WHEN o.provider = 'yfinance' THEN 1 WHEN o.provider = 'polygon' THEN 2 ELSE 3 END,
        o.ts DESC, o.fetched_at DESC NULLS LAST
      ) as rn
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id AND o.timeframe = p_timeframe
        AND o.ts >= p_start_date AND o.ts <= p_end_date
        AND ((DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('yfinance', 'polygon'))
          OR (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
          OR (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast'))
    )
    SELECT to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      d.open, d.high, d.low, d.close, d.volume, d.provider,
      d.is_intraday, d.is_forecast, d.data_status, d.confidence_score, d.upper_band, d.lower_band
    FROM deduplicated d WHERE d.rn = 1 ORDER BY d.ts ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS
'Returns chart data with proper layer classification.
Fixed: is_intraday now based on DATE(ts) = CURRENT_DATE for m15/h1/h4 timeframes.
Historical intraday bars (before today) will have is_intraday=false.
Today''s intraday bars will have is_intraday=true.
Accepts m15/h1/h4 for intraday, d1/w1 for daily/weekly.';
