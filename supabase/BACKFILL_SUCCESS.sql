-- Verify AAPL data is now current
-- Run this in Supabase SQL Editor

SELECT 
  timeframe,
  COUNT(*) as total_bars,
  MIN(ts) AT TIME ZONE 'UTC' as oldest_bar,
  MAX(ts) AT TIME ZONE 'UTC' as newest_bar,
  EXTRACT(HOUR FROM (NOW() - MAX(ts))) as hours_since_last_bar,
  CASE 
    WHEN MAX(ts) >= NOW() - INTERVAL '2 hours' THEN '✅ CURRENT'
    WHEN MAX(ts) >= NOW() - INTERVAL '1 day' THEN '⚠️ RECENT'
    ELSE '❌ STALE'
  END as status
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND provider = 'alpaca'
  AND is_forecast = false
GROUP BY timeframe
ORDER BY 
  CASE timeframe
    WHEN 'm15' THEN 1
    WHEN 'h1' THEN 2
    WHEN 'h4' THEN 3
    WHEN 'd1' THEN 4
    WHEN 'w1' THEN 5
  END;
