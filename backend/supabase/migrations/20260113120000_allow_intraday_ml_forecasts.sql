CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  IF NEW.provider = 'alpaca' THEN
    IF bar_date < today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca historical data cannot be marked as forecast';
      END IF;
    END IF;

    IF bar_date = today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca real-time data cannot be marked as forecast';
      END IF;
      IF NEW.is_intraday = false AND NEW.timeframe IN ('m1', 'm5', 'm15', 'm30', 'h1', 'h4') THEN
        RAISE EXCEPTION 'Alpaca intraday timeframes for today must be marked as intraday';
      END IF;
    END IF;

    IF bar_date > today_date AND NEW.is_forecast = false THEN
      RAISE EXCEPTION 'Alpaca cannot write to future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;

    RETURN NEW;
  END IF;

  IF NEW.provider IN ('yfinance', 'polygon', 'tradier') THEN
    RAISE EXCEPTION 'Provider % is DEPRECATED. Use provider=alpaca for all new OHLCV data. Legacy data is read-only.', NEW.provider;
  END IF;

  IF NEW.provider = 'ml_forecast' THEN
    IF NEW.is_forecast = false THEN
      RAISE EXCEPTION 'ML forecast provider must have is_forecast=true';
    END IF;

    IF NEW.is_intraday = true THEN
      RAISE EXCEPTION 'ML forecast data cannot be marked as intraday';
    END IF;

    IF NEW.timeframe IN ('m15', 'h1', 'h4') THEN
      IF bar_date < today_date THEN
        RAISE EXCEPTION 'ML intraday forecasts must be for today or future dates. Bar date: %, Today: %', bar_date, today_date;
      END IF;
    ELSE
      IF bar_date <= today_date THEN
        RAISE EXCEPTION 'ML forecast data must be for future dates only. Bar date: %, Today: %', bar_date, today_date;
      END IF;
    END IF;

    RETURN NEW;
  END IF;

  IF NEW.provider = 'finnhub' THEN
    RAISE EXCEPTION 'Finnhub provider is for news only, not OHLCV data. Use provider=alpaca for OHLCV.';
  END IF;

  RAISE EXCEPTION 'Unknown provider: %. Use provider=alpaca for OHLCV data.', NEW.provider;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_ohlc_v2_write_trigger ON ohlc_bars_v2;
CREATE TRIGGER validate_ohlc_v2_write_trigger
  BEFORE INSERT OR UPDATE ON ohlc_bars_v2
  FOR EACH ROW
  EXECUTE FUNCTION validate_ohlc_v2_write();

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
      AND o.provider IN ('alpaca', 'polygon', 'tradier', 'yfinance')
    ORDER BY o.ts DESC
    LIMIT p_max_bars
  ),
  forecast_data AS (
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
      AND o.is_forecast = true
      AND o.provider = 'ml_forecast'
      AND (
        (p_timeframe IN ('m15', 'h1', 'h4') AND DATE(o.ts AT TIME ZONE 'America/New_York') >= CURRENT_DATE)
        OR (p_timeframe NOT IN ('m15', 'h1', 'h4') AND DATE(o.ts AT TIME ZONE 'America/New_York') > CURRENT_DATE)
      )
    ORDER BY o.ts ASC
    LIMIT 2000
  )
  SELECT
    to_char(combined.bar_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    combined.open,
    combined.high,
    combined.low,
    combined.close,
    combined.volume,
    combined.provider,
    combined.is_intraday,
    combined.is_forecast,
    combined.data_status,
    combined.confidence_score,
    combined.upper_band,
    combined.lower_band
  FROM (
    SELECT * FROM recent_data
    UNION ALL
    SELECT * FROM forecast_data
  ) combined
  ORDER BY combined.bar_ts ASC;
END;
$$ LANGUAGE plpgsql;
