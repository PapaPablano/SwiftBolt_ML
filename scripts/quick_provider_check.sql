-- Quick check: What provider is being used for recent data?
SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  MAX(o.ts) as latest_bar,
  COUNT(*) as bars_with_this_provider
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker IN ('AAPL', 'NVDA')
  AND o.timeframe IN ('m15', 'h1', 'd1')
  AND o.ts >= NOW() - INTERVAL '7 days'  -- Last 7 days only
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, o.timeframe, o.provider;
