-- Complete Alpaca Database Support Migration
-- Purpose: Ensure all database constraints, triggers, and functions support Alpaca provider
-- Date: 2026-01-09
-- Related: ALPACA_OPTIMIZATION_SUMMARY.md

-- ============================================================================
-- PART 1: Update Provider Constraint
-- ============================================================================

-- Drop existing constraint
ALTER TABLE ohlc_bars_v2 DROP CONSTRAINT IF EXISTS ohlc_bars_v2_provider_check;

-- Add new constraint with alpaca included
ALTER TABLE ohlc_bars_v2 ADD CONSTRAINT ohlc_bars_v2_provider_check 
CHECK (provider IN ('alpaca', 'yfinance', 'polygon', 'tradier', 'ml_forecast'));

COMMENT ON CONSTRAINT ohlc_bars_v2_provider_check ON ohlc_bars_v2 IS 
'Allowed data providers (priority order):
- alpaca: Primary provider for historical and real-time data (preferred)
- yfinance: Free historical data (fallback)
- polygon: Historical data via Massive API (fallback)
- tradier: Real-time intraday data (fallback)
- ml_forecast: ML-generated forecasts';

-- ============================================================================
-- PART 2: Update Validation Trigger for Alpaca Rules
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  -- Rule 1: Alpaca can write to ANY date (historical, intraday, or today)
  -- Alpaca is the primary provider with full coverage
  IF NEW.provider = 'alpaca' THEN
    -- Alpaca can write historical data (before today)
    IF bar_date < today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca historical data cannot be marked as forecast';
      END IF;
      -- Alpaca historical can be daily or intraday
    END IF;
    
    -- Alpaca can write today's data (real-time)
    IF bar_date = today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca real-time data cannot be marked as forecast';
      END IF;
      -- Today's data should be marked as intraday
      IF NEW.is_intraday = false AND NEW.timeframe IN ('m1', 'm5', 'm15', 'm30', 'h1', 'h4') THEN
        RAISE EXCEPTION 'Alpaca intraday timeframes for today must be marked as intraday';
      END IF;
    END IF;
    
    -- Alpaca cannot write future dates
    IF bar_date > today_date THEN
      RAISE EXCEPTION 'Alpaca cannot write to future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
  END IF;

  -- Rule 2: YFinance can write historical data (before today)
  IF NEW.provider = 'yfinance' THEN
    IF bar_date >= today_date THEN
      RAISE EXCEPTION 'YFinance historical data cannot write to today or future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'YFinance historical data cannot be marked as forecast';
    END IF;
    -- YFinance typically provides daily data, but can have intraday historical
  END IF;

  -- Rule 3: Polygon can write historical data (before today)
  IF NEW.provider = 'polygon' THEN
    IF bar_date >= today_date THEN
      RAISE EXCEPTION 'Polygon historical data cannot write to today or future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'Polygon historical data cannot be marked as forecast';
    END IF;
    -- Polygon can write historical intraday bars
  END IF;

  -- Rule 4: Tradier can only write to TODAY (real-time intraday)
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

  -- Rule 5: ML Forecasts can only write to FUTURE dates
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

COMMENT ON FUNCTION validate_ohlc_v2_write IS
'Validates data layer separation rules:
- Alpaca: Historical and real-time data (primary provider, all timeframes)
- YFinance: Historical data for dates BEFORE today (fallback)
- Polygon: Historical data (including intraday) for dates BEFORE today (fallback)
- Tradier: Real-time intraday data for TODAY only (fallback)
- ML: Forecasts for FUTURE dates only';

-- ============================================================================
-- PART 3: Helper Functions for Alpaca Monitoring
-- ============================================================================

-- Function: Get provider usage statistics
CREATE OR REPLACE FUNCTION get_provider_usage_stats(
  p_days INTEGER DEFAULT 7
)
RETURNS TABLE (
  provider VARCHAR(20),
  total_bars BIGINT,
  unique_symbols BIGINT,
  date_range_start DATE,
  date_range_end DATE,
  avg_bars_per_symbol NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    o.provider,
    COUNT(*) as total_bars,
    COUNT(DISTINCT o.symbol_id) as unique_symbols,
    MIN(DATE(o.ts)) as date_range_start,
    MAX(DATE(o.ts)) as date_range_end,
    ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT o.symbol_id), 0), 2) as avg_bars_per_symbol
  FROM ohlc_bars_v2 o
  WHERE o.fetched_at > NOW() - INTERVAL '1 day' * p_days
  GROUP BY o.provider
  ORDER BY total_bars DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_provider_usage_stats IS
'Returns provider usage statistics for monitoring Alpaca adoption.
Use to verify Alpaca is being used as primary provider.';

