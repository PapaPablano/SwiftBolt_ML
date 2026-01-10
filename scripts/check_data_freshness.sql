-- Check data freshness for all watchlist symbols
-- Run this in Supabase SQL Editor

SELECT 
  s.ticker,
  o.timeframe,
  COUNT(*) as total_bars,
  MIN(o.ts) as earliest_bar,
  MAX(o.ts) as latest_bar,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) / 3600) as hours_since_latest,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) / 86400) as days_since_latest,
  STRING_AGG(DISTINCT o.provider, ', ' ORDER BY o.provider) as providers,
  CASE 
    WHEN o.timeframe IN ('m15', 'h1', 'h4') AND EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) > 86400 
      THEN '⚠️ STALE (>24h)'
    WHEN o.timeframe = 'd1' AND EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) > 172800 
      THEN '⚠️ STALE (>48h)'
    WHEN o.timeframe = 'w1' AND EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) > 604800 
      THEN '⚠️ STALE (>7d)'
    ELSE '✓ Fresh'
  END as status
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;

-- Summary
WITH latest_bars AS (
  SELECT 
    s.ticker,
    MAX(o.ts) as latest_ts
  FROM watchlist_items wi
  JOIN symbols s ON s.id = wi.symbol_id
  LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
  GROUP BY s.ticker
)
SELECT 
  'SUMMARY' as report_type,
  COUNT(DISTINCT ticker) as total_symbols,
  COUNT(DISTINCT CASE WHEN EXTRACT(EPOCH FROM (NOW() - latest_ts)) > 86400 THEN ticker END) as symbols_with_stale_data,
  MAX(latest_ts) as newest_bar_in_system,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(latest_ts))) / 86400) as days_behind
FROM latest_bars;
