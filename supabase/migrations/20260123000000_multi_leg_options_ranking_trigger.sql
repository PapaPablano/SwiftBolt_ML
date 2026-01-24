-- Migration: Auto-queue options ranking for multi-leg strategy symbols
-- This ensures that when a multi-leg strategy is created, the underlying symbol
-- is automatically added to the options ranking refresh list
--
-- Date: 2026-01-23
-- Issue: MU data not current - multi-leg strategies need options data refresh

-- ============================================================================
-- FUNCTION: Queue ranking job when multi-leg strategy is created
-- ============================================================================

CREATE OR REPLACE FUNCTION queue_ranking_on_multi_leg_create()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_ticker TEXT;
    v_existing_job_id UUID;
BEGIN
    -- Get the ticker for the underlying symbol
    SELECT ticker INTO v_ticker
    FROM symbols
    WHERE id = NEW.underlying_symbol_id;
    
    -- If ticker not found, skip (shouldn't happen but defensive)
    IF v_ticker IS NULL THEN
        RAISE WARNING 'Symbol ID % not found for multi-leg strategy %', NEW.underlying_symbol_id, NEW.id;
        RETURN NEW;
    END IF;
    
    -- Check if there's already a pending/running ranking job for this symbol within the last hour
    SELECT id INTO v_existing_job_id
    FROM ranking_jobs
    WHERE symbol = v_ticker
      AND status IN ('pending', 'running')
      AND created_at > NOW() - INTERVAL '1 hour';
    
    -- Only queue if no recent job exists (avoid duplicates)
    IF v_existing_job_id IS NULL THEN
        -- Queue ranking job with high priority (priority 2 = higher than watchlist default)
        PERFORM queue_ranking_job(v_ticker, 2);
        
        RAISE NOTICE 'Queued options ranking job for % (multi-leg strategy: %)', v_ticker, NEW.id;
    ELSE
        RAISE DEBUG 'Ranking job already queued for % (job_id: %)', v_ticker, v_existing_job_id;
    END IF;
    
    RETURN NEW;
END;
$$;

-- ============================================================================
-- TRIGGER: Auto-queue ranking when multi-leg strategy created
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_queue_ranking_on_multi_leg_create ON options_strategies;

CREATE TRIGGER trigger_queue_ranking_on_multi_leg_create
    AFTER INSERT ON options_strategies
    FOR EACH ROW
    WHEN (NEW.status = 'open')  -- Only queue for open strategies
    EXECUTE FUNCTION queue_ranking_on_multi_leg_create();

-- ============================================================================
-- FUNCTION: Also queue ranking when strategy is reopened
-- ============================================================================

CREATE OR REPLACE FUNCTION queue_ranking_on_multi_leg_reopen()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_ticker TEXT;
    v_existing_job_id UUID;
BEGIN
    -- Only trigger when status changes from closed/expired to open
    IF NEW.status = 'open' AND OLD.status IN ('closed', 'expired') THEN
        -- Get the ticker for the underlying symbol
        SELECT ticker INTO v_ticker
        FROM symbols
        WHERE id = NEW.underlying_symbol_id;
        
        IF v_ticker IS NULL THEN
            RETURN NEW;
        END IF;
        
        -- Check if there's already a pending/running ranking job
        SELECT id INTO v_existing_job_id
        FROM ranking_jobs
        WHERE symbol = v_ticker
          AND status IN ('pending', 'running')
          AND created_at > NOW() - INTERVAL '1 hour';
        
        -- Only queue if no recent job exists
        IF v_existing_job_id IS NULL THEN
            PERFORM queue_ranking_job(v_ticker, 2);
            RAISE NOTICE 'Queued options ranking job for % (multi-leg strategy reopened: %)', v_ticker, NEW.id;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$;

-- ============================================================================
-- TRIGGER: Auto-queue ranking when strategy is reopened
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_queue_ranking_on_multi_leg_reopen ON options_strategies;

CREATE TRIGGER trigger_queue_ranking_on_multi_leg_reopen
    AFTER UPDATE ON options_strategies
    FOR EACH ROW
    WHEN (
        NEW.status = 'open' 
        AND OLD.status IN ('closed', 'expired')
    )
    EXECUTE FUNCTION queue_ranking_on_multi_leg_reopen();

-- ============================================================================
-- FUNCTION: Get symbols from active multi-leg strategies
-- ============================================================================
-- This function can be used by ranking automation to include multi-leg symbols
-- even if they're not in watchlist

CREATE OR REPLACE FUNCTION get_multi_leg_strategy_symbols()
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    strategy_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        s.id as symbol_id,
        s.ticker,
        COUNT(DISTINCT os.id) as strategy_count
    FROM options_strategies os
    JOIN symbols s ON s.id = os.underlying_symbol_id
    WHERE os.status = 'open'
    GROUP BY s.id, s.ticker
    ORDER BY strategy_count DESC, s.ticker;
END;
$$;

-- ============================================================================
-- FUNCTION: Queue ranking jobs for all active multi-leg strategy symbols
-- ============================================================================
-- This can be called by scheduled jobs to ensure multi-leg symbols are ranked

CREATE OR REPLACE FUNCTION queue_multi_leg_strategy_ranking_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol RECORD;
    v_count INTEGER := 0;
BEGIN
    FOR v_symbol IN
        SELECT DISTINCT s.ticker
        FROM options_strategies os
        JOIN symbols s ON s.id = os.underlying_symbol_id
        WHERE os.status = 'open'
    LOOP
        -- Check if job already queued recently
        IF NOT EXISTS (
            SELECT 1
            FROM ranking_jobs
            WHERE symbol = v_symbol.ticker
              AND status IN ('pending', 'running')
              AND created_at > NOW() - INTERVAL '1 hour'
        ) THEN
            PERFORM queue_ranking_job(v_symbol.ticker, 2);
            v_count := v_count + 1;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Queued ranking jobs for % multi-leg strategy symbols', v_count;
    RETURN v_count;
END;
$$;

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT EXECUTE ON FUNCTION queue_ranking_on_multi_leg_create TO service_role;
GRANT EXECUTE ON FUNCTION queue_ranking_on_multi_leg_reopen TO service_role;
GRANT EXECUTE ON FUNCTION get_multi_leg_strategy_symbols TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION queue_multi_leg_strategy_ranking_jobs TO service_role;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION queue_ranking_on_multi_leg_create IS 
'Automatically queues an options ranking job when a multi-leg strategy is created. Ensures underlying symbol gets options data refresh.';

COMMENT ON FUNCTION queue_ranking_on_multi_leg_reopen IS 
'Automatically queues an options ranking job when a multi-leg strategy is reopened from closed/expired status.';

COMMENT ON FUNCTION get_multi_leg_strategy_symbols IS 
'Returns all unique symbols that have active (open) multi-leg strategies, with strategy count per symbol.';

COMMENT ON FUNCTION queue_multi_leg_strategy_ranking_jobs IS 
'Queues ranking jobs for all symbols with active multi-leg strategies. Can be called by scheduled jobs to ensure multi-leg symbols are always ranked.';

COMMENT ON TRIGGER trigger_queue_ranking_on_multi_leg_create ON options_strategies IS 
'Automatically queues options ranking job when a new open multi-leg strategy is created.';

COMMENT ON TRIGGER trigger_queue_ranking_on_multi_leg_reopen ON options_strategies IS 
'Automatically queues options ranking job when a multi-leg strategy is reopened.';
