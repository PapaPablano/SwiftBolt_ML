-- Migration: Hourly Ranking Automation
-- Sets up functions to queue ranking jobs for all watchlist symbols
-- Designed to be called hourly to keep rankings fresh with Momentum Framework scores

-- Function: Queue a ranking job for a symbol
CREATE OR REPLACE FUNCTION queue_ranking_job(p_symbol TEXT, p_priority INTEGER DEFAULT 0)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- Check if job already pending/running for this symbol within the hour
    SELECT id INTO v_job_id
    FROM ranking_jobs
    WHERE symbol = p_symbol
      AND status IN ('pending', 'running')
      AND created_at > NOW() - INTERVAL '1 hour';

    IF v_job_id IS NOT NULL THEN
        RETURN v_job_id;  -- Return existing job
    END IF;

    -- Create new job
    INSERT INTO ranking_jobs (symbol, status, priority, requested_by)
    VALUES (p_symbol, 'pending', p_priority, 'hourly_scheduler')
    RETURNING id INTO v_job_id;

    RETURN v_job_id;
END;
$$;

-- Function: Queue ranking jobs for ALL watchlist symbols
CREATE OR REPLACE FUNCTION queue_all_watchlist_ranking_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
    v_count INTEGER := 0;
BEGIN
    -- Queue jobs for each unique symbol in watchlists
    FOR v_symbol IN
        SELECT DISTINCT s.ticker
        FROM watchlist_items wi
        JOIN symbols s ON s.id = wi.symbol_id
    LOOP
        PERFORM queue_ranking_job(v_symbol, 1);  -- Priority 1 for watchlist items
        v_count := v_count + 1;
    END LOOP;

    RAISE NOTICE 'Queued ranking jobs for % watchlist symbols', v_count;
    RETURN v_count;
END;
$$;

-- Function: Queue ranking jobs for symbols with stale rankings
-- (Rankings older than 1 hour or NULL momentum scores)
CREATE OR REPLACE FUNCTION queue_stale_ranking_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
    v_count INTEGER := 0;
BEGIN
    -- Find symbols in watchlists with stale or missing rankings
    FOR v_symbol IN
        SELECT DISTINCT s.ticker
        FROM watchlist_items wi
        JOIN symbols s ON s.id = wi.symbol_id
        LEFT JOIN options_ranks orr ON orr.underlying_symbol_id = s.id
        WHERE orr.id IS NULL
           OR orr.composite_rank IS NULL
           OR orr.run_at < NOW() - INTERVAL '1 hour'
        GROUP BY s.ticker
    LOOP
        PERFORM queue_ranking_job(v_symbol, 2);  -- Higher priority for stale
        v_count := v_count + 1;
    END LOOP;

    RAISE NOTICE 'Queued ranking jobs for % symbols with stale rankings', v_count;
    RETURN v_count;
END;
$$;

-- View: Watchlist symbols with ranking status
CREATE OR REPLACE VIEW watchlist_ranking_status AS
SELECT
    s.ticker,
    s.id as symbol_id,
    COUNT(DISTINCT orr.id) as total_ranks,
    COUNT(DISTINCT orr.id) FILTER (WHERE orr.composite_rank IS NOT NULL) as scored_ranks,
    MAX(orr.run_at) as last_ranked_at,
    CASE
        WHEN MAX(orr.run_at) IS NULL THEN 'never'
        WHEN MAX(orr.run_at) < NOW() - INTERVAL '2 hours' THEN 'stale'
        WHEN COUNT(*) FILTER (WHERE orr.composite_rank IS NULL) > 0 THEN 'partial'
        ELSE 'fresh'
    END as status
FROM watchlist_items wi
JOIN symbols s ON s.id = wi.symbol_id
LEFT JOIN options_ranks orr ON orr.underlying_symbol_id = s.id
GROUP BY s.id, s.ticker
ORDER BY s.ticker;

GRANT SELECT ON watchlist_ranking_status TO authenticated;

-- Function: Get ranking health summary
CREATE OR REPLACE FUNCTION get_ranking_health()
RETURNS TABLE (
    total_symbols INTEGER,
    fresh_count INTEGER,
    stale_count INTEGER,
    never_ranked_count INTEGER,
    partial_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER as total_symbols,
        COUNT(*) FILTER (WHERE status = 'fresh')::INTEGER as fresh_count,
        COUNT(*) FILTER (WHERE status = 'stale')::INTEGER as stale_count,
        COUNT(*) FILTER (WHERE status = 'never')::INTEGER as never_ranked_count,
        COUNT(*) FILTER (WHERE status = 'partial')::INTEGER as partial_count
    FROM watchlist_ranking_status;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION queue_ranking_job TO service_role;
GRANT EXECUTE ON FUNCTION queue_all_watchlist_ranking_jobs TO service_role;
GRANT EXECUTE ON FUNCTION queue_stale_ranking_jobs TO service_role;
GRANT EXECUTE ON FUNCTION get_ranking_health TO authenticated, service_role;

COMMENT ON FUNCTION queue_ranking_job IS 'Queue a ranking job for a specific symbol';
COMMENT ON FUNCTION queue_all_watchlist_ranking_jobs IS 'Queue ranking jobs for all watchlist symbols';
COMMENT ON FUNCTION queue_stale_ranking_jobs IS 'Queue ranking jobs for symbols with stale or missing rankings';
COMMENT ON VIEW watchlist_ranking_status IS 'Shows ranking health status for all watchlist symbols';
