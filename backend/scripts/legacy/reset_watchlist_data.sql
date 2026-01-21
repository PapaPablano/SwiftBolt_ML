-- Reset and Reload Watchlist Data (Post-Spec8 Cleanup)
-- This script resets watchlist data and triggers fresh loads using Alpaca-only strategy
-- Run this in Supabase SQL Editor

-- ============================================================================
-- PART 1: Get Current Watchlist Symbols
-- ============================================================================

DO $$
DECLARE
  v_symbol_record RECORD;
  v_count INT := 0;
BEGIN
  RAISE NOTICE '========================================';
  RAISE NOTICE 'WATCHLIST DATA RESET - Starting';
  RAISE NOTICE '========================================';
  RAISE NOTICE '';
  
  -- Show current watchlist
  RAISE NOTICE 'Current watchlist symbols:';
  FOR v_symbol_record IN
    SELECT DISTINCT s.ticker, s.id
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    ORDER BY s.ticker
  LOOP
    v_count := v_count + 1;
    RAISE NOTICE '  %: %', v_count, v_symbol_record.ticker;
  END LOOP;
  
  RAISE NOTICE '';
  RAISE NOTICE 'Total symbols in watchlist: %', v_count;
  RAISE NOTICE '';
END $$;

-- ============================================================================
-- PART 2: Clear Old Data (Optional - Uncomment to Clear)
-- ============================================================================

-- CAUTION: This will delete existing OHLC data for watchlist symbols
-- Only uncomment if you want a complete reset

/*
DO $$
DECLARE
  v_symbol_id UUID;
  v_ticker TEXT;
  v_deleted_count INT;
BEGIN
  RAISE NOTICE '========================================';
  RAISE NOTICE 'CLEARING OLD DATA';
  RAISE NOTICE '========================================';
  
  FOR v_symbol_id, v_ticker IN
    SELECT DISTINCT s.id, s.ticker
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
  LOOP
    -- Delete from ohlc_bars_v2 (keep only last 7 days for safety)
    DELETE FROM ohlc_bars_v2
    WHERE symbol_id = v_symbol_id
      AND ts < NOW() - INTERVAL '7 days';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RAISE NOTICE 'Cleared % old bars for %', v_deleted_count, v_ticker;
  END LOOP;
  
  RAISE NOTICE '';
END $$;
*/

-- ============================================================================
-- PART 3: Trigger Fresh Data Load via symbol-init
-- ============================================================================

-- This creates a temporary function to call symbol-init for each watchlist symbol
CREATE OR REPLACE FUNCTION reload_watchlist_data()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_symbol_record RECORD;
  v_results JSONB := '[]'::JSONB;
  v_result JSONB;
  v_count INT := 0;
  v_supabase_url TEXT;
  v_service_key TEXT;
BEGIN
  -- Get environment variables (these should be set in your Supabase project)
  v_supabase_url := current_setting('app.settings.supabase_url', true);
  v_service_key := current_setting('app.settings.service_role_key', true);
  
  RAISE NOTICE 'Reloading data for all watchlist symbols...';
  
  FOR v_symbol_record IN
    SELECT DISTINCT s.ticker, s.id
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    ORDER BY s.ticker
  LOOP
    v_count := v_count + 1;
    
    BEGIN
      -- Note: This queues the symbol for initialization
      -- The actual data fetch happens via symbol-init edge function
      v_result := jsonb_build_object(
        'ticker', v_symbol_record.ticker,
        'symbol_id', v_symbol_record.id,
        'status', 'queued',
        'message', 'Call symbol-init edge function to load data'
      );
      
      v_results := v_results || v_result;
      RAISE NOTICE 'Queued: % (% of total)', v_symbol_record.ticker, v_count;
      
    EXCEPTION WHEN OTHERS THEN
      v_result := jsonb_build_object(
        'ticker', v_symbol_record.ticker,
        'status', 'error',
        'error', SQLERRM
      );
      v_results := v_results || v_result;
      RAISE WARNING 'Failed to queue %: %', v_symbol_record.ticker, SQLERRM;
    END;
  END LOOP;
  
  RETURN jsonb_build_object(
    'total_symbols', v_count,
    'results', v_results,
    'next_steps', 'Call the reload-watchlist-data edge function to trigger actual data loads'
  );
END;
$$;

-- Execute the reload function
SELECT reload_watchlist_data();

-- ============================================================================
-- PART 4: Check Data Status After Reload
-- ============================================================================

-- Run this query after the edge function completes to verify data
SELECT 
  s.ticker,
  COUNT(DISTINCT CASE WHEN o.timeframe = 'd1' THEN o.ts END) as d1_bars,
  COUNT(DISTINCT CASE WHEN o.timeframe = 'h1' THEN o.ts END) as h1_bars,
  COUNT(DISTINCT CASE WHEN o.timeframe = 'm15' THEN o.ts END) as m15_bars,
  MAX(CASE WHEN o.timeframe = 'd1' THEN o.ts END) as d1_latest,
  MAX(CASE WHEN o.timeframe = 'h1' THEN o.ts END) as h1_latest,
  STRING_AGG(DISTINCT o.provider, ', ' ORDER BY o.provider) as providers
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id
GROUP BY s.ticker
ORDER BY s.ticker;

-- ============================================================================
-- PART 5: Cleanup Functions
-- ============================================================================

-- Drop the temporary reload function
DROP FUNCTION IF EXISTS reload_watchlist_data();

RAISE NOTICE '';
RAISE NOTICE '========================================';
RAISE NOTICE 'RESET COMPLETE';
RAISE NOTICE '========================================';
RAISE NOTICE 'Next step: Call the reload-watchlist-data edge function';
RAISE NOTICE 'This will trigger symbol-init for each watchlist symbol';
RAISE NOTICE '';
