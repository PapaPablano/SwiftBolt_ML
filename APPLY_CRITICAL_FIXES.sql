-- ============================================================================
-- CRITICAL FIXES FOR CHART RENDERING ISSUES
-- Apply this SQL in Supabase Dashboard → SQL Editor
-- ============================================================================

-- 1. DEDUPLICATION: Fix get_chart_data_v2 to return only one bar per day
-- ============================================================================
-- Drop both possible signatures to ensure clean migration
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP, TIMESTAMP);
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE);

CREATE OR REPLACE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP WITH TIME ZONE,
  p_end_date TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
  ts TEXT,
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  provider VARCHAR(20),
  is_intraday BOOLEAN,
  is_forecast BOOLEAN,
  data_status VARCHAR(20),
  confidence_score DECIMAL(3, 2),
  upper_band DECIMAL(10, 4),
  lower_band DECIMAL(10, 4)
) AS $$
BEGIN
  RETURN QUERY
  WITH deduplicated AS (
    SELECT 
      o.*,
      ROW_NUMBER() OVER (
        PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday 
        ORDER BY o.ts DESC, o.fetched_at DESC NULLS LAST
      ) as rn
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date
      AND o.ts <= p_end_date
      AND (
        (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider = 'polygon')
        OR
        (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
        OR
        (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast')
      )
  )
  SELECT 
    to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
    d.open,
    d.high,
    d.low,
    d.close,
    d.volume,
    d.provider,
    d.is_intraday,
    d.is_forecast,
    d.data_status,
    d.confidence_score,
    d.upper_band,
    d.lower_band
  FROM deduplicated d
  WHERE d.rn = 1
  ORDER BY d.ts ASC;
END;
$$ LANGUAGE plpgsql;

-- 2. UNIQUE CONSTRAINTS: Prevent future duplicates
-- ============================================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_unique_historical 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider)
WHERE is_forecast = false;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_unique_forecast 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider, confidence_score)
WHERE is_forecast = true;

-- 3. PERFORMANCE INDEXES: Speed up queries
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ohlc_chart_query 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_forecast = false;

CREATE INDEX IF NOT EXISTS idx_ohlc_provider_range 
ON ohlc_bars_v2 (symbol_id, timeframe, provider, ts)
WHERE is_forecast = false;

CREATE INDEX IF NOT EXISTS idx_ohlc_intraday 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_intraday = true;

CREATE INDEX IF NOT EXISTS idx_ohlc_forecast 
ON ohlc_bars_v2 (symbol_id, timeframe, ts)
WHERE is_forecast = true;

-- 4. CLEANUP: Remove existing duplicates (optional but recommended)
-- ============================================================================
-- This will keep only the most recent bar for each date
-- WARNING: This deletes data. Backup first if needed.

-- Uncomment to execute cleanup:
/*
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
*/

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check for remaining duplicates (should return 0 after cleanup)
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
ORDER BY bar_count DESC
LIMIT 10;

-- Test the deduplication function
SELECT COUNT(*) as total_bars
FROM get_chart_data_v2(
  (SELECT id FROM symbols WHERE ticker = 'AAPL' LIMIT 1),
  'd1',
  NOW() - INTERVAL '30 days',
  NOW()
);

-- ============================================================================
-- SUCCESS!
-- After applying this SQL:
-- 1. Rebuild your Swift app
-- 2. Test charts with NVDA and AAPL
-- 3. Charts should render smoothly without discontinuities
-- ============================================================================
