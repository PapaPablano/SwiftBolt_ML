-- Migration: Create ohlc_bars_v2 with data layering architecture
-- Purpose: Separate historical (Polygon), intraday (Tradier), and forecast (ML) data flows

-- Create the new versioned OHLC table
CREATE TABLE IF NOT EXISTS ohlc_bars_v2 (
  id BIGSERIAL PRIMARY KEY,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  timeframe VARCHAR(10) NOT NULL,
  ts TIMESTAMP NOT NULL,
  
  -- OHLCV data
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  
  -- Data source tracking
  provider VARCHAR(20) NOT NULL CHECK (provider IN ('polygon', 'tradier', 'ml_forecast')),
  is_intraday BOOLEAN DEFAULT false,
  is_forecast BOOLEAN DEFAULT false,
  data_status VARCHAR(20) CHECK (data_status IN ('verified', 'live', 'provisional')),
  
  -- Freshness tracking
  fetched_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  -- Confidence & metadata (for forecasts)
  confidence_score DECIMAL(3, 2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
  upper_band DECIMAL(10, 4),
  lower_band DECIMAL(10, 4),
  
  -- Unique constraint: one row per symbol/timeframe/timestamp/provider/forecast combination
  UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)
);

-- Indexes for efficient querying
CREATE INDEX idx_ohlc_v2_chart_query ON ohlc_bars_v2(symbol_id, timeframe, ts DESC);
CREATE INDEX idx_ohlc_v2_provider ON ohlc_bars_v2(provider, ts DESC);
CREATE INDEX idx_ohlc_v2_forecast ON ohlc_bars_v2(is_forecast, ts) WHERE is_forecast = true;
CREATE INDEX idx_ohlc_v2_intraday ON ohlc_bars_v2(is_intraday, ts) WHERE is_intraday = true;

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_ohlc_v2_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ohlc_v2_updated_at_trigger
  BEFORE UPDATE ON ohlc_bars_v2
  FOR EACH ROW
  EXECUTE FUNCTION update_ohlc_v2_updated_at();

-- Validation function: Enforce data layer separation rules
CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  -- Rule 1: Historical (Polygon) can only write to dates BEFORE today
  IF NEW.provider = 'polygon' THEN
    IF bar_date >= today_date THEN
      RAISE EXCEPTION 'Polygon historical data cannot write to today or future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_intraday = true THEN
      RAISE EXCEPTION 'Polygon historical data cannot be marked as intraday';
    END IF;
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'Polygon historical data cannot be marked as forecast';
    END IF;
  END IF;
  
  -- Rule 2: Intraday (Tradier) can only write to TODAY
  IF NEW.provider = 'tradier' THEN
    IF bar_date != today_date THEN
      RAISE EXCEPTION 'Tradier intraday data must be for today only. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_intraday = false THEN
      RAISE EXCEPTION 'Tradier data must be marked as intraday';
    END IF;
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'Tradier intraday data cannot be marked as forecast';
    END IF;
  END IF;
  
  -- Rule 3: Forecasts (ML) can only write to FUTURE dates
  IF NEW.provider = 'ml_forecast' THEN
    IF bar_date <= today_date THEN
      RAISE EXCEPTION 'ML forecasts must be for future dates only. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_forecast = false THEN
      RAISE EXCEPTION 'ML forecast data must be marked as forecast';
    END IF;
    IF NEW.is_intraday = true THEN
      RAISE EXCEPTION 'ML forecast data cannot be marked as intraday';
    END IF;
    -- Forecasts should have confidence bands
    IF NEW.upper_band IS NULL OR NEW.lower_band IS NULL THEN
      RAISE EXCEPTION 'ML forecasts must include upper_band and lower_band';
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ohlc_v2_validation_trigger
  BEFORE INSERT OR UPDATE ON ohlc_bars_v2
  FOR EACH ROW
  EXECUTE FUNCTION validate_ohlc_v2_write();

-- Function: Get chart data with proper layer separation
CREATE OR REPLACE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP,
  p_end_date TIMESTAMP
)
RETURNS TABLE (
  ts TIMESTAMP,
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

-- Function: Check if intraday data is locked (after market close)
CREATE OR REPLACE FUNCTION is_intraday_locked()
RETURNS BOOLEAN AS $$
DECLARE
  current_time_et TIMESTAMP;
  market_close_time TIMESTAMP;
  lock_time TIMESTAMP;
BEGIN
  -- Convert current time to ET (approximate - should use proper timezone in production)
  current_time_et := now() AT TIME ZONE 'America/New_York';
  
  -- Market closes at 4:00 PM ET
  market_close_time := DATE(current_time_et) + INTERVAL '16 hours';
  
  -- Lock 5 minutes after close (4:05 PM ET)
  lock_time := market_close_time + INTERVAL '5 minutes';
  
  RETURN current_time_et > lock_time;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON ohlc_bars_v2 TO authenticated;
GRANT SELECT, INSERT, UPDATE ON ohlc_bars_v2 TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ohlc_bars_v2_id_seq TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE ohlc_bars_v2_id_seq TO service_role;

-- Add comment for documentation
COMMENT ON TABLE ohlc_bars_v2 IS 'Versioned OHLC data with strict layer separation: historical (Polygon), intraday (Tradier), and forecasts (ML)';
COMMENT ON COLUMN ohlc_bars_v2.provider IS 'Data source: polygon (historical), tradier (intraday), ml_forecast (predictions)';
COMMENT ON COLUMN ohlc_bars_v2.is_intraday IS 'True if this is real-time intraday data aggregated to daily';
COMMENT ON COLUMN ohlc_bars_v2.is_forecast IS 'True if this is a ML forecast for future dates';
COMMENT ON COLUMN ohlc_bars_v2.data_status IS 'verified (historical/closed), live (market open), provisional (forecast)';