-- Function: Check Alpaca data quality
CREATE OR REPLACE FUNCTION check_alpaca_data_quality(
  p_symbol_ticker VARCHAR(10),
  p_timeframe VARCHAR(10) DEFAULT 'd1'
)
RETURNS TABLE (
  date DATE,
  alpaca_bars INTEGER,
  other_provider_bars INTEGER,
  alpaca_percentage NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH daily_counts AS (
    SELECT 
      DATE(o.ts) as bar_date,
      COUNT(*) FILTER (WHERE o.provider = 'alpaca') as alpaca_count,
      COUNT(*) FILTER (WHERE o.provider != 'alpaca') as other_count
    FROM ohlc_bars_v2 o
    JOIN symbols s ON o.symbol_id = s.id
    WHERE s.ticker = p_symbol_ticker
      AND o.timeframe = p_timeframe
      AND o.is_forecast = false
      AND DATE(o.ts) >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE(o.ts)
  )
  SELECT 
    bar_date as date,
    alpaca_count::INTEGER as alpaca_bars,
    other_count::INTEGER as other_provider_bars,
    ROUND(
      (alpaca_count::NUMERIC / NULLIF(alpaca_count + other_count, 0)) * 100, 
      2
    ) as alpaca_percentage
  FROM daily_counts
  ORDER BY bar_date DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_alpaca_data_quality IS
'Checks what percentage of data is coming from Alpaca vs other providers.
Use to verify Alpaca prioritization is working correctly.';

-- Function: Get Alpaca coverage report
CREATE OR REPLACE FUNCTION get_alpaca_coverage_report()
RETURNS TABLE (
  symbol_ticker VARCHAR(10),
  timeframe VARCHAR(10),
  total_bars BIGINT,
  alpaca_bars BIGINT,
  alpaca_coverage_pct NUMERIC,
  latest_alpaca_date DATE,
  data_gap_days INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    s.ticker as symbol_ticker,
    o.timeframe,
    COUNT(*) as total_bars,
    COUNT(*) FILTER (WHERE o.provider = 'alpaca') as alpaca_bars,
    ROUND(
      (COUNT(*) FILTER (WHERE o.provider = 'alpaca')::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
      2
    ) as alpaca_coverage_pct,
    MAX(DATE(o.ts)) FILTER (WHERE o.provider = 'alpaca') as latest_alpaca_date,
    (CURRENT_DATE - MAX(DATE(o.ts)) FILTER (WHERE o.provider = 'alpaca'))::INTEGER as data_gap_days
  FROM ohlc_bars_v2 o
  JOIN symbols s ON o.symbol_id = s.id
  WHERE o.is_forecast = false
    AND DATE(o.ts) >= CURRENT_DATE - INTERVAL '90 days'
  GROUP BY s.ticker, o.timeframe
  HAVING COUNT(*) FILTER (WHERE o.provider = 'alpaca') > 0
  ORDER BY alpaca_coverage_pct DESC, s.ticker, o.timeframe;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_alpaca_coverage_report IS
'Generates a coverage report showing which symbols/timeframes have Alpaca data.
Use to identify gaps in Alpaca coverage and verify migration progress.';

-- ============================================================================
-- PART 4: Update Table Comments
-- ============================================================================

COMMENT ON TABLE ohlc_bars_v2 IS 
'OHLC bars with multi-provider support and layer separation.
Supported providers (priority order):
- alpaca: Primary provider for historical and real-time data (preferred)
- yfinance: Free historical data (fallback)
- polygon: Historical data via Massive API (fallback)
- tradier: Real-time intraday data (fallback)
- ml_forecast: ML-generated forecasts

Data Layer Rules:
- Historical (< today): alpaca > yfinance > polygon
- Intraday (= today): alpaca > tradier
- Forecast (> today): ml_forecast only';

-- ============================================================================
-- PART 5: Create Monitoring View
-- ============================================================================

CREATE OR REPLACE VIEW v_alpaca_health AS
SELECT 
  'Provider Distribution' as metric_name,
  json_build_object(
    'alpaca', COUNT(*) FILTER (WHERE provider = 'alpaca'),
    'yfinance', COUNT(*) FILTER (WHERE provider = 'yfinance'),
    'polygon', COUNT(*) FILTER (WHERE provider = 'polygon'),
    'tradier', COUNT(*) FILTER (WHERE provider = 'tradier'),
    'ml_forecast', COUNT(*) FILTER (WHERE provider = 'ml_forecast')
  ) as metric_value,
  'Last 24 hours' as time_window
FROM ohlc_bars_v2
WHERE fetched_at > NOW() - INTERVAL '24 hours'

UNION ALL

SELECT 
  'Alpaca Coverage %' as metric_name,
  json_build_object(
    'percentage', ROUND(
      (COUNT(*) FILTER (WHERE provider = 'alpaca')::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
      2
    )
  ) as metric_value,
  'Last 24 hours' as time_window
FROM ohlc_bars_v2
WHERE fetched_at > NOW() - INTERVAL '24 hours'
  AND is_forecast = false

UNION ALL

SELECT 
  'Alpaca Symbols Active' as metric_name,
  json_build_object(
    'count', COUNT(DISTINCT symbol_id)
  ) as metric_value,
  'Last 24 hours' as time_window
FROM ohlc_bars_v2
WHERE provider = 'alpaca'
  AND fetched_at > NOW() - INTERVAL '24 hours';

COMMENT ON VIEW v_alpaca_health IS
'Real-time health metrics for Alpaca integration.
Use for monitoring dashboards and alerting.';

-- Grant permissions on new functions
GRANT EXECUTE ON FUNCTION get_provider_usage_stats TO authenticated;
GRANT EXECUTE ON FUNCTION check_alpaca_data_quality TO authenticated;
GRANT EXECUTE ON FUNCTION get_alpaca_coverage_report TO authenticated;
GRANT SELECT ON v_alpaca_health TO authenticated;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Run these queries after migration to verify Alpaca support:

-- 1. Verify provider constraint includes alpaca
-- SELECT conname, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conrelid = 'ohlc_bars_v2'::regclass 
-- AND conname = 'ohlc_bars_v2_provider_check';

-- 2. Check provider distribution
-- SELECT * FROM get_provider_usage_stats(7);

-- 3. Verify Alpaca data is being stored
-- SELECT provider, COUNT(*) 
-- FROM ohlc_bars_v2 
-- WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
-- GROUP BY provider;

-- 4. Check Alpaca health metrics
-- SELECT * FROM v_alpaca_health;
