-- Delete all corrupted AAPL bars that don't exist in Yahoo Finance
-- These bars have extreme intraday ranges or are on non-trading days

DO $$
DECLARE
    v_symbol_id UUID;
    v_deleted_count INT;
BEGIN
    -- Get AAPL symbol_id
    SELECT id INTO v_symbol_id FROM symbols WHERE ticker = 'AAPL';
    
    -- Delete the 8 corrupted bars
    DELETE FROM ohlc_bars_v2
    WHERE symbol_id = v_symbol_id
      AND timeframe = 'd1'
      AND is_forecast = false
      AND DATE(ts) IN (
          '2024-06-01',
          '2024-09-01', 
          '2024-12-01',
          '2025-03-01',
          '2025-06-01',
          '2025-09-01',
          '2025-12-27',
          '2026-01-01'
      );
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % corrupted AAPL bars', v_deleted_count;
END $$;

-- Verify deletion
SELECT 
    DATE(ts) as date,
    open, high, low, close,
    (high - low) as intraday_range,
    ((high - low) / close * 100) as range_pct
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
  AND is_forecast = false
  AND DATE(ts) IN (
      '2024-06-01', '2024-09-01', '2024-12-01',
      '2025-03-01', '2025-06-01', '2025-09-01',
      '2025-12-27', '2026-01-01'
  )
ORDER BY ts;

-- Should return 0 rows if deletion was successful

-- Check for any remaining bars with extreme intraday ranges (>20%)
SELECT 
    DATE(ts) as date,
    open, high, low, close,
    (high - low) as intraday_range,
    ((high - low) / close * 100) as range_pct
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
  AND is_forecast = false
  AND ((high - low) / close * 100) > 20
ORDER BY range_pct DESC
LIMIT 10;

-- Should return 0 rows for clean data
