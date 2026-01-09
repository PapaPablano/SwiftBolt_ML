-- Migration: Automatic Backfill for Watchlist Stocks
-- When users add stocks to their watchlist, automatically seed 2-year backfill jobs

-- ============================================================================
-- PART 1: Function to Seed Backfill for a Single Symbol
-- ============================================================================

CREATE OR REPLACE FUNCTION seed_backfill_for_symbol(
  p_symbol_id UUID,
  p_timeframes TEXT[] DEFAULT ARRAY['h1']
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_ticker TEXT;
  v_timeframe TEXT;
  v_job_id UUID;
  v_results JSONB := '[]'::JSONB;
  v_job_result JSONB;
BEGIN
  -- Get the ticker symbol
  SELECT ticker INTO v_ticker FROM symbols WHERE id = p_symbol_id;

  IF v_ticker IS NULL THEN
    RAISE EXCEPTION 'Symbol with ID % not found', p_symbol_id;
  END IF;

  -- Seed backfill jobs for each requested timeframe
  FOREACH v_timeframe IN ARRAY p_timeframes
  LOOP
    BEGIN
      -- Call the existing seed function
      v_job_id := seed_intraday_backfill_2yr(v_ticker, v_timeframe);

      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'job_id', v_job_id,
        'status', 'created'
      );

      v_results := v_results || v_job_result;

    EXCEPTION WHEN OTHERS THEN
      -- Log error but continue with other timeframes
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

COMMENT ON FUNCTION seed_backfill_for_symbol IS
'Seeds 2-year intraday backfill jobs for a specific symbol. Callable from UI.';

-- ============================================================================
-- PART 2: Trigger Function for Automatic Backfill on Watchlist Add
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_backfill_on_watchlist_add()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_result JSONB;
BEGIN
  -- Seed backfill for the newly added symbol (h1 timeframe by default)
  -- Use h1 as it's a good balance between data granularity and API cost
  BEGIN
    v_result := seed_backfill_for_symbol(NEW.symbol_id, ARRAY['h1']);

    RAISE NOTICE 'Auto-backfill triggered for watchlist addition: %', v_result;

  EXCEPTION WHEN OTHERS THEN
    -- Don't fail the watchlist insert if backfill fails
    RAISE WARNING 'Failed to trigger auto-backfill for symbol_id %: %', NEW.symbol_id, SQLERRM;
  END;

  RETURN NEW;
END;
$$;

-- Create trigger on watchlist_items
DROP TRIGGER IF EXISTS watchlist_auto_backfill_trigger ON watchlist_items;

CREATE TRIGGER watchlist_auto_backfill_trigger
  AFTER INSERT ON watchlist_items
  FOR EACH ROW
  EXECUTE FUNCTION trigger_backfill_on_watchlist_add();

COMMENT ON TRIGGER watchlist_auto_backfill_trigger ON watchlist_items IS
'Automatically seeds 2-year backfill jobs when a symbol is added to any watchlist';

-- ============================================================================
-- PART 3: Function to Backfill All Current Watchlist Items
-- ============================================================================

CREATE OR REPLACE FUNCTION backfill_all_watchlist_symbols(
  p_timeframes TEXT[] DEFAULT ARRAY['h1']
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_symbol_id UUID;
  v_ticker TEXT;
  v_all_results JSONB := '[]'::JSONB;
  v_symbol_result JSONB;
  v_count INT := 0;
BEGIN
  -- Get all unique symbols from all watchlists
  FOR v_symbol_id, v_ticker IN
    SELECT DISTINCT wi.symbol_id, s.ticker
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    ORDER BY s.ticker
  LOOP
    v_count := v_count + 1;

    BEGIN
      v_symbol_result := seed_backfill_for_symbol(v_symbol_id, p_timeframes);
      v_all_results := v_all_results || v_symbol_result;

    EXCEPTION WHEN OTHERS THEN
      v_symbol_result := jsonb_build_object(
        'symbol_id', v_symbol_id,
        'ticker', v_ticker,
        'status', 'error',
        'error', SQLERRM
      );
      v_all_results := v_all_results || v_symbol_result;
    END;
  END LOOP;

  RETURN jsonb_build_object(
    'total_symbols', v_count,
    'timeframes', p_timeframes,
    'results', v_all_results
  );
END;
$$;

COMMENT ON FUNCTION backfill_all_watchlist_symbols IS
'Seeds 2-year backfill jobs for all symbols in all watchlists. Run once to backfill existing watchlist items.';

-- ============================================================================
-- PART 4: User-Facing Function to Check Backfill Status for a Symbol
-- ============================================================================

CREATE OR REPLACE FUNCTION get_symbol_backfill_status(p_ticker TEXT)
RETURNS TABLE(
  timeframe TEXT,
  status TEXT,
  progress INT,
  total_chunks INT,
  done_chunks INT,
  pending_chunks INT,
  error_chunks INT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)
LANGUAGE sql STABLE
AS $$
  SELECT
    bj.timeframe,
    bj.status,
    bj.progress,
    (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = bj.id) as total_chunks,
    (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = bj.id AND status = 'done') as done_chunks,
    (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = bj.id AND status = 'pending') as pending_chunks,
    (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = bj.id AND status = 'error') as error_chunks,
    bj.created_at,
    bj.updated_at
  FROM backfill_jobs bj
  WHERE bj.symbol = p_ticker
  ORDER BY bj.timeframe;
$$;

COMMENT ON FUNCTION get_symbol_backfill_status IS
'Returns backfill job status for a specific symbol. Useful for UI progress display.';

-- ============================================================================
-- PART 5: Function to Manually Trigger Backfill from UI
-- ============================================================================

CREATE OR REPLACE FUNCTION request_symbol_backfill(
  p_ticker TEXT,
  p_timeframes TEXT[] DEFAULT ARRAY['h1']
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER -- Allow authenticated users to call this
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

  -- Seed the backfill
  v_result := seed_backfill_for_symbol(v_symbol_id, p_timeframes);

  RETURN v_result;
END;
$$;

COMMENT ON FUNCTION request_symbol_backfill IS
'User-facing function to manually request backfill for a symbol. Requires authentication.';

-- Grant execute to authenticated users
GRANT EXECUTE ON FUNCTION request_symbol_backfill TO authenticated;
GRANT EXECUTE ON FUNCTION get_symbol_backfill_status TO authenticated;

-- ============================================================================
-- PART 6: Backfill Existing Watchlist Items (Run Once)
-- ============================================================================

-- This will seed backfill jobs for all symbols currently in watchlists
-- Comment this out after first run if you don't want to re-run it
DO $$
DECLARE
  v_result JSONB;
BEGIN
  -- Only run if there are watchlist items without backfill jobs
  IF EXISTS (
    SELECT 1
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    WHERE NOT EXISTS (
      SELECT 1 FROM backfill_jobs bj
      WHERE bj.symbol = s.ticker AND bj.timeframe = 'h1'
    )
  ) THEN
    RAISE NOTICE 'Seeding backfill jobs for existing watchlist items...';
    SELECT backfill_all_watchlist_symbols(ARRAY['h1']) INTO v_result;
    RAISE NOTICE 'Backfill seeding complete: %', v_result;
  ELSE
    RAISE NOTICE 'All watchlist items already have backfill jobs';
  END IF;
END $$;
