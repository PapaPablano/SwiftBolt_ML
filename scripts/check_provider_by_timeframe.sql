-- Check which provider is being used for each timeframe
-- This will show if we're using the wrong provider for intraday data

SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bar_count,
  MIN(o.ts) as earliest,
  MAX(o.ts) as latest,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(o.ts))) / 3600) as hours_old
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')
  AND s.ticker IN ('AAPL', 'NVDA')  -- Check a couple symbols
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, o.timeframe, o.provider;

-- Check if we have mixed providers for same timeframe
SELECT 
  s.ticker,
  o.timeframe,
  STRING_AGG(DISTINCT o.provider, ', ' ORDER BY o.provider) as providers,
  COUNT(DISTINCT o.provider) as provider_count
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')
GROUP BY s.ticker, o.timeframe
HAVING COUNT(DISTINCT o.provider) > 1
ORDER BY s.ticker, o.timeframe;
