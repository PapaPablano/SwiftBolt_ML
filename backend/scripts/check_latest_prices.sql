-- Latest prices for each stock on each timeframe
SELECT 
  s.ticker,
  ob.timeframe,
  ob.close as latest_price,
  ob.open,
  ob.high,
  ob.low,
  ob.volume,
  ob.ts as timestamp,
  CASE 
    WHEN ob.close > ob.open THEN '📈 Up'
    WHEN ob.close < ob.open THEN '📉 Down'
    ELSE '➡️ Flat'
  END as direction,
  ROUND(((ob.close - ob.open) / ob.open * 100)::numeric, 2) as change_pct
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'GOOG', 'MU', 'NVDA', 'PLTR', 'TSLA')
AND ob.provider = 'alpaca'
AND ob.is_forecast = false
AND ob.ts IN (
  SELECT MAX(ts)
  FROM ohlc_bars_v2
  WHERE symbol_id = ob.symbol_id
  AND timeframe = ob.timeframe
  AND provider = 'alpaca'
  AND is_forecast = false
)
ORDER BY s.ticker, 
  CASE ob.timeframe
    WHEN 'm15' THEN 1
    WHEN 'h1' THEN 2
    WHEN 'h4' THEN 3
    WHEN 'd1' THEN 4
    WHEN 'w1' THEN 5
  END;
