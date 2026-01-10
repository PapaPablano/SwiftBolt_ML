-- Verify we have current data after backfill
-- Run this in Supabase SQL Editor

-- Check latest bars for each symbol and timeframe
SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bars,
  MAX(o.ts) as latest_bar,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) / 3600, 1) as hours_old,
  CASE 
    WHEN MAX(o.ts) >= NOW() - INTERVAL '24 hours' THEN '✅ Current'
    WHEN MAX(o.ts) >= NOW() - INTERVAL '7 days' THEN '⚠️ Week old'
    ELSE '❌ Stale'
  END as status
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')
  AND o.provider = 'alpaca'  -- Only Alpaca data
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, 
  CASE o.timeframe 
    WHEN 'm15' THEN 1 
    WHEN 'h1' THEN 2 
    WHEN 'h4' THEN 3 
    WHEN 'd1' THEN 4 
    WHEN 'w1' THEN 5 
  END;

-- Summary: How many symbols have current data?
SELECT 
  'Current Data Status' as metric,
  COUNT(DISTINCT s.ticker) as total_symbols,
  COUNT(DISTINCT CASE WHEN MAX(o.ts) >= NOW() - INTERVAL '24 hours' THEN s.ticker END) as current_symbols,
  COUNT(DISTINCT CASE WHEN MAX(o.ts) < NOW() - INTERVAL '7 days' THEN s.ticker END) as stale_symbols
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.provider = 'alpaca'
GROUP BY s.ticker;
