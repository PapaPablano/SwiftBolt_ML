-- Clean up AAPL data from ohlc_bars_v2 and prepare for fresh backfill
-- This will remove all existing AAPL daily data to resolve constraint conflicts

-- Get AAPL symbol_id
DO $$
DECLARE
  aapl_id UUID;
BEGIN
  SELECT id INTO aapl_id FROM symbols WHERE ticker = 'AAPL' LIMIT 1;

  IF aapl_id IS NOT NULL THEN
    -- Delete all d1 bars for AAPL from ohlc_bars_v2
    DELETE FROM ohlc_bars_v2
    WHERE symbol_id = aapl_id
      AND timeframe = 'd1'
      AND is_forecast = false;

    RAISE NOTICE 'Deleted all AAPL d1 bars from ohlc_bars_v2';
  ELSE
    RAISE NOTICE 'AAPL symbol not found';
  END IF;
END $$;

-- Verify deletion
SELECT
  COUNT(*) as remaining_bars,
  MIN(DATE(ts)) as first_date,
  MAX(DATE(ts)) as last_date
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE s.ticker = 'AAPL'
  AND timeframe = 'd1';
