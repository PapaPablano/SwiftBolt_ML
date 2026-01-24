-- ============================================================================
-- Intraday Data Diagnostic Script
-- Purpose: Check current state of intraday data and Alpaca coverage
-- Date: 2026-01-09
-- ============================================================================

-- 1. Check provider distribution for AAPL and NVDA
\echo '\n========================================='
\echo '1. PROVIDER DISTRIBUTION (AAPL & NVDA)'
\echo '=========================================\n'

SELECT
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bar_count,
  MIN(DATE(o.ts)) as earliest_date,
  MAX(DATE(o.ts)) as latest_date,
  MAX(o.fetched_at) as last_fetched
FROM ohlc_bars_v2 o
JOIN symbols s ON o.symbol_id = s.id
WHERE s.ticker IN ('AAPL', 'NVDA')
  AND o.timeframe = 'h1'
  AND o.is_forecast = false
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, o.provider;

-- 2. Check Alpaca health metrics
\echo '\n========================================='
\echo '2. ALPACA HEALTH METRICS'
\echo '=========================================\n'

SELECT * FROM v_alpaca_health;

-- 3. Check backfill job status
\echo '\n========================================='
\echo '3. BACKFILL JOB STATUS'
\echo '=========================================\n'

SELECT
  s.ticker,
  j.timeframe,
  j.status,
  j.total_chunks,
  j.completed_chunks,
  j.failed_chunks,
  j.bars_collected,
  j.created_at,
  j.updated_at
FROM backfill_jobs j
JOIN symbols s ON j.symbol_id = s.id
WHERE s.ticker IN ('AAPL', 'NVDA')
  AND j.timeframe = 'h1'
ORDER BY j.created_at DESC
LIMIT 10;

-- 4. Check pending chunks
\echo '\n========================================='
\echo '4. PENDING BACKFILL CHUNKS'
\echo '=========================================\n'

SELECT
  c.symbol,
  c.timeframe,
  c.day,
  c.status,
  c.try_count,
  c.last_error
FROM backfill_chunks c
WHERE c.symbol IN ('AAPL', 'NVDA')
  AND c.timeframe = 'h1'
  AND c.status = 'pending'
ORDER BY c.symbol, c.day
LIMIT 20;

-- 5. Get Alpaca coverage report
\echo '\n========================================='
\echo '5. ALPACA COVERAGE REPORT'
\echo '=========================================\n'

SELECT
  symbol_ticker,
  timeframe,
  total_bars,
  alpaca_bars,
  alpaca_coverage_pct,
  latest_alpaca_date,
  data_gap_days
FROM get_alpaca_coverage_report()
WHERE symbol_ticker IN ('AAPL', 'NVDA')
  AND timeframe = 'h1';

-- 6. Check for old Polygon data that should be replaced
\echo '\n========================================='
\echo '6. OLD POLYGON DATA (SHOULD BE REPLACED)'
\echo '=========================================\n'

SELECT
  s.ticker,
  o.timeframe,
  COUNT(*) as polygon_bars,
  MIN(DATE(o.ts)) as earliest,
  MAX(DATE(o.ts)) as latest
FROM ohlc_bars_v2 o
JOIN symbols s ON o.symbol_id = s.id
WHERE s.ticker IN ('AAPL', 'NVDA')
  AND o.provider = 'polygon'
  AND o.timeframe = 'h1'
  AND o.is_forecast = false
GROUP BY s.ticker, o.timeframe;

-- 7. Sample data from ohlc_bars_v2
\echo '\n========================================='
\echo '7. SAMPLE DATA (Latest 10 bars for AAPL h1)'
\echo '=========================================\n'

SELECT
  o.ts,
  o.open,
  o.high,
  o.low,
  o.close,
  o.volume,
  o.provider,
  o.is_intraday,
  o.data_status
FROM ohlc_bars_v2 o
JOIN symbols s ON o.symbol_id = s.id
WHERE s.ticker = 'AAPL'
  AND o.timeframe = 'h1'
  AND o.is_forecast = false
ORDER BY o.ts DESC
LIMIT 10;
