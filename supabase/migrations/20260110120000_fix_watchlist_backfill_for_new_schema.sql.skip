-- Migration: Fix Watchlist Auto-Backfill to Use New job_definitions Schema
-- The old seed_intraday_backfill_2yr function writes to backfill_jobs/backfill_chunks
-- This migration replaces it to use job_definitions/job_runs instead

-- ============================================================================
-- Drop old trigger and functions that reference backfill_jobs
-- ============================================================================

DROP TRIGGER IF EXISTS watchlist_auto_backfill_trigger ON watchlist_items;
DROP FUNCTION IF EXISTS trigger_backfill_on_watchlist_add() CASCADE;
DROP FUNCTION IF EXISTS seed_backfill_for_symbol(UUID, TEXT[]) CASCADE;
DROP FUNCTION IF EXISTS backfill_all_watchlist_symbols(TEXT[]) CASCADE;
DROP FUNCTION IF EXISTS get_symbol_backfill_status(TEXT) CASCADE;
DROP FUNCTION IF EXISTS request_symbol_backfill(TEXT, TEXT[]) CASCADE;

-- ============================================================================
-- New Function: Seed Job Definition for Symbol (New Schema)
-- ============================================================================

CREATE OR REPLACE FUNCTION seed_job_definition_for_symbol(
  p_symbol_id UUID,
  p_timeframes TEXT[] DEFAULT ARRAY['h1']
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_ticker TEXT;
  v_timeframe TEXT;
  v_job_def_id UUID;
  v_results JSONB := '[]'::JSONB;
  v_job_result JSONB;
  v_job_type TEXT;
BEGIN
  -- Get the ticker symbol
  SELECT ticker INTO v_ticker FROM symbols WHERE id = p_symbol_id;

  IF v_ticker IS NULL THEN
    RAISE EXCEPTION 'Symbol with ID % not found', p_symbol_id;
  END IF;

  -- Create job definitions for each requested timeframe
  FOREACH v_timeframe IN ARRAY p_timeframes
  LOOP
    BEGIN
      -- Determine job type based on timeframe
      v_job_type := CASE 
        WHEN v_timeframe IN ('15m', '1h', '4h', 'h1', 'h4', 'm15') THEN 'fetch_intraday'
        ELSE 'fetch_historical'
      END;

      -- Normalize timeframe names
      v_timeframe := CASE v_timeframe
        WHEN '1h' THEN 'h1'
        WHEN '4h' THEN 'h4'
        WHEN '15m' THEN 'm15'
        ELSE v_timeframe
      END;

      -- Upsert job definition
      INSERT INTO job_definitions (symbol, timeframe, job_type, window_days, priority, enabled)
      VALUES (v_ticker, v_timeframe, v_job_type, 730, 150, true)
      ON CONFLICT (symbol, timeframe, job_type) 
      DO UPDATE SET 
        window_days = GREATEST(job_definitions.window_days, 730),
        priority = GREATEST(job_definitions.priority, 150),
        enabled = true,
        updated_at = NOW()
      RETURNING id INTO v_job_def_id;

      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'job_type', v_job_type,
        'job_def_id', v_job_def_id,
        'status', 'created'
      );

      v_results := v_results || v_job_result;

    EXCEPTION WHEN OTHERS THEN
      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'status', 'error',
        'error', SQLERRM
      );

      v_results := v_results || v_job_result;
    END;
  END LOOP;

  RETURN jsonb_build_object(
    'symbol_id', p_symbol_id,
    'ticker', v_ticker,
    'jobs', v_results
  );
END;
$$;

COMMENT ON FUNCTION seed_job_definition_for_symbol IS
'Creates job definitions for a symbol using the new job_definitions schema. Replaces seed_backfill_for_symbol.';

-- ============================================================================
-- New Trigger Function for Watchlist Add
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_job_definition_on_watchlist_add()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_result JSONB;
BEGIN
  -- Create job definition for the newly added symbol (h1 timeframe by default)
  BEGIN
    v_result := seed_job_definition_for_symbol(NEW.symbol_id, ARRAY['h1']);

    RAISE NOTICE 'Auto job definition created for watchlist addition: %', v_result;

  EXCEPTION WHEN OTHERS THEN
    -- Don't fail the watchlist insert if job creation fails
    RAISE WARNING 'Failed to create job definition for symbol_id %: %', NEW.symbol_id, SQLERRM;
  END;

  RETURN NEW;
