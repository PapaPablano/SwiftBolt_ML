-- Migration: Watchlist Ranking Triggers
-- Automatically queue ranking jobs when symbols are added to watchlist
-- Optionally clean up rankings when symbols are removed

-- ============================================================================
-- TRIGGER: Auto-queue ranking job when symbol added to watchlist
-- ============================================================================

CREATE OR REPLACE FUNCTION auto_queue_ranking_on_watchlist_add()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
BEGIN
    -- Get the ticker for this symbol
    SELECT ticker INTO v_symbol
    FROM symbols
    WHERE id = NEW.symbol_id;

    IF v_symbol IS NOT NULL THEN
        -- Queue ranking job with high priority (2)
        PERFORM queue_ranking_job(v_symbol, 2);
        RAISE NOTICE 'Queued ranking job for % (watchlist add)', v_symbol;
    END IF;

    RETURN NEW;
END;
$$;

-- Create trigger for INSERT
DROP TRIGGER IF EXISTS trigger_ranking_on_watchlist_add ON watchlist_items;
CREATE TRIGGER trigger_ranking_on_watchlist_add
    AFTER INSERT ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION auto_queue_ranking_on_watchlist_add();

COMMENT ON FUNCTION auto_queue_ranking_on_watchlist_add IS
'Automatically queues a ranking job when a symbol is added to any watchlist';

-- ============================================================================
-- TRIGGER: Handle symbol removal from watchlist
-- ============================================================================

-- Function to check if symbol is still in ANY watchlist
CREATE OR REPLACE FUNCTION is_symbol_in_any_watchlist(p_symbol_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM watchlist_items
        WHERE symbol_id = p_symbol_id
    );
END;
$$;

-- Function to clean up rankings for symbols no longer in any watchlist
-- This is optional - you may want to keep rankings for historical reference
CREATE OR REPLACE FUNCTION cleanup_rankings_on_watchlist_remove()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
    v_still_watched BOOLEAN;
BEGIN
    -- Check if this symbol is still in any watchlist
    v_still_watched := is_symbol_in_any_watchlist(OLD.symbol_id);

    IF NOT v_still_watched THEN
        -- Get ticker for logging
        SELECT ticker INTO v_symbol
        FROM symbols
        WHERE id = OLD.symbol_id;

        -- Option 1: Delete rankings (uncomment if you want to clean up)
        -- DELETE FROM options_ranks WHERE underlying_symbol_id = OLD.symbol_id;
        -- RAISE NOTICE 'Cleaned up rankings for % (removed from all watchlists)', v_symbol;

        -- Option 2: Just log (current behavior - rankings are kept)
        RAISE NOTICE 'Symbol % removed from all watchlists (rankings preserved)', v_symbol;
    END IF;

    RETURN OLD;
END;
$$;

-- Create trigger for DELETE (optional cleanup)
DROP TRIGGER IF EXISTS trigger_cleanup_on_watchlist_remove ON watchlist_items;
CREATE TRIGGER trigger_cleanup_on_watchlist_remove
    AFTER DELETE ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_rankings_on_watchlist_remove();

COMMENT ON FUNCTION cleanup_rankings_on_watchlist_remove IS
'Handles cleanup when a symbol is removed from all watchlists (currently just logs)';

-- ============================================================================
-- VIEW: Symbols pending ranking (in watchlist but no recent rankings)
-- ============================================================================

CREATE OR REPLACE VIEW symbols_pending_ranking AS
SELECT
    symbol_id,
    ticker,
    ranking_status,
    last_ranked_at,
    priority_order
FROM (
    SELECT
        s.id as symbol_id,
        s.ticker,
        CASE
            WHEN MAX(orr.run_at) IS NULL THEN 'never_ranked'
            WHEN MAX(orr.run_at) < NOW() - INTERVAL '2 hours' THEN 'stale'
            WHEN COUNT(*) FILTER (WHERE orr.composite_rank IS NULL) > 0 THEN 'partial'
            ELSE 'fresh'
        END as ranking_status,
        MAX(orr.run_at) as last_ranked_at,
        CASE WHEN MAX(orr.run_at) IS NULL THEN 0 ELSE 1 END as priority_order
    FROM watchlist_items wi
    JOIN symbols s ON s.id = wi.symbol_id
    LEFT JOIN options_ranks orr ON orr.underlying_symbol_id = s.id
    GROUP BY s.id, s.ticker
    HAVING MAX(orr.run_at) IS NULL
        OR MAX(orr.run_at) < NOW() - INTERVAL '1 hour'
        OR COUNT(*) FILTER (WHERE orr.composite_rank IS NULL) > 0
) sub
ORDER BY priority_order, last_ranked_at ASC NULLS FIRST;

GRANT SELECT ON symbols_pending_ranking TO authenticated, service_role;

COMMENT ON VIEW symbols_pending_ranking IS
'Shows watchlist symbols that need ranking (never ranked, stale, or partial scores)';

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION auto_queue_ranking_on_watchlist_add TO service_role;
GRANT EXECUTE ON FUNCTION is_symbol_in_any_watchlist TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_rankings_on_watchlist_remove TO service_role;
