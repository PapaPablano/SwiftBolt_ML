-- Comprehensive diagnostic for AAPL data issue

-- 1. Check all constraints on ohlc_bars_v2
SELECT
  'CONSTRAINT ANALYSIS' as section,
  con.conname AS constraint_name,
  con.contype AS type,
  pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE rel.relname = 'ohlc_bars_v2'
  AND nsp.nspname = 'public'
ORDER BY con.conname;

-- 2. Check all unique indexes on ohlc_bars_v2
SELECT
  'UNIQUE INDEX ANALYSIS' as section,
  i.relname as index_name,
  a.attname as column_name,
  ix.indisunique as is_unique,
  pg_get_indexdef(ix.indexrelid) as index_definition
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
WHERE t.relname = 'ohlc_bars_v2'
  AND ix.indisunique = true
ORDER BY i.relname, a.attnum;

-- 3. Get AAPL symbol info
SELECT
  'AAPL SYMBOL INFO' as section,
  id,
  ticker,
  asset_type
FROM symbols
WHERE ticker = 'AAPL';

-- 4. Check what AAPL data exists in ohlc_bars_v2
WITH aapl_id AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
)
SELECT
  'AAPL DATA IN OHLC_BARS_V2' as section,
  provider,
  timeframe,
  is_forecast,
  is_intraday,
  COUNT(*) as bar_count,
  MIN(DATE(ts)) as first_date,
  MAX(DATE(ts)) as last_date
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM aapl_id)
GROUP BY provider, timeframe, is_forecast, is_intraday
ORDER BY timeframe, provider;

-- 5. Check for data in the 2024-2025 range specifically
WITH aapl_id AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
)
SELECT
  'AAPL DATA 2024-2025' as section,
  DATE(ts) as date,
  provider,
  is_forecast,
  open,
  close
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM aapl_id)
  AND timeframe = 'd1'
  AND DATE(ts) BETWEEN '2024-01-01' AND '2025-12-31'
ORDER BY ts
LIMIT 20;

-- 6. Check if there's data in old ohlc_bars table
WITH aapl_id AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
)
SELECT
  'AAPL DATA IN OLD OHLC_BARS' as section,
  COUNT(*) as total_bars,
  MIN(DATE(ts)) as first_date,
  MAX(DATE(ts)) as last_date
FROM ohlc_bars
WHERE symbol_id = (SELECT id FROM aapl_id)
  AND timeframe::text = 'd1';