END;
$$;

-- Create trigger on watchlist_items
CREATE TRIGGER watchlist_auto_job_definition_trigger
  AFTER INSERT ON watchlist_items
  FOR EACH ROW
  EXECUTE FUNCTION trigger_job_definition_on_watchlist_add();

COMMENT ON TRIGGER watchlist_auto_job_definition_trigger ON watchlist_items IS
'Automatically creates job definitions when a symbol is added to any watchlist';

-- ============================================================================
-- New Function: Get Job Definition Status for Symbol
-- ============================================================================

CREATE OR REPLACE FUNCTION get_symbol_job_status(p_ticker TEXT)
RETURNS TABLE(
  timeframe TEXT,
  job_type TEXT,
  enabled BOOLEAN,
  window_days INT,
  priority INT,
  total_runs INT,
  success_runs INT,
  running_runs INT,
  queued_runs INT,
  failed_runs INT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)
LANGUAGE sql STABLE
AS $$
  SELECT
    jd.timeframe,
    jd.job_type,
    jd.enabled,
    jd.window_days,
    jd.priority,
    (SELECT COUNT(*) FROM job_runs WHERE job_def_id = jd.id) as total_runs,
    (SELECT COUNT(*) FROM job_runs WHERE job_def_id = jd.id AND status = 'success') as success_runs,
    (SELECT COUNT(*) FROM job_runs WHERE job_def_id = jd.id AND status = 'running') as running_runs,
    (SELECT COUNT(*) FROM job_runs WHERE job_def_id = jd.id AND status = 'queued') as queued_runs,
    (SELECT COUNT(*) FROM job_runs WHERE job_def_id = jd.id AND status = 'failed') as failed_runs,
    jd.created_at,
    jd.updated_at
  FROM job_definitions jd
  WHERE jd.symbol = p_ticker
  ORDER BY jd.timeframe;
$$;

COMMENT ON FUNCTION get_symbol_job_status IS
'Returns job definition status for a specific symbol. Replaces get_symbol_backfill_status.';

-- ============================================================================
-- New Function: Manually Request Job Definition from UI
-- ============================================================================

CREATE OR REPLACE FUNCTION request_symbol_job_definition(
  p_ticker TEXT,
  p_timeframes TEXT[] DEFAULT ARRAY['h1']
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_symbol_id UUID;
  v_result JSONB;
BEGIN
  -- Verify the user is authenticated
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Authentication required';
  END IF;

  -- Get symbol_id
  SELECT id INTO v_symbol_id FROM symbols WHERE ticker = p_ticker;

  IF v_symbol_id IS NULL THEN
    RAISE EXCEPTION 'Symbol % not found', p_ticker;
  END IF;

  -- Create job definitions
  v_result := seed_job_definition_for_symbol(v_symbol_id, p_timeframes);

  RETURN v_result;
END;
$$;

COMMENT ON FUNCTION request_symbol_job_definition IS
'User-facing function to manually request job definitions for a symbol. Requires authentication.';

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION request_symbol_job_definition TO authenticated;
GRANT EXECUTE ON FUNCTION get_symbol_job_status TO authenticated;

-- ============================================================================
-- Backfill Job Definitions for Existing Watchlist Items
-- ============================================================================

DO $$
DECLARE
  v_symbol_id UUID;
  v_ticker TEXT;
  v_result JSONB;
  v_count INT := 0;
BEGIN
  -- Create job definitions for all symbols currently in watchlists
  FOR v_symbol_id, v_ticker IN
    SELECT DISTINCT wi.symbol_id, s.ticker
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    WHERE NOT EXISTS (
      SELECT 1 FROM job_definitions jd
      WHERE jd.symbol = s.ticker AND jd.timeframe = 'h1' AND jd.job_type = 'fetch_intraday'
    )
    ORDER BY s.ticker
  LOOP
    v_count := v_count + 1;
    
    BEGIN
      v_result := seed_job_definition_for_symbol(v_symbol_id, ARRAY['h1']);
      RAISE NOTICE 'Created job definition for %: %', v_ticker, v_result;
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'Failed to create job definition for %: %', v_ticker, SQLERRM;
    END;
  END LOOP;

  IF v_count > 0 THEN
    RAISE NOTICE 'Created job definitions for % watchlist symbols', v_count;
  ELSE
    RAISE NOTICE 'All watchlist items already have job definitions';
  END IF;
END $$;
