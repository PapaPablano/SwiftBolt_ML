-- Check AAPL data in ohlc_bars_v2 to verify we have current data
-- Run this in Supabase SQL Editor

-- Get symbol_id for AAPL
DO $$
DECLARE
  v_symbol_id UUID;
  v_timeframe TEXT;
BEGIN
  SELECT id INTO v_symbol_id FROM symbols WHERE ticker = 'AAPL';
  
  RAISE NOTICE '========================================';
  RAISE NOTICE 'AAPL Data Check';
  RAISE NOTICE 'Symbol ID: %', v_symbol_id;
  RAISE NOTICE '========================================';
  RAISE NOTICE '';
  
  -- Check each timeframe
  FOREACH v_timeframe IN ARRAY ARRAY['m15', 'h1', 'h4', 'd1', 'w1']
  LOOP
    RAISE NOTICE 'Timeframe: %', v_timeframe;
    RAISE NOTICE '----------------------------------------';
    
    -- Show bar counts and date range
    PERFORM (
      SELECT 
        RAISE NOTICE '  Total bars: %', COUNT(*)
      FROM ohlc_bars_v2
      WHERE symbol_id = v_symbol_id
        AND timeframe = v_timeframe
    );
    
    PERFORM (
      SELECT 
        RAISE NOTICE '  Earliest: %', MIN(ts)::date
      FROM ohlc_bars_v2
      WHERE symbol_id = v_symbol_id
        AND timeframe = v_timeframe
    );
    
    PERFORM (
      SELECT 
        RAISE NOTICE '  Latest: %', MAX(ts)
      FROM ohlc_bars_v2
      WHERE symbol_id = v_symbol_id
        AND timeframe = v_timeframe
    );
    
    PERFORM (
      SELECT 
        RAISE NOTICE '  Providers: %', STRING_AGG(DISTINCT provider, ', ')
      FROM ohlc_bars_v2
      WHERE symbol_id = v_symbol_id
        AND timeframe = v_timeframe
    );
    
    RAISE NOTICE '';
  END LOOP;
END $$;

-- Detailed view of latest bars per timeframe
SELECT 
  timeframe,
  COUNT(*) as total_bars,
  MIN(ts)::date as earliest_date,
  MAX(ts) as latest_timestamp,
  EXTRACT(EPOCH FROM (NOW() - MAX(ts))) / 3600 as hours_since_latest,
  STRING_AGG(DISTINCT provider, ', ' ORDER BY provider) as providers
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY timeframe
ORDER BY timeframe;

-- Show last 10 bars for d1 timeframe
SELECT 
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider,
  is_intraday,
  is_forecast
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
ORDER BY ts DESC
LIMIT 10;
