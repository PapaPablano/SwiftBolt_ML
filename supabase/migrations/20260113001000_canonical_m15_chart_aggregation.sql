CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_m15_symbol_ts
  ON ohlc_bars_v2(symbol_id, ts DESC)
  WHERE timeframe = 'm15' AND is_forecast = false;

CREATE OR REPLACE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMPTZ,
  p_end_date TIMESTAMPTZ
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
  IF p_timeframe = 'm15' THEN
    RETURN QUERY
    WITH m15_dedup AS (
      SELECT DISTINCT ON (o.ts)
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN AS is_intraday,
        false::BOOLEAN AS is_forecast,
        o.data_status,
        NULL::DECIMAL(3, 2) AS confidence_score,
        NULL::DECIMAL(10, 4) AS upper_band,
        NULL::DECIMAL(10, 4) AS lower_band
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id
        AND o.timeframe = 'm15'
        AND o.is_forecast = false
        AND o.ts >= p_start_date
        AND o.ts <= p_end_date
        AND o.provider IN ('alpaca', 'polygon', 'yfinance', 'tradier')
      ORDER BY o.ts ASC,
        CASE o.provider
          WHEN 'alpaca' THEN 1
          WHEN 'polygon' THEN 2
          WHEN 'yfinance' THEN 3
          WHEN 'tradier' THEN 4
          ELSE 5
        END ASC,
        o.fetched_at DESC NULLS LAST,
        o.updated_at DESC NULLS LAST,
        o.id DESC
    )
    SELECT
      to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      d.open, d.high, d.low, d.close,
      COALESCE(d.volume, 0)::BIGINT,
      d.provider::VARCHAR(20),
      d.is_intraday,
      d.is_forecast,
      COALESCE(d.data_status, 'verified')::VARCHAR(20),
      d.confidence_score,
      d.upper_band,
      d.lower_band
    FROM m15_dedup d
    ORDER BY d.ts ASC;

  ELSIF p_timeframe IN ('h1', 'h4') THEN
    RETURN QUERY
    WITH m15_dedup AS (
      SELECT DISTINCT ON (o.ts)
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        COALESCE(o.volume, 0)::BIGINT AS volume,
        o.provider
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id
        AND o.timeframe = 'm15'
        AND o.is_forecast = false
        AND o.ts >= p_start_date
        AND o.ts <= p_end_date
        AND o.provider IN ('alpaca', 'polygon', 'yfinance', 'tradier')
      ORDER BY o.ts ASC,
        CASE o.provider
          WHEN 'alpaca' THEN 1
          WHEN 'polygon' THEN 2
          WHEN 'yfinance' THEN 3
          WHEN 'tradier' THEN 4
          ELSE 5
        END ASC,
        o.fetched_at DESC NULLS LAST,
        o.updated_at DESC NULLS LAST,
        o.id DESC
    ),
    bucketed AS (
      SELECT
        CASE
          WHEN p_timeframe = 'h1' THEN date_trunc('hour', ts)
          ELSE date_trunc('day', ts) + (FLOOR(EXTRACT(HOUR FROM ts) / 4) * INTERVAL '4 hours')
        END AS bucket_ts,
        ts,
        open,
        high,
        low,
        close,
        volume,
        provider
      FROM m15_dedup
    ),
    agg AS (
      SELECT
        b.bucket_ts,
        (array_agg(b.open ORDER BY b.ts ASC))[1]::DECIMAL(10,4) AS open,
        MAX(b.high)::DECIMAL(10,4) AS high,
        MIN(b.low)::DECIMAL(10,4) AS low,
        (array_agg(b.close ORDER BY b.ts DESC))[1]::DECIMAL(10,4) AS close,
        SUM(b.volume)::BIGINT AS volume,
        CASE
          WHEN bool_or(b.provider = 'alpaca') THEN 'alpaca'
          WHEN bool_or(b.provider = 'polygon') THEN 'polygon'
          WHEN bool_or(b.provider = 'yfinance') THEN 'yfinance'
          WHEN bool_or(b.provider = 'tradier') THEN 'tradier'
          ELSE 'unknown'
        END::VARCHAR(20) AS provider
      FROM bucketed b
      GROUP BY b.bucket_ts
    )
    SELECT
      to_char(a.bucket_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      a.open,
      a.high,
      a.low,
      a.close,
      COALESCE(a.volume, 0)::BIGINT,
      a.provider,
      (DATE(a.bucket_ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN AS is_intraday,
      false::BOOLEAN AS is_forecast,
      CASE
        WHEN DATE(a.bucket_ts AT TIME ZONE 'America/New_York') = CURRENT_DATE THEN 'live'
        ELSE 'verified'
      END::VARCHAR(20) AS data_status,
      NULL::DECIMAL(3,2) AS confidence_score,
      NULL::DECIMAL(10,4) AS upper_band,
      NULL::DECIMAL(10,4) AS lower_band
    FROM agg a
    ORDER BY a.bucket_ts ASC;

  ELSE
    RETURN QUERY
    SELECT DISTINCT ON (o.ts)
      to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      o.open,
      o.high,
      o.low,
      o.close,
      COALESCE(o.volume, 0)::BIGINT,
      o.provider::VARCHAR(20),
      (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN AS is_intraday,
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
        (o.is_forecast = false AND o.provider IN ('alpaca', 'polygon', 'yfinance', 'tradier'))
        OR (o.is_forecast = true AND o.provider = 'ml_forecast')
      )
    ORDER BY o.ts ASC,
      CASE o.provider
        WHEN 'alpaca' THEN 1
        WHEN 'polygon' THEN 2
        WHEN 'yfinance' THEN 3
        WHEN 'tradier' THEN 4
        WHEN 'ml_forecast' THEN 5
        ELSE 6
      END ASC,
      o.fetched_at DESC NULLS LAST,
      o.updated_at DESC NULLS LAST,
      o.id DESC;
  END IF;
END;
$$ LANGUAGE plpgsql;
