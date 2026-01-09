-- Check AAPL data timeline for gaps
SELECT
  DATE(ts) as date,
  COUNT(*) as bar_count,
  MIN(ts) as first_bar,
  MAX(ts) as last_bar,
  STRING_AGG(DISTINCT provider, ', ') as providers,
  STRING_AGG(DISTINCT data_status, ', ') as statuses
FROM bars_d1
WHERE symbol = 'AAPL'
  AND ts >= '2024-01-01'
  AND ts <= '2026-01-31'
GROUP BY DATE(ts)
ORDER BY DATE(ts) DESC
LIMIT 50;
