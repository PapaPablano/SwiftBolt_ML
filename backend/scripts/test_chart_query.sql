-- Test the exact query that chart-data-v2 Edge Function uses
-- This simulates what the app should be receiving

-- Get AAPL symbol_id
DO $$
DECLARE
  v_symbol_id UUID;
  v_start_date TIMESTAMP WITH TIME ZONE;
  v_end_date TIMESTAMP WITH TIME ZONE;
BEGIN
  -- Get symbol ID
  SELECT id INTO v_symbol_id FROM symbols WHERE ticker = 'AAPL';
  
  -- Calculate date range (same as Edge Function: 60 days back)
  v_end_date := NOW();
  v_start_date := v_end_date - INTERVAL '60 days';
  
  RAISE NOTICE 'Symbol ID: %', v_symbol_id;
  RAISE NOTICE 'Start Date: %', v_start_date;
  RAISE NOTICE 'End Date: %', v_end_date;
  RAISE NOTICE '';
  RAISE NOTICE 'Testing get_chart_data_v2 for AAPL h1...';
  RAISE NOTICE '';
END $$;

-- Run the actual function call
SELECT 
  COUNT(*) as total_bars,
  MIN(ts::timestamp) as oldest_bar,
  MAX(ts::timestamp) as newest_bar,
  MAX(ts::timestamp)::date as newest_date,
  COUNT(DISTINCT provider) as provider_count,
  STRING_AGG(DISTINCT provider, ', ' ORDER BY provider) as providers
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1',
  NOW() - INTERVAL '60 days',
  NOW()
);

-- Show last 10 bars
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
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL'),
  'h1',
  NOW() - INTERVAL '60 days',
  NOW()
)
ORDER BY ts::timestamp DESC
LIMIT 10;

-- Check what's in the raw table
SELECT 
  COUNT(*) as total_bars,
  MIN(ts) as oldest_bar,
  MAX(ts) as newest_bar,
  MAX(ts)::date as newest_date
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
AND timeframe = 'h1'
AND provider = 'alpaca'
AND is_forecast = false;

-- Show last 10 raw bars
SELECT 
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
AND timeframe = 'h1'
AND provider = 'alpaca'
AND is_forecast = false
ORDER BY ts DESC
LIMIT 10;
