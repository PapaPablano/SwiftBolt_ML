-- Delete corrupted AAPL bars with impossible intraday ranges
-- These bars have extreme high-low spreads that don't match real market data

-- Get AAPL symbol_id
DO $$
DECLARE
    v_symbol_id UUID;
BEGIN
    SELECT id INTO v_symbol_id FROM symbols WHERE ticker = 'AAPL';
    
    -- Delete the 3 corrupted bars
    DELETE FROM ohlc_bars_v2
    WHERE symbol_id = v_symbol_id
      AND timeframe = 'd1'
      AND is_forecast = false
      AND (
          -- June 1, 2024 bar (45-point range)
          (DATE(ts) = '2024-06-01' AND high > 235 AND low < 195)
          OR
          -- March 1, 2025 bar (75-point range)
          (DATE(ts) = '2025-03-01' AND high > 240 AND low < 175)
          OR
          -- September 1, 2025 bar (54-point range)
          (DATE(ts) = '2025-09-01' AND high > 275 AND low < 230)
      );
    
    RAISE NOTICE 'Deleted corrupted AAPL bars';
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
  AND DATE(ts) IN ('2024-06-01', '2025-03-01', '2025-09-01')
ORDER BY ts;

-- Should return 0 rows if deletion was successful
