-- Delete data from deprecated providers to force fresh Alpaca loads
-- Run this in Supabase SQL Editor

-- BACKUP FIRST (optional - uncomment to create backup)
-- CREATE TABLE ohlc_bars_v2_backup_20260110 AS 
-- SELECT * FROM ohlc_bars_v2 
-- WHERE provider IN ('yfinance', 'tradier', 'polygon');

-- Show what will be deleted
SELECT 
  provider,
  timeframe,
  COUNT(*) as bars_to_delete,
  MIN(ts) as oldest,
  MAX(ts) as newest
FROM ohlc_bars_v2
WHERE provider IN ('yfinance', 'tradier', 'polygon')
  AND ts >= NOW() - INTERVAL '30 days'  -- Only recent data
GROUP BY provider, timeframe
ORDER BY provider, timeframe;

-- DELETE recent data from deprecated providers
-- This forces chart-data-v2 to fetch fresh data from Alpaca
BEGIN;

DELETE FROM ohlc_bars_v2
WHERE provider IN ('yfinance', 'tradier', 'polygon')
  AND ts >= NOW() - INTERVAL '30 days';  -- Only last 30 days

-- Verify deletion
SELECT 
  'After deletion' as status,
  provider,
  COUNT(*) as remaining_bars
FROM ohlc_bars_v2
WHERE provider IN ('yfinance', 'tradier', 'polygon')
GROUP BY provider;

COMMIT;

-- Verify Alpaca data exists
SELECT 
  s.ticker,
  o.timeframe,
  COUNT(*) as alpaca_bars,
  MAX(o.ts) as latest_bar
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
WHERE o.provider = 'alpaca'
  AND o.timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
