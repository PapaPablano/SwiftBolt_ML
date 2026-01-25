/**
 * AAPL Data Verification Script
 * Checks migration status and data integrity for AAPL
 * Run this in Supabase SQL Editor
 */

-- ============================================
-- 1. VERIFY MIGRATIONS AND SCHEMA
-- ============================================

-- Check enum values including h8 timeframe
SELECT
  enum_range(NULL::timeframe) AS all_timeframes,
  'Timeframe enum should include: m15, h1, h4, d1, h8, w1' AS expected;

-- Check key tables exist
SELECT
  table_name,
  CASE
    WHEN table_name IN ('ohlc_bars_v2', 'ml_forecasts_intraday', 'symbols') THEN 'EXISTS ✓'
    ELSE 'MISSING'
  END as status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('ohlc_bars_v2', 'ml_forecasts_intraday', 'symbols')
ORDER BY table_name;

-- ============================================
-- 2. AAPL SYMBOL METADATA
-- ============================================

SELECT
  id,
  ticker,
  description,
  asset_type,
  primary_source,
  created_at,
  'AAPL metadata loaded' AS status
FROM symbols
WHERE ticker = 'AAPL';

-- ============================================
-- 3. OHLC BARS V2 DATA COVERAGE
-- ============================================

-- Summary by timeframe with data freshness
SELECT
  timeframe,
  COUNT(*) as total_bars,
  MIN(ts)::date as earliest_date,
  MAX(ts) as latest_timestamp,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(ts))) / 3600)::int as hours_since_latest,
  STRING_AGG(DISTINCT provider, ', ' ORDER BY provider) as providers,
  COUNT(DISTINCT provider) as provider_count
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY timeframe
ORDER BY
  CASE timeframe
    WHEN 'm15' THEN 1
    WHEN 'h1' THEN 2
    WHEN 'h4' THEN 3
    WHEN 'd1' THEN 4
    WHEN 'h8' THEN 5
    WHEN 'w1' THEN 6
  END;

-- ============================================
-- 4. RECENT OHLC DATA (Last 10 bars per timeframe)
-- ============================================

-- H1 (1-hour) - Most recent data
SELECT
  'h1' as timeframe,
  ts,
  ROUND(open::numeric, 2) as open,
  ROUND(high::numeric, 2) as high,
  ROUND(low::numeric, 2) as low,
  ROUND(close::numeric, 2) as close,
  volume,
  provider,
  data_status
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'h1'
ORDER BY ts DESC
LIMIT 10;

-- D1 (daily) - Most recent data
SELECT
  'd1' as timeframe,
  ts,
  ROUND(open::numeric, 2) as open,
  ROUND(high::numeric, 2) as high,
  ROUND(low::numeric, 2) as low,
  ROUND(close::numeric, 2) as close,
  volume,
  provider,
  data_status
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
ORDER BY ts DESC
LIMIT 10;

-- ============================================
-- 5. ML INTRADAY FORECASTS
-- ============================================

-- Forecast summary by horizon
SELECT
  horizon,
  COUNT(*) as total_forecasts,
  COUNT(CASE WHEN expires_at > NOW() THEN 1 END) as active_forecasts,
  COUNT(CASE WHEN expires_at <= NOW() THEN 1 END) as expired_forecasts,
  MAX(created_at) as latest_forecast_time,
  MAX(expires_at) as latest_expiration
FROM ml_forecasts_intraday
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY horizon
ORDER BY
  CASE horizon
    WHEN '15m' THEN 1
    WHEN '1h' THEN 2
    WHEN '4h' THEN 3
    WHEN '8h' THEN 4
    WHEN '1D' THEN 5
  END;

-- Recent active forecasts (last 5 per horizon)
SELECT
  horizon,
  overall_label as direction,
  ROUND(confidence::numeric, 3) as confidence,
  ROUND(target_price::numeric, 2) as target_price,
  ROUND(current_price::numeric, 2) as current_price,
  ROUND(support::numeric, 2) as support_level,
  ROUND(resistance::numeric, 2) as resistance_level,
  created_at,
  expires_at,
  CASE
    WHEN expires_at > NOW() THEN 'ACTIVE'
    ELSE 'EXPIRED'
  END as status
FROM ml_forecasts_intraday
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND expires_at > (NOW() - INTERVAL '24 hours')
ORDER BY created_at DESC
LIMIT 20;

-- ============================================
-- 6. DATA QUALITY CHECKS
-- ============================================

-- Check for null/invalid values in critical columns
SELECT
  'OHLC Data Quality Check' as check_name,
  COUNT(*) as total_records,
  COUNT(CASE WHEN open IS NULL OR close IS NULL THEN 1 END) as null_values,
  COUNT(CASE WHEN volume < 0 THEN 1 END) as negative_volume,
  COUNT(CASE WHEN high < low THEN 1 END) as invalid_high_low,
  ROUND(100.0 * COUNT(CASE WHEN (open IS NOT NULL AND close IS NOT NULL AND volume >= 0) THEN 1 END) / COUNT(*), 2) as quality_percent
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL');

-- Check for duplicate bars
SELECT
  'Duplicate OHLC Records' as check_name,
  timeframe,
  ts,
  provider,
  COUNT(*) as count
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY timeframe, ts, provider
HAVING COUNT(*) > 1
ORDER BY count DESC;
