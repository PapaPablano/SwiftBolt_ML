-- Migration: Alpaca-Only Data Provider Strategy
-- Purpose: Consolidate all OHLCV data to Alpaca as single source of truth
-- Date: 2026-01-10
-- Related: Alpaca-only migration to simplify provider architecture

-- ============================================================================
-- PART 1: Update Provider Constraint to Deprecate Legacy Providers
-- ============================================================================

-- Drop existing constraint
ALTER TABLE ohlc_bars_v2 DROP CONSTRAINT IF EXISTS ohlc_bars_v2_provider_check;

-- Add new constraint - Alpaca is primary, keep legacy for historical data
ALTER TABLE ohlc_bars_v2 ADD CONSTRAINT ohlc_bars_v2_provider_check 
CHECK (provider IN ('alpaca', 'finnhub', 'polygon', 'yfinance', 'tradier', 'ml_forecast'));

COMMENT ON CONSTRAINT ohlc_bars_v2_provider_check ON ohlc_bars_v2 IS 
'Allowed data providers (Alpaca-only strategy):
- alpaca: PRIMARY provider for all OHLCV data (historical + real-time)
- finnhub: News only (no OHLCV)
- polygon: DEPRECATED - legacy historical data only (no new inserts)
- yfinance: DEPRECATED - legacy historical data only (no new inserts)
- tradier: DEPRECATED - legacy intraday data only (no new inserts)
- ml_forecast: ML-generated forecasts

New data MUST use alpaca provider. Legacy providers kept for historical data only.';

-- ============================================================================
-- PART 2: Update Validation Trigger for Alpaca-First Strategy
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  -- Rule 1: Alpaca is the ONLY provider allowed for new OHLCV data
  -- All new bars MUST use provider='alpaca'
  IF NEW.provider = 'alpaca' THEN
    -- Alpaca can write historical data (before today)
    IF bar_date < today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca historical data cannot be marked as forecast';
      END IF;
    END IF;
    
    -- Alpaca can write today's data (real-time)
    IF bar_date = today_date THEN
      IF NEW.is_forecast = true THEN
        RAISE EXCEPTION 'Alpaca real-time data cannot be marked as forecast';
      END IF;
      -- Today's data should be marked as intraday for intraday timeframes
      IF NEW.is_intraday = false AND NEW.timeframe IN ('m1', 'm5', 'm15', 'm30', 'h1', 'h4') THEN
        RAISE EXCEPTION 'Alpaca intraday timeframes for today must be marked as intraday';
      END IF;
    END IF;
    
    -- Alpaca cannot write future dates (except forecasts)
    IF bar_date > today_date AND NEW.is_forecast = false THEN
      RAISE EXCEPTION 'Alpaca cannot write to future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    
    RETURN NEW; -- Allow Alpaca writes
  END IF;

  -- Rule 2: DEPRECATED providers - block all new writes
  -- These providers are read-only for legacy data
  IF NEW.provider IN ('yfinance', 'polygon', 'tradier') THEN
    RAISE EXCEPTION 'Provider % is DEPRECATED. Use provider=alpaca for all new OHLCV data. Legacy data is read-only.', NEW.provider;
  END IF;

  -- Rule 3: ML Forecasts can only write to FUTURE dates
  IF NEW.provider = 'ml_forecast' THEN
    IF bar_date <= today_date THEN
      RAISE EXCEPTION 'ML forecast data must be for future dates only. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_forecast = false THEN
      RAISE EXCEPTION 'ML forecast provider must have is_forecast=true';
    END IF;
    RETURN NEW; -- Allow ML forecast writes
  END IF;

  -- Rule 4: Finnhub is for news only, not OHLCV
  IF NEW.provider = 'finnhub' THEN
    RAISE EXCEPTION 'Finnhub provider is for news only, not OHLCV data. Use provider=alpaca for OHLCV.';
  END IF;

  -- Default: reject unknown providers
  RAISE EXCEPTION 'Unknown provider: %. Use provider=alpaca for OHLCV data.', NEW.provider;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_ohlc_v2_write IS
'Validates OHLCV writes with Alpaca-only strategy.
- NEW data MUST use provider=alpaca
- Legacy providers (polygon, yfinance, tradier) are READ-ONLY
- ML forecasts allowed for future dates only
- Finnhub blocked for OHLCV (news only)';

-- Recreate trigger
DROP TRIGGER IF EXISTS validate_ohlc_v2_write_trigger ON ohlc_bars_v2;
CREATE TRIGGER validate_ohlc_v2_write_trigger
  BEFORE INSERT OR UPDATE ON ohlc_bars_v2
  FOR EACH ROW
  EXECUTE FUNCTION validate_ohlc_v2_write();

-- ============================================================================
-- PART 3: Update get_chart_data_v2 to Simplify Provider Logic
-- ============================================================================

DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, TEXT, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, CHARACTER VARYING, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, timeframe, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;

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
  -- Alpaca-only strategy: Query alpaca provider first, fallback to legacy if needed
  -- For intraday timeframes (m15/h1/h4), include today's real-time data
  IF p_timeframe IN ('m15', 'h1', 'h4') THEN
    RETURN QUERY
    WITH combined_data AS (
      -- Historical + today's data from Alpaca (primary)
      SELECT
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN as is_intraday,
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
        AND o.provider = 'alpaca'  -- Alpaca-only for new data
        AND o.is_forecast = false

      UNION ALL

      -- Legacy data from deprecated providers (read-only)
      SELECT
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN as is_intraday,
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
        AND o.provider IN ('polygon', 'tradier')  -- Legacy providers
        AND o.is_forecast = false
        AND NOT EXISTS (
          -- Only use legacy if Alpaca doesn't have this timestamp
          SELECT 1 FROM ohlc_bars_v2 o2
          WHERE o2.symbol_id = o.symbol_id
            AND o2.timeframe = o.timeframe
            AND o2.ts = o.ts
            AND o2.provider = 'alpaca'
        )
    )
    -- Deduplicate: prefer Alpaca > Polygon > Tradier per timestamp
    SELECT DISTINCT ON (cd.ts)
      to_char(cd.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      cd.open,
      cd.high,
      cd.low,
      cd.close,
      cd.volume,
      cd.provider,
      cd.is_intraday,
      cd.is_forecast,
      cd.data_status,
      cd.confidence_score,
      cd.upper_band,
      cd.lower_band
    FROM combined_data cd
    ORDER BY cd.ts ASC,
      CASE cd.provider
        WHEN 'alpaca' THEN 1    -- Alpaca is primary
        WHEN 'polygon' THEN 2   -- Polygon is legacy fallback
        WHEN 'tradier' THEN 3   -- Tradier is lowest priority
        ELSE 4
      END ASC;

  -- For daily/weekly timeframes (d1/w1), use simplified query
  ELSE
    RETURN QUERY
    SELECT DISTINCT ON (o.ts)
      to_char(o.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      o.open, o.high, o.low, o.close, o.volume, o.provider,
      o.is_intraday, o.is_forecast, o.data_status, o.confidence_score, o.upper_band, o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date AND o.ts <= p_end_date
      AND (
        -- Historical data: Alpaca primary, legacy fallback
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('alpaca', 'polygon', 'yfinance'))
        -- Today's intraday data: Alpaca only
        OR (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'alpaca')
        -- Future forecast data
        OR (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
      )
    ORDER BY o.ts ASC,
      CASE o.provider
        WHEN 'alpaca' THEN 1     -- Alpaca is primary
        WHEN 'polygon' THEN 2    -- Polygon is legacy fallback
        WHEN 'yfinance' THEN 3   -- YFinance is lowest priority
        ELSE 4
      END ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2(uuid, character varying, timestamp with time zone, timestamp with time zone) IS
'Returns chart data with Alpaca-only strategy (legacy providers as fallback).
Uses DISTINCT ON for efficient deduplication.
For intraday timeframes (m15/h1/h4):
  - Primary: Alpaca (all data)
  - Fallback: Polygon/Tradier (legacy read-only)
  - Deduplication priority: Alpaca > Polygon > Tradier
For daily/weekly timeframes (d1/w1):
  - Primary: Alpaca (all data)
  - Fallback: Polygon/YFinance (legacy read-only)
  - Deduplication priority: Alpaca > Polygon > YFinance
Properly classifies is_intraday based on DATE(ts) = CURRENT_DATE.';

-- ============================================================================
-- PART 4: Create Migration Audit Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS provider_migration_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  migration_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  old_provider VARCHAR(20),
  new_provider VARCHAR(20),
  symbol_id UUID,
  timeframe VARCHAR(10),
  bar_count INTEGER,
  earliest_ts TIMESTAMP WITH TIME ZONE,
  latest_ts TIMESTAMP WITH TIME ZONE,
  notes TEXT
);

COMMENT ON TABLE provider_migration_audit IS
'Audit log for provider migration from Polygon/YFinance to Alpaca.
Tracks which data was migrated and when.';

-- Log existing provider distribution (before migration)
INSERT INTO provider_migration_audit (old_provider, symbol_id, timeframe, bar_count, earliest_ts, latest_ts, notes)
SELECT 
  provider as old_provider,
  symbol_id,
  timeframe,
  COUNT(*) as bar_count,
  MIN(ts) as earliest_ts,
  MAX(ts) as latest_ts,
  'Pre-migration snapshot' as notes
FROM ohlc_bars_v2
WHERE provider IN ('polygon', 'yfinance', 'tradier')
  AND is_forecast = false
GROUP BY provider, symbol_id, timeframe;

-- ============================================================================
-- PART 5: Create Helper Views for Monitoring
-- ============================================================================

CREATE OR REPLACE VIEW provider_coverage_summary AS
SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bar_count,
  MIN(o.ts) as earliest_bar,
  MAX(o.ts) as latest_bar,
  MAX(o.fetched_at) as last_updated
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE o.is_forecast = false
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, o.timeframe, 
  CASE o.provider 
    WHEN 'alpaca' THEN 1 
    WHEN 'polygon' THEN 2 
    WHEN 'yfinance' THEN 3 
    ELSE 4 
  END;

COMMENT ON VIEW provider_coverage_summary IS
'Summary view showing data coverage by provider.
Use this to monitor Alpaca migration progress and identify gaps.';

-- ============================================================================
-- PART 6: Success Metrics
-- ============================================================================

-- Query to check migration progress
COMMENT ON TABLE ohlc_bars_v2 IS
'OHLCV bars with Alpaca-only strategy (as of 2026-01-10).

Migration Status:
- NEW data MUST use provider=alpaca
- Legacy providers (polygon, yfinance, tradier) are READ-ONLY
- Use provider_coverage_summary view to monitor migration

Success Criteria:
1. All new bars in last 24h have provider=alpaca
2. No new inserts with provider IN (polygon, yfinance, tradier)
3. Chart queries return alpaca data as primary source

Verification Queries:
-- Check recent inserts (should be 100% alpaca)
SELECT provider, COUNT(*) FROM ohlc_bars_v2 
WHERE created_at > NOW() - INTERVAL ''24 hours'' 
GROUP BY provider;

-- Check provider distribution
SELECT * FROM provider_coverage_summary WHERE ticker = ''AAPL'';
';
