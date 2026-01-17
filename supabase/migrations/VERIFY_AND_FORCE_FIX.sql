-- ============================================================================
-- STEP 1: Check current function definition
-- ============================================================================

-- Check what's currently in the database
SELECT
  proname as function_name,
  pg_get_function_arguments(oid) as arguments,
  pg_get_function_result(oid) as returns
FROM pg_proc
WHERE proname = 'get_chart_data_v2';

-- ============================================================================
-- STEP 2: FORCE DROP all variants
-- ============================================================================

-- Drop with CASCADE to handle dependencies
DROP FUNCTION IF EXISTS get_chart_data_v2 CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR(10), TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, TEXT, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;
DROP FUNCTION IF EXISTS get_chart_data_v2(UUID, VARCHAR, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) CASCADE;

-- Verify it's gone
DO $$
DECLARE
  func_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO func_count FROM pg_proc WHERE proname = 'get_chart_data_v2';

  IF func_count = 0 THEN
    RAISE NOTICE '✅ Old function successfully dropped';
  ELSE
    RAISE WARNING '⚠️ Function still exists after DROP! Count: %', func_count;
  END IF;
END $$;

-- ============================================================================
-- STEP 3: CREATE new function with CORRECT timeframe handling
-- ============================================================================

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
BEGIN
  -- CRITICAL FIX: Accept m15/h1/h4 format from client
  v_is_intraday_tf := p_timeframe IN ('m15', 'h1', 'h4');

  IF v_is_intraday_tf THEN
    -- For 15-minute bars: direct query
    IF p_timeframe = 'm15' THEN
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

    -- For 1-hour bars: aggregate 15m to hourly
    ELSIF p_timeframe = 'h1' THEN
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

    -- For 4-hour bars: aggregate 15m to 4h blocks
    ELSIF p_timeframe = 'h4' THEN
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
    -- For daily/weekly: query ohlc_bars_v2
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
          (DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('yfinance', 'polygon'))
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
  END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STEP 4: Verify the fix
-- ============================================================================

DO $$
DECLARE
  func_exists BOOLEAN;
  test_result RECORD;
BEGIN
  -- Check function exists
  SELECT EXISTS(
    SELECT 1 FROM pg_proc WHERE proname = 'get_chart_data_v2'
  ) INTO func_exists;

  IF func_exists THEN
    RAISE NOTICE '';
    RAISE NOTICE '=================================================================';
    RAISE NOTICE '✅ SUCCESS! Function get_chart_data_v2() created';
    RAISE NOTICE '=================================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Function now accepts: m15, h1, h4, d1, w1';
    RAISE NOTICE '';
    RAISE NOTICE 'Next: Refresh your app and click 1H timeframe';
    RAISE NOTICE '';
  ELSE
    RAISE EXCEPTION '❌ FAILED: Function was not created! Check errors above.';
  END IF;
END $$;
