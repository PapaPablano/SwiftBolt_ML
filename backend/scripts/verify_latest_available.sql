-- Check data coverage and identify gaps
WITH latest_bars AS (
  SELECT 
    s.ticker,
    ob.timeframe,
    COUNT(*) as total_bars,
    MIN(ob.ts) as oldest_bar,
    MAX(ob.ts) as newest_bar,
    MAX(ob.close) as latest_price
  FROM ohlc_bars_v2 ob
  JOIN symbols s ON s.id = ob.symbol_id
  WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'GOOG', 'MU', 'NVDA', 'PLTR', 'TSLA')
  AND ob.provider = 'alpaca'
  AND ob.is_forecast = false
  GROUP BY s.ticker, ob.timeframe
),
expected_timeframes AS (
  SELECT 
    ticker,
    timeframe
  FROM (
    SELECT UNNEST(ARRAY['AAPL', 'AMD', 'AMZN', 'CRWD', 'GOOG', 'MU', 'NVDA', 'PLTR', 'TSLA']) as ticker
  ) symbols
  CROSS JOIN (
    SELECT UNNEST(ARRAY['m15', 'h1', 'h4', 'd1', 'w1']) as timeframe
  ) timeframes
)
SELECT 
  et.ticker,
  et.timeframe,
  COALESCE(lb.total_bars, 0) as bars_count,
  lb.oldest_bar,
  lb.newest_bar,
  lb.latest_price,
  CASE 
    WHEN lb.total_bars IS NULL THEN '❌ MISSING'
    WHEN lb.newest_bar < NOW() - INTERVAL '7 days' THEN '⚠️ STALE (>7 days old)'
    WHEN lb.newest_bar < NOW() - INTERVAL '2 days' THEN '⚠️ OLD (>2 days old)'
    ELSE '✅ CURRENT'
  END as status
FROM expected_timeframes et
LEFT JOIN latest_bars lb ON et.ticker = lb.ticker AND et.timeframe = lb.timeframe
ORDER BY et.ticker, 
  CASE et.timeframe
    WHEN 'm15' THEN 1
    WHEN 'h1' THEN 2
    WHEN 'h4' THEN 3
    WHEN 'd1' THEN 4
    WHEN 'w1' THEN 5
  END;
