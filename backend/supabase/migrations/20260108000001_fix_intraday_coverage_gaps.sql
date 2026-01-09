-- Migration: Fix coverage gap detection for intraday timeframes
-- Problem: get_coverage_gaps() was checking historical days for intraday timeframes
-- Tradier only provides data for TODAY, so we should only check today's coverage
-- Solution: For intraday timeframes (m15, h1, h4), set target_from to start of today

DROP FUNCTION IF EXISTS get_coverage_gaps(text, text, int);

CREATE OR REPLACE FUNCTION get_coverage_gaps(
  p_symbol text,
  p_timeframe text,
  p_window_days int default 7
)
RETURNS TABLE(
  gap_from timestamptz,
  gap_to timestamptz,
  gap_hours numeric
) AS $$
DECLARE
  v_target_from timestamptz;
  v_target_to timestamptz;
  v_coverage_from timestamptz;
  v_coverage_to timestamptz;
  v_is_intraday boolean;
BEGIN
  -- Detect if this is an intraday timeframe
  v_is_intraday := p_timeframe IN ('m15', 'h1', 'h4');

  v_target_to := now();

  -- Use window_days for both intraday and daily timeframes
  -- Polygon provides historical intraday data, so we can backfill 2+ years
  v_target_from := v_target_to - (p_window_days || ' days')::interval;

  -- Get current coverage
  SELECT from_ts, to_ts INTO v_coverage_from, v_coverage_to
  FROM coverage_status
  WHERE symbol = p_symbol AND timeframe = p_timeframe;

  -- If no coverage exists, return the full target range as a gap
  IF v_coverage_from IS NULL OR v_coverage_to IS NULL THEN
    RETURN QUERY SELECT v_target_from, v_target_to,
      EXTRACT(EPOCH FROM (v_target_to - v_target_from)) / 3600.0;
    RETURN;
  END IF;

  -- Check for gap at the beginning (coverage starts after target)
  IF v_coverage_from > v_target_from THEN
    RETURN QUERY SELECT v_target_from, v_coverage_from,
      EXTRACT(EPOCH FROM (v_coverage_from - v_target_from)) / 3600.0;
  END IF;

  -- Check for gap at the end (coverage ends before target)
  IF v_coverage_to < v_target_to THEN
    RETURN QUERY SELECT v_coverage_to, v_target_to,
      EXTRACT(EPOCH FROM (v_target_to - v_coverage_to)) / 3600.0;
  END IF;

  RETURN;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_coverage_gaps IS
'Identifies coverage gaps for a symbol/timeframe pair.
Uses window_days parameter for both intraday and daily timeframes.
Polygon provides historical intraday data, enabling 2+ year backfills.';
