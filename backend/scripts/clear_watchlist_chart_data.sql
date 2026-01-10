-- ============================================================================
-- Clear Watchlist Chart Data - Alpaca Migration Prep
-- ============================================================================
-- Purpose: Remove legacy provider data for watchlist symbols
-- Safe: Preserves ML forecasts, rankings, and all other data
-- Date: 2026-01-10
-- Watchlist: AAPL, AMD, AMZN, CRWD, MU, NVDA, PLTR (7 symbols)
-- ============================================================================

BEGIN;

-- Step 1: Show current state BEFORE deletion
SELECT 
  '=== BEFORE DELETION ===' as status,
  s.ticker,
  ob.provider,
  ob.timeframe,
  COUNT(*) as bar_count,
  MIN(ob.ts) as oldest_bar,
  MAX(ob.ts) as newest_bar
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
GROUP BY s.ticker, ob.provider, ob.timeframe
ORDER BY s.ticker, ob.provider, ob.timeframe;

-- Step 2: Delete legacy provider data for watchlist symbols
-- Preserves: ml_forecast data
-- Removes: alpaca, polygon, yfinance, tradier, finnhub OHLC data
WITH watchlist_symbols AS (
  SELECT UNNEST(ARRAY['AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR']) as ticker
),
deleted_rows AS (
  DELETE FROM ohlc_bars_v2 
  WHERE symbol_id IN (
    SELECT s.id 
    FROM symbols s 
    JOIN watchlist_symbols ws ON s.ticker = ws.ticker
  )
  AND provider != 'ml_forecast'  -- Preserve ML forecasts
  RETURNING symbol_id, provider, timeframe
)
SELECT 
  '=== DELETION SUMMARY ===' as status,
  s.ticker,
  dr.provider,
  dr.timeframe,
  COUNT(*) as bars_deleted
FROM deleted_rows dr
JOIN symbols s ON s.id = dr.symbol_id
GROUP BY s.ticker, dr.provider, dr.timeframe
ORDER BY s.ticker, dr.provider, dr.timeframe;

-- Step 3: Show current state AFTER deletion
SELECT 
  '=== AFTER DELETION ===' as status,
  s.ticker,
  COALESCE(ob.provider, 'NO DATA') as provider,
  COALESCE(ob.timeframe, 'N/A') as timeframe,
  COUNT(ob.id) as bar_count,
  MIN(ob.ts) as oldest_bar,
  MAX(ob.ts) as newest_bar
FROM symbols s
LEFT JOIN ohlc_bars_v2 ob ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
GROUP BY s.ticker, ob.provider, ob.timeframe
ORDER BY s.ticker, ob.provider, ob.timeframe;

-- Step 4: Verify ML forecasts are preserved
SELECT 
  '=== ML FORECASTS PRESERVED ===' as status,
  s.ticker,
  COUNT(*) as forecast_count,
  MIN(ob.ts) as oldest_forecast,
  MAX(ob.ts) as newest_forecast
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'ml_forecast'
GROUP BY s.ticker
ORDER BY s.ticker;

-- Step 5: Show what needs to be backfilled
SELECT 
  '=== READY FOR ALPACA BACKFILL ===' as status,
  ticker,
  'h1' as recommended_timeframe,
  '100 bars minimum' as target,
  'python ml/src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1' as command
FROM (
  SELECT UNNEST(ARRAY['AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR']) as ticker
) symbols;

COMMIT;

-- ============================================================================
-- Next Steps:
-- ============================================================================
-- 1. Review the deletion summary above
-- 2. Run Alpaca backfill for h1 (hourly):
--    python ml/src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1
-- 3. Run Alpaca backfill for d1 (daily):
--    python ml/src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe d1
-- 4. Verify charts load with 100 bars in macOS client
-- 5. Check chart standardization is working correctly
-- ============================================================================
