-- ============================================================================
-- CLEANUP EXISTING DUPLICATE BARS IN DATABASE
-- This removes duplicate bars, keeping only the most recent per day
-- ============================================================================

-- BACKUP RECOMMENDATION: Export your data before running this!
-- This DELETE operation is irreversible.

-- Step 1: Check how many duplicates exist
SELECT 
  COUNT(*) as total_duplicate_bars
FROM (
  SELECT id,
    ROW_NUMBER() OVER (
      PARTITION BY symbol_id, DATE(ts), timeframe, provider, is_forecast, is_intraday
      ORDER BY ts DESC, fetched_at DESC NULLS LAST
    ) as rn
  FROM ohlc_bars_v2
  WHERE is_forecast = false
) duplicates
WHERE rn > 1;

-- Step 2: Show sample duplicates (first 10)
SELECT 
  symbol_id,
  DATE(ts) as date,
  timeframe,
  provider,
  COUNT(*) as bar_count,
  STRING_AGG(ts::text, ', ' ORDER BY ts) as timestamps
FROM ohlc_bars_v2
WHERE is_forecast = false
GROUP BY symbol_id, DATE(ts), timeframe, provider
HAVING COUNT(*) > 1
ORDER BY bar_count DESC
LIMIT 10;

-- Step 3: DELETE duplicates (keeps most recent bar per day)
-- WARNING: This will permanently delete data!
WITH duplicates AS (
  SELECT id,
    ROW_NUMBER() OVER (
      PARTITION BY symbol_id, DATE(ts), timeframe, provider, is_forecast, is_intraday
      ORDER BY ts DESC, fetched_at DESC NULLS LAST
    ) as rn
  FROM ohlc_bars_v2
  WHERE is_forecast = false
)
DELETE FROM ohlc_bars_v2
WHERE id IN (
  SELECT id FROM duplicates WHERE rn > 1
);

-- Step 4: Verify cleanup
SELECT 
  symbol_id,
  DATE(ts) as date,
  timeframe,
  provider,
  COUNT(*) as bar_count
FROM ohlc_bars_v2
WHERE is_forecast = false
GROUP BY symbol_id, DATE(ts), timeframe, provider
HAVING COUNT(*) > 1
LIMIT 10;

-- Should return 0 rows if cleanup was successful

-- ============================================================================
-- IMPORTANT: After cleanup, the unique constraints will prevent future duplicates
-- ============================================================================
