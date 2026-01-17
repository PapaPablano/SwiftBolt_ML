-- Migration: Watchlist Limits & Backfill Helpers
-- Adds:
--   1. 50-symbol per user limit trigger
--   2. get_all_watchlist_symbols() function for backfill jobs
--   3. options_chain_snapshots table for nightly options data

-- ============================================================================
-- 1. WATCHLIST LIMITS (50 symbols per user)
-- ============================================================================

-- Function to check watchlist item count before insert
CREATE OR REPLACE FUNCTION check_watchlist_item_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_current_count INTEGER;
    v_max_items INTEGER := 50;
BEGIN
    -- Get the user_id from the watchlist being modified
    SELECT user_id INTO v_user_id
    FROM watchlists
    WHERE id = NEW.watchlist_id;

    -- Count current items across all user's watchlists
    SELECT COUNT(*) INTO v_current_count
    FROM watchlist_items wi
    JOIN watchlists w ON wi.watchlist_id = w.id
    WHERE w.user_id = v_user_id;

    -- Check limit
    IF v_current_count >= v_max_items THEN
        RAISE EXCEPTION 'Watchlist limit exceeded: Maximum % symbols per user', v_max_items;
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger: Enforce 50-symbol limit per user
DROP TRIGGER IF EXISTS enforce_watchlist_item_limit ON watchlist_items;
CREATE TRIGGER enforce_watchlist_item_limit
    BEFORE INSERT ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION check_watchlist_item_limit();

COMMENT ON FUNCTION check_watchlist_item_limit IS 'Enforces 50-symbol maximum per user across all watchlists';

-- ============================================================================
-- 2. HELPER FUNCTIONS FOR BACKFILL JOBS
-- ============================================================================

-- Function: Get all unique symbols from all user watchlists (for nightly jobs)
-- Returns distinct symbols up to a system-wide cap (200)
CREATE OR REPLACE FUNCTION get_all_watchlist_symbols(p_limit INTEGER DEFAULT 200)
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (s.ticker)
        s.id as symbol_id,
        s.ticker
    FROM watchlist_items wi
    JOIN watchlists w ON wi.watchlist_id = w.id
    JOIN symbols s ON wi.symbol_id = s.id
    ORDER BY s.ticker, wi.added_at ASC
    LIMIT p_limit;
END;
$$;

COMMENT ON FUNCTION get_all_watchlist_symbols IS 'Returns all unique symbols from user watchlists (capped at 200 for nightly jobs)';

-- Function: Get symbols with their latest OHLC timestamp (for incremental backfill)
CREATE OR REPLACE FUNCTION get_watchlist_symbols_with_ohlc_status(p_timeframe TEXT DEFAULT 'd1')
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    latest_bar_ts TIMESTAMPTZ,
    bar_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id as symbol_id,
        s.ticker,
        MAX(ob.ts) as latest_bar_ts,
        COUNT(ob.id) as bar_count
    FROM (
        SELECT DISTINCT wi.symbol_id
        FROM watchlist_items wi
    ) ws
    JOIN symbols s ON ws.symbol_id = s.id
    LEFT JOIN ohlc_bars ob ON ob.symbol_id = s.id AND ob.timeframe = p_timeframe::timeframe
    GROUP BY s.id, s.ticker
    ORDER BY s.ticker;
END;
$$;

COMMENT ON FUNCTION get_watchlist_symbols_with_ohlc_status IS 'Returns watchlist symbols with their OHLC data status for incremental backfill';

-- ============================================================================
-- 3. OPTIONS CHAIN SNAPSHOTS TABLE
-- ============================================================================

-- Table for storing nightly options chain snapshots
CREATE TABLE IF NOT EXISTS options_chain_snapshots (
    id BIGSERIAL PRIMARY KEY,
    underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    expiry DATE NOT NULL,
    strike NUMERIC(20, 6) NOT NULL,
    side option_side NOT NULL,

    -- Pricing data
    bid NUMERIC(20, 6),
    ask NUMERIC(20, 6),
    mark NUMERIC(20, 6),
    last_price NUMERIC(20, 6),

    -- Volume & interest
    volume INTEGER DEFAULT 0,
    open_interest INTEGER DEFAULT 0,

    -- Greeks
    implied_vol NUMERIC(10, 6),
    delta NUMERIC(10, 6),
    gamma NUMERIC(10, 6),
    theta NUMERIC(10, 6),
    vega NUMERIC(10, 6),
    rho NUMERIC(10, 6),

    -- Metadata
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint: one snapshot per contract per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_options_snapshots_unique
    ON options_chain_snapshots(underlying_symbol_id, expiry, strike, side, snapshot_date);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_options_snapshots_underlying
    ON options_chain_snapshots(underlying_symbol_id);
CREATE INDEX IF NOT EXISTS idx_options_snapshots_date
    ON options_chain_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_options_snapshots_expiry
    ON options_chain_snapshots(expiry);

-- Enable RLS
ALTER TABLE options_chain_snapshots ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "options_snapshots_select_authenticated" ON options_chain_snapshots
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "options_snapshots_service_all" ON options_chain_snapshots
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE options_chain_snapshots IS 'Nightly options chain snapshot data for historical analysis and ML training';

-- ============================================================================
-- 4. HELPER FUNCTION FOR OPTIONS NIGHTLY JOB
-- ============================================================================

-- Function: Get symbols that need options snapshot (no snapshot today)
CREATE OR REPLACE FUNCTION get_symbols_needing_options_snapshot()
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    last_snapshot_date DATE
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id as symbol_id,
        s.ticker,
        MAX(ocs.snapshot_date) as last_snapshot_date
    FROM (
        SELECT DISTINCT wi.symbol_id
        FROM watchlist_items wi
    ) ws
    JOIN symbols s ON ws.symbol_id = s.id
    LEFT JOIN options_chain_snapshots ocs ON ocs.underlying_symbol_id = s.id
    GROUP BY s.id, s.ticker
    HAVING MAX(ocs.snapshot_date) IS NULL
        OR MAX(ocs.snapshot_date) < CURRENT_DATE
    ORDER BY s.ticker;
END;
$$;

COMMENT ON FUNCTION get_symbols_needing_options_snapshot IS 'Returns watchlist symbols that need a fresh options snapshot today';

-- ============================================================================
-- 5. CLEANUP FUNCTION FOR OLD SNAPSHOTS
-- ============================================================================

-- Function: Cleanup old options snapshots (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_options_snapshots(p_days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_deleted INTEGER;
BEGIN
    DELETE FROM options_chain_snapshots
    WHERE snapshot_date < CURRENT_DATE - p_days_to_keep;

    GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;

    RETURN v_rows_deleted;
END;
$$;

COMMENT ON FUNCTION cleanup_old_options_snapshots IS 'Removes options snapshots older than specified days (default 30)';

-- Grant execution to service role
GRANT EXECUTE ON FUNCTION get_all_watchlist_symbols TO service_role;
GRANT EXECUTE ON FUNCTION get_watchlist_symbols_with_ohlc_status TO service_role;
GRANT EXECUTE ON FUNCTION get_symbols_needing_options_snapshot TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_old_options_snapshots TO service_role;
