-- Comprehensive diagnostic query to identify why charts show old data
-- Run this for AAPL to diagnose the issue shown in screenshots

-- 1. Check what data exists in the database for AAPL across all timeframes
WITH symbol_lookup AS (
  SELECT id, ticker FROM symbols WHERE ticker = 'AAPL'
),
data_summary AS (
  SELECT 
    s.ticker,
    ob.timeframe,
    ob.provider,
    COUNT(*) as total_bars,
    MIN(ob.ts) as oldest_bar,
    MAX(ob.ts) as newest_bar,
    MAX(ob.ts) FILTER (WHERE DATE(ob.ts) = CURRENT_DATE) as today_latest,
    MAX(ob.ts) FILTER (WHERE DATE(ob.ts) < CURRENT_DATE) as historical_latest,
    COUNT(*) FILTER (WHERE DATE(ob.ts) = CURRENT_DATE) as today_count,
    COUNT(*) FILTER (WHERE DATE(ob.ts) < CURRENT_DATE) as historical_count
  FROM ohlc_bars_v2 ob
  JOIN symbol_lookup s ON s.id = ob.symbol_id
  WHERE ob.is_forecast = false
  GROUP BY s.ticker, ob.timeframe, ob.provider
)
SELECT 
  ticker,
  timeframe,
  provider,
  total_bars,
  oldest_bar AT TIME ZONE 'UTC' as oldest_bar_utc,
  newest_bar AT TIME ZONE 'UTC' as newest_bar_utc,
  today_latest AT TIME ZONE 'UTC' as today_latest_utc,
  historical_latest AT TIME ZONE 'UTC' as historical_latest_utc,
  today_count,
  historical_count,
  CASE 
    WHEN newest_bar >= CURRENT_DATE THEN '✅ HAS TODAY DATA'
    WHEN newest_bar >= CURRENT_DATE - INTERVAL '1 day' THEN '⚠️ YESTERDAY'
    WHEN newest_bar >= CURRENT_DATE - INTERVAL '7 days' THEN '⚠️ LAST WEEK'
    ELSE '❌ STALE (>' || EXTRACT(DAY FROM CURRENT_DATE - DATE(newest_bar)) || ' days old)'
  END as data_status
FROM data_summary
ORDER BY timeframe, provider;

-- 2. Test what get_chart_data_v2_dynamic returns for each timeframe
\echo '\n=== Testing get_chart_data_v2_dynamic for h1 timeframe ==='
SELECT 
  ts,
  close,
  provider,
  is_intraday,
  ROW_NUMBER() OVER (ORDER BY ts DESC) as row_num
FROM get_chart_data_v2_dynamic(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1',
  1000,
  false
)
ORDER BY ts DESC
LIMIT 10;

\echo '\n=== Testing get_chart_data_v2_dynamic for d1 timeframe ==='
SELECT 
  ts,
  close,
  provider,
  is_intraday,
  ROW_NUMBER() OVER (ORDER BY ts DESC) as row_num
FROM get_chart_data_v2_dynamic(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'd1',
  1000,
  false
)
ORDER BY ts DESC
LIMIT 10;

-- 3. Check if the WHERE clause filters are excluding recent data
\echo '\n=== Checking what data the WHERE clause filters out ==='
WITH symbol_lookup AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL'
)
SELECT 
  timeframe,
  provider,
  DATE(ts) as bar_date,
  is_intraday,
  COUNT(*) as bars_on_date,
  MAX(ts) as latest_bar_time,
  CASE 
    WHEN DATE(ts) < CURRENT_DATE AND provider IN ('polygon', 'alpaca', 'yfinance') THEN '✅ INCLUDED (historical)'
    WHEN DATE(ts) = CURRENT_DATE AND is_intraday = true AND provider IN ('tradier', 'alpaca') THEN '✅ INCLUDED (today)'
    ELSE '❌ EXCLUDED by WHERE clause'
  END as filter_status
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbol_lookup)
  AND is_forecast = false
  AND timeframe IN ('h1', 'd1')
GROUP BY timeframe, provider, DATE(ts), is_intraday
ORDER BY timeframe, bar_date DESC
LIMIT 20;

-- 4. Check for timezone issues
\echo '\n=== Checking for timezone issues ==='
SELECT 
  timeframe,
  ts AT TIME ZONE 'UTC' as ts_utc,
  ts AT TIME ZONE 'America/New_York' as ts_et,
  DATE(ts) as date_utc,
  DATE(ts AT TIME ZONE 'America/New_York') as date_et,
  CURRENT_DATE as current_date_utc,
  CURRENT_DATE AT TIME ZONE 'America/New_York' as current_date_et,
  close,
  provider
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND is_forecast = false
  AND timeframe IN ('h1', 'd1')
ORDER BY ts DESC
LIMIT 10;
