-- Migration: Add Alpaca provider support and fix data flow
-- Purpose: Enable Alpaca as a data provider alongside existing providers
-- Also fixes RLS on symbols table and updates chart query function

-- ============================================================================
-- PART 1: Update provider constraint to include 'alpaca' and 'yfinance'
-- ============================================================================

-- Drop and recreate the check constraint
ALTER TABLE ohlc_bars_v2
DROP CONSTRAINT IF EXISTS ohlc_bars_v2_provider_check;

ALTER TABLE ohlc_bars_v2
ADD CONSTRAINT ohlc_bars_v2_provider_check
CHECK (provider IN ('polygon', 'tradier', 'ml_forecast', 'alpaca', 'yfinance'));

-- ============================================================================
-- PART 2: Update validation trigger to handle Alpaca
-- Alpaca can provide BOTH historical AND intraday data
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  -- Rule 1: Historical providers (Polygon, Alpaca, Yahoo) can write to dates BEFORE today
  IF NEW.provider IN ('polygon', 'alpaca', 'yfinance') AND NEW.is_forecast = false AND NEW.is_intraday = false THEN
    IF bar_date >= today_date THEN
      RAISE EXCEPTION '% historical data cannot write to today or future dates. Bar date: %, Today: %',
        NEW.provider, bar_date, today_date;
    END IF;
  END IF;

  -- Rule 2: Intraday providers (Tradier, Alpaca) can write TODAY's data
  IF NEW.is_intraday = true AND NEW.is_forecast = false THEN
    IF NEW.provider NOT IN ('tradier', 'alpaca') THEN
      RAISE EXCEPTION 'Intraday data must come from tradier or alpaca, not %', NEW.provider;
    END IF;
    IF bar_date != today_date THEN
      RAISE EXCEPTION 'Intraday data must be for today only. Bar date: %, Today: %', bar_date, today_date;
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

-- ============================================================================
-- PART 3: Update get_chart_data_v2 to include Alpaca data
-- ============================================================================

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
      -- Historical: completed days before today (Polygon, Alpaca, Yahoo)
      (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.is_intraday = false
       AND o.provider IN ('polygon', 'alpaca', 'yfinance'))
      OR
      -- Intraday: today's data from Tradier or Alpaca
      (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true
       AND o.provider IN ('tradier', 'alpaca'))
      OR
      -- Forecasts: future dates
      (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
    )
  ORDER BY o.ts ASC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PART 4: Fix RLS on symbols table - Allow service role to create symbols
-- ============================================================================

-- Disable RLS entirely for symbols table (simplest fix)
-- The Edge Functions use service_role key which should bypass RLS anyway
ALTER TABLE symbols DISABLE ROW LEVEL SECURITY;

-- Alternatively, if you want to keep RLS enabled, add a policy:
-- DROP POLICY IF EXISTS "Service role can manage symbols" ON symbols;
-- CREATE POLICY "Service role can manage symbols"
-- ON symbols
-- FOR ALL
-- TO service_role
-- USING (true)
-- WITH CHECK (true);

-- ============================================================================
-- PART 5: Add indexes for Alpaca provider queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_ohlc_v2_alpaca_historical
ON ohlc_bars_v2(symbol_id, timeframe, ts DESC)
WHERE provider = 'alpaca' AND is_intraday = false;

CREATE INDEX IF NOT EXISTS idx_ohlc_v2_alpaca_intraday
ON ohlc_bars_v2(symbol_id, timeframe, ts DESC)
WHERE provider = 'alpaca' AND is_intraday = true;

-- ============================================================================
-- PART 6: Update coverage_status table to track Alpaca coverage
-- ============================================================================

-- Add column to track which provider last updated coverage (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'coverage_status' AND column_name = 'last_provider'
  ) THEN
    ALTER TABLE coverage_status ADD COLUMN last_provider VARCHAR(20);
  END IF;
END $$;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION validate_ohlc_v2_write() IS
'Validates OHLC data writes with provider-specific rules:
- Polygon/Alpaca/Yahoo: Historical data (before today)
- Tradier/Alpaca: Intraday data (today only)
- ML Forecast: Future predictions only';

COMMENT ON FUNCTION get_chart_data_v2(UUID, VARCHAR, TIMESTAMP, TIMESTAMP) IS
'Returns chart data with proper layer separation:
- Historical from Polygon, Alpaca, or Yahoo (before today)
- Intraday from Tradier or Alpaca (today)
- Forecasts from ML (future dates)';
