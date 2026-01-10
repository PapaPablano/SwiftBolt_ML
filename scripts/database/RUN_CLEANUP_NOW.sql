-- ============================================================================
-- DELETE 153,708 DUPLICATE BARS
-- Keeps most recent bar per day, deletes older duplicates
-- ============================================================================

-- Execute this in Supabase SQL Editor
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

-- After this completes, verify with:
-- SELECT COUNT(*) FROM ohlc_bars_v2 WHERE is_forecast = false;
