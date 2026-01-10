-- Check actual constraints on ohlc_bars_v2
SELECT
  con.conname AS constraint_name,
  con.contype AS constraint_type,
  pg_get_constraintdef(con.oid) AS constraint_definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE rel.relname = 'ohlc_bars_v2'
  AND nsp.nspname = 'public'
ORDER BY con.conname;

-- Check what data exists for AAPL in ohlc_bars_v2
WITH aapl_id AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
)
SELECT
  provider,
  timeframe,
  is_forecast,
  is_intraday,
  COUNT(*) as bar_count,
  MIN(DATE(ts)) as first_date,
  MAX(DATE(ts)) as last_date
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM aapl_id)
  AND timeframe = 'd1'
GROUP BY provider, timeframe, is_forecast, is_intraday
ORDER BY provider;
