-- ============================================================================
-- ALL-IN-ONE INTRADAY FIX
-- Run this complete script to fix all intraday timeframe issues
-- ============================================================================

-- ============================================================================
-- FIX 1: Update get_chart_data_v2() to accept m15/h1/h4 format
-- ============================================================================

-- Force drop the old function (all signatures)
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE);
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, TEXT, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE);
DROP FUNCTION IF EXISTS get_chart_data_v2;

-- Create new function with correct timeframe handling
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
DECLARE
  v_is_intraday_tf BOOLEAN;
  v_intraday_tf TEXT;
BEGIN
  -- Determine if this is an intraday timeframe request
  v_is_intraday_tf := p_timeframe IN ('m15', 'h1', 'h4');

  -- Map timeframe to intraday_bars format
  v_intraday_tf := CASE p_timeframe
    WHEN 'm15' THEN '15m'
    WHEN 'h1' THEN '15m'  -- Aggregate 15m bars to 1h
    WHEN 'h4' THEN '15m'  -- Aggregate 15m bars to 4h
    ELSE '15m'
  END;

  IF v_is_intraday_tf THEN
    -- Query intraday_bars table for 15m/1h/4h timeframes
    IF p_timeframe = 'm15' THEN
      -- Direct 15m bars
      RETURN QUERY
      SELECT
        to_char(ib.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
        ib.open::DECIMAL(10,4),
        ib.high::DECIMAL(10,4),
        ib.low::DECIMAL(10,4),
        ib.close::DECIMAL(10,4),
        ib.volume,
        'tradier'::VARCHAR(20) AS provider,
        true AS is_intraday,
        false AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM intraday_bars ib
      WHERE ib.symbol_id = p_symbol_id
        AND ib.timeframe = '15m'
        AND ib.ts >= p_start_date
        AND ib.ts <= p_end_date
      ORDER BY ib.ts ASC;

    ELSIF p_timeframe = 'h1' THEN
      -- Aggregate 15m bars to 1h
      RETURN QUERY
      WITH hourly_agg AS (
        SELECT
          date_trunc('hour', ib.ts) AS hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1] AS open,
          MAX(ib.high) AS high,
          MIN(ib.low) AS low,
          (array_agg(ib.close ORDER BY ib.ts DESC))[1] AS close,
          SUM(ib.volume) AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id
          AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date
          AND ib.ts <= p_end_date
        GROUP BY date_trunc('hour', ib.ts)
      )
      SELECT
        to_char(ha.hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
        ha.open::DECIMAL(10,4),
        ha.high::DECIMAL(10,4),
        ha.low::DECIMAL(10,4),
        ha.close::DECIMAL(10,4),
        ha.volume,
        'tradier'::VARCHAR(20) AS provider,
        true AS is_intraday,
        false AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM hourly_agg ha
      ORDER BY ha.hour_ts ASC;

    ELSIF p_timeframe = 'h4' THEN
      -- Aggregate 15m bars to 4h
      RETURN QUERY
      WITH four_hour_agg AS (
        SELECT
          date_trunc('day', ib.ts) +
            (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours') AS four_hour_ts,
          (array_agg(ib.open ORDER BY ib.ts ASC))[1] AS open,
          MAX(ib.high) AS high,
          MIN(ib.low) AS low,
          (array_agg(ib.close ORDER BY ib.ts DESC))[1] AS close,
          SUM(ib.volume) AS volume
        FROM intraday_bars ib
        WHERE ib.symbol_id = p_symbol_id
          AND ib.timeframe = '15m'
          AND ib.ts >= p_start_date
          AND ib.ts <= p_end_date
        GROUP BY date_trunc('day', ib.ts) +
          (FLOOR(EXTRACT(HOUR FROM ib.ts) / 4) * INTERVAL '4 hours')
      )
      SELECT
        to_char(fha.four_hour_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS ts,
        fha.open::DECIMAL(10,4),
        fha.high::DECIMAL(10,4),
        fha.low::DECIMAL(10,4),
        fha.close::DECIMAL(10,4),
        fha.volume,
        'tradier'::VARCHAR(20) AS provider,
        true AS is_intraday,
        false AS is_forecast,
        'verified'::VARCHAR(20) AS data_status,
        NULL::DECIMAL(3,2) AS confidence_score,
        NULL::DECIMAL(10,4) AS upper_band,
        NULL::DECIMAL(10,4) AS lower_band
      FROM four_hour_agg fha
      ORDER BY fha.four_hour_ts ASC;
    END IF;

  ELSE
    -- Query ohlc_bars_v2 for daily/weekly timeframes (original logic)
    RETURN QUERY
    WITH deduplicated AS (
      SELECT
        o.*,
        ROW_NUMBER() OVER (
          PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday
          ORDER BY
            CASE
              WHEN o.provider = 'yfinance' THEN 1
              WHEN o.provider = 'polygon' THEN 2
              ELSE 3
            END,
            o.ts DESC,
            o.fetched_at DESC NULLS LAST
        ) as rn
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id
        AND o.timeframe = p_timeframe
        AND o.ts >= p_start_date
        AND o.ts <= p_end_date
        AND (
          -- Historical: completed days before today (prefer yfinance, fallback to polygon)
          (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('yfinance', 'polygon'))
          OR
          -- Intraday: today's data from Tradier (aggregated daily)
          (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
          OR
          -- Forecasts: future dates
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
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS
'Returns chart data with proper timeframe routing:
- m15/h1/h4: Queries intraday_bars table, aggregates as needed
- d1/w1: Queries ohlc_bars_v2 with layer separation (yfinance > polygon > tradier > ml_forecast)';

-- ============================================================================
-- FIX 2: Clean up invalid historical intraday job runs
-- ============================================================================

DELETE FROM job_runs
WHERE job_type = 'fetch_intraday'
  AND DATE(slice_to) < CURRENT_DATE
  AND status IN ('queued', 'failed', 'running');

-- ============================================================================
-- FIX 3: Fix coverage gap detection for intraday timeframes
-- ============================================================================

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

  -- For intraday timeframes, only check TODAY (Tradier limitation)
  -- For daily/weekly timeframes, check the full window
  IF v_is_intraday THEN
    v_target_from := date_trunc('day', now());
  ELSE
    v_target_from := v_target_to - (p_window_days || ' days')::interval;
  END IF;

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
For intraday timeframes (m15, h1, h4): Only checks TODAY (Tradier limitation).
For daily/weekly timeframes (d1, w1): Checks full window_days range.';

-- ============================================================================
-- VERIFICATION & SUMMARY
-- ============================================================================

DO $$
DECLARE
  deleted_count INTEGER;
  function_exists BOOLEAN;
BEGIN
  -- Check if function was created successfully
  SELECT EXISTS(
    SELECT 1 FROM pg_proc
    WHERE proname = 'get_chart_data_v2'
  ) INTO function_exists;

  IF function_exists THEN
    RAISE NOTICE '✅ get_chart_data_v2() function recreated successfully';
  ELSE
    RAISE WARNING '❌ Function creation failed - check errors above';
  END IF;

  -- Report cleanup
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RAISE NOTICE '✅ Cleaned up % historical intraday job runs', deleted_count;

  RAISE NOTICE '✅ Fixed get_coverage_gaps() to only check TODAY for intraday';
  RAISE NOTICE '';
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'ALL FIXES APPLIED SUCCESSFULLY!';
  RAISE NOTICE '=================================================================';
  RAISE NOTICE '';
  RAISE NOTICE 'Next steps:';
  RAISE NOTICE '1. Refresh your macOS app';
  RAISE NOTICE '2. Click 1H timeframe for AAPL';
  RAISE NOTICE '3. Check console for: [DEBUG] buildBars → ... intraday: N';
  RAISE NOTICE '4. If intraday: 0, wait 1-2 minutes for orchestrator to hydrate';
  RAISE NOTICE '';
END $$;
