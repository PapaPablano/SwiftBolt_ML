-- Migration: Add RPC functions for gap detection and coverage stats
-- Purpose: Support backfill_with_gap_detection.py script
-- Date: 2026-01-10

-- ============================================================================
-- Function: detect_ohlc_gaps
-- Detect gaps in OHLC data for a symbol/timeframe
-- ============================================================================
DROP FUNCTION IF EXISTS detect_ohlc_gaps CASCADE;

CREATE FUNCTION detect_ohlc_gaps(
  p_symbol TEXT,
  p_timeframe TEXT,
  p_max_gap_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
  gap_start TIMESTAMP WITH TIME ZONE,
  gap_end TIMESTAMP WITH TIME ZONE,
  gap_hours DECIMAL
) AS $$
BEGIN
  RETURN QUERY
  WITH bars_with_next AS (
    SELECT
      o.ts,
      LEAD(o.ts) OVER (ORDER BY o.ts) as next_ts,
      EXTRACT(EPOCH FROM (LEAD(o.ts) OVER (ORDER BY o.ts) - o.ts)) / 3600 as gap_hrs
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = (SELECT id FROM symbols WHERE ticker = p_symbol)
      AND o.timeframe = p_timeframe
      AND o.provider = 'alpaca'
      AND o.is_forecast = false
    ORDER BY o.ts
  )
  SELECT
    b.ts as gap_start,
    b.next_ts as gap_end,
    b.gap_hrs as gap_hours
  FROM bars_with_next b
  WHERE b.gap_hrs > p_max_gap_hours
  ORDER BY b.gap_hrs DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_ohlc_gaps IS
'Detect gaps in OHLC data exceeding max_gap_hours for a symbol/timeframe.
Returns (gap_start, gap_end, gap_hours) sorted by gap size descending.';

-- ============================================================================
-- Function: get_ohlc_coverage_stats
-- Get coverage statistics for a symbol/timeframe
-- ============================================================================
DROP FUNCTION IF EXISTS get_ohlc_coverage_stats CASCADE;

CREATE FUNCTION get_ohlc_coverage_stats(
  p_symbol TEXT,
  p_timeframe TEXT
)
RETURNS TABLE (
  bar_count BIGINT,
  oldest_bar TIMESTAMP WITH TIME ZONE,
  newest_bar TIMESTAMP WITH TIME ZONE,
  time_span_days INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*)::BIGINT as bar_count,
    MIN(o.ts)::TIMESTAMP WITH TIME ZONE as oldest_bar,
    MAX(o.ts)::TIMESTAMP WITH TIME ZONE as newest_bar,
    EXTRACT(DAY FROM (MAX(o.ts) - MIN(o.ts)))::INTEGER as time_span_days
  FROM ohlc_bars_v2 o
  WHERE o.symbol_id = (SELECT id FROM symbols WHERE ticker = p_symbol)
    AND o.timeframe = p_timeframe
    AND o.provider = 'alpaca'
    AND o.is_forecast = false;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_ohlc_coverage_stats IS
'Get coverage statistics (bar count, date range, time span) for a symbol/timeframe.';

-- ============================================================================
-- Grant execute permissions to service role
-- ============================================================================
GRANT EXECUTE ON FUNCTION detect_ohlc_gaps TO service_role;
GRANT EXECUTE ON FUNCTION get_ohlc_coverage_stats TO service_role;

-- ============================================================================
-- Verify functions were created
-- ============================================================================
DO $$
DECLARE
  gap_fn_exists BOOLEAN;
  stats_fn_exists BOOLEAN;
BEGIN
  SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'detect_ohlc_gaps') INTO gap_fn_exists;
  SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'get_ohlc_coverage_stats') INTO stats_fn_exists;

  IF gap_fn_exists AND stats_fn_exists THEN
    RAISE NOTICE 'Gap detection RPC functions created successfully';
  ELSE
    RAISE WARNING 'Function creation may have failed';
  END IF;
END $$;
