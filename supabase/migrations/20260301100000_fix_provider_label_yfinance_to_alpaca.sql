-- Fix provider label: d1/w1 bars were mislabeled as 'yfinance' when Alpaca fetched them.
-- The unique constraint is on (symbol_id, timeframe, ts, provider, is_forecast).
-- We must first delete yfinance rows where an alpaca row already covers the same bar,
-- then relabel the remaining yfinance rows to alpaca.

BEGIN;

-- Step 1: Delete yfinance rows where an alpaca row already exists for the same bar
-- (prevents unique constraint violation on the UPDATE below)
DELETE FROM ohlc_bars_v2 yf
USING ohlc_bars_v2 al
WHERE yf.provider = 'yfinance'
  AND al.provider = 'alpaca'
  AND al.symbol_id = yf.symbol_id
  AND al.timeframe = yf.timeframe
  AND al.ts = yf.ts
  AND al.is_forecast = yf.is_forecast
  AND yf.timeframe IN ('d1', 'w1')
  AND yf.is_forecast = false;

-- Step 2: Relabel remaining yfinance rows (no conflict possible now)
UPDATE ohlc_bars_v2
SET provider = 'alpaca',
    updated_at = NOW()
WHERE provider = 'yfinance'
  AND timeframe IN ('d1', 'w1')
  AND is_forecast = false;

COMMIT;
