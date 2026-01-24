-- Check data ingestion status for AAPL
-- This will show us what data exists and identify gaps

WITH symbol_lookup AS (
  SELECT id, ticker FROM symbols WHERE ticker = 'AAPL'
),
data_by_timeframe AS (
  SELECT 
    s.ticker,
    ob.timeframe,
    ob.provider,
    COUNT(*) as total_bars,
    MIN(ob.ts) as oldest_bar,
    MAX(ob.ts) as newest_bar,
    MAX(ob.ts) FILTER (WHERE DATE(ob.ts) >= CURRENT_DATE - INTERVAL '7 days') as last_week,
    MAX(ob.ts) FILTER (WHERE DATE(ob.ts) >= CURRENT_DATE - INTERVAL '30 days') as last_month,
    COUNT(*) FILTER (WHERE DATE(ob.ts) >= CURRENT_DATE - INTERVAL '7 days') as bars_last_week,
    COUNT(*) FILTER (WHERE DATE(ob.ts) >= CURRENT_DATE - INTERVAL '30 days') as bars_last_month
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
  EXTRACT(DAY FROM (NOW() - newest_bar)) as days_since_last_bar,
  bars_last_week,
  bars_last_month,
  CASE 
    WHEN newest_bar >= NOW() - INTERVAL '2 days' THEN '✅ CURRENT'
    WHEN newest_bar >= NOW() - INTERVAL '7 days' THEN '⚠️ RECENT (within week)'
    WHEN newest_bar >= NOW() - INTERVAL '30 days' THEN '⚠️ OLD (within month)'
    WHEN newest_bar >= NOW() - INTERVAL '180 days' THEN '❌ STALE (within 6 months)'
    ELSE '❌ VERY STALE (>6 months)'
  END as status
FROM data_by_timeframe
ORDER BY timeframe, provider;

-- Check for any recent data ingestion jobs
SELECT 
  'Recent backfill jobs:' as info,
  COUNT(*) as job_count,
  MAX(created_at) as last_job
FROM backfill_jobs
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND created_at >= NOW() - INTERVAL '7 days';

-- Check if there are any pending or running jobs
SELECT 
  'Job status summary:' as info,
  status,
  COUNT(*) as count
FROM backfill_jobs
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY status;
