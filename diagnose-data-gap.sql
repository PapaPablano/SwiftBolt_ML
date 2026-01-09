-- Comprehensive diagnosis of AAPL data gaps

-- 1. Get AAPL symbol_id first
WITH aapl_symbol AS (
  SELECT id, ticker FROM symbols WHERE ticker = 'AAPL' LIMIT 1
),

-- 2. Check what data exists in bars_d1 (old table if it exists)
bars_d1_data AS (
  SELECT
    'bars_d1' as source_table,
    MIN(DATE(ts)) as first_date,
    MAX(DATE(ts)) as last_date,
    COUNT(*) as total_bars,
    COUNT(DISTINCT DATE(ts)) as distinct_days,
    STRING_AGG(DISTINCT provider, ', ') as providers
  FROM bars_d1 b
  JOIN aapl_symbol a ON b.symbol_id = a.id
  WHERE DATE(ts) BETWEEN '2024-01-01' AND '2026-01-31'
),

-- 3. Check what data exists in ohlc_bars_v2 (new table)
ohlc_v2_data AS (
  SELECT
    'ohlc_bars_v2' as source_table,
    MIN(DATE(ts)) as first_date,
    MAX(DATE(ts)) as last_date,
    COUNT(*) as total_bars,
    COUNT(DISTINCT DATE(ts)) as distinct_days,
    STRING_AGG(DISTINCT provider, ', ') as providers,
    STRING_AGG(DISTINCT data_status, ', ') as statuses
  FROM ohlc_bars_v2 o
  JOIN aapl_symbol a ON o.symbol_id = a.id
  WHERE timeframe = 'd1'
    AND DATE(ts) BETWEEN '2024-01-01' AND '2026-01-31'
)

-- Show summary
SELECT * FROM bars_d1_data
UNION ALL
SELECT
  source_table,
  first_date,
  last_date,
  total_bars,
  distinct_days,
  providers,
  NULL as extra_column
FROM ohlc_v2_data;

-- 4. Show month-by-month breakdown for ohlc_bars_v2
WITH aapl_symbol AS (
  SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
)
SELECT
  TO_CHAR(DATE_TRUNC('month', ts), 'YYYY-MM') as month,
  COUNT(*) as bar_count,
  STRING_AGG(DISTINCT provider, ', ') as providers,
  MIN(DATE(ts)) as first_day,
  MAX(DATE(ts)) as last_day
FROM ohlc_bars_v2 o
JOIN aapl_symbol a ON o.symbol_id = a.id
WHERE timeframe = 'd1'
  AND DATE(ts) BETWEEN '2024-01-01' AND '2026-01-31'
GROUP BY DATE_TRUNC('month', ts)
ORDER BY month DESC;
