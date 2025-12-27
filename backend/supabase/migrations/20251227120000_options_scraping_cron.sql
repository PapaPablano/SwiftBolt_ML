-- Migration: Options Scraping Automation
-- Sets up daily cron job to scrape options for all watchlist symbols
-- Also adds job tracking for options scraping

-- Create options_scrape_jobs table for tracking
CREATE TABLE IF NOT EXISTS options_scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    options_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_options_scrape_jobs_status
    ON options_scrape_jobs(status) WHERE status IN ('pending', 'running');
CREATE INDEX IF NOT EXISTS idx_options_scrape_jobs_created
    ON options_scrape_jobs(created_at DESC);

-- RLS
ALTER TABLE options_scrape_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Options scrape jobs readable by authenticated"
    ON options_scrape_jobs FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role manages options scrape jobs"
    ON options_scrape_jobs FOR ALL TO service_role USING (true);

-- Function: Queue options scrape for a symbol
CREATE OR REPLACE FUNCTION queue_options_scrape(p_symbol TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- Check if job already pending/running for this symbol today
    SELECT id INTO v_job_id
    FROM options_scrape_jobs
    WHERE symbol = p_symbol
      AND status IN ('pending', 'running')
      AND created_at > NOW() - INTERVAL '1 hour';

    IF v_job_id IS NOT NULL THEN
        RETURN v_job_id;  -- Return existing job
    END IF;

    -- Create new job
    INSERT INTO options_scrape_jobs (symbol, status)
    VALUES (p_symbol, 'pending')
    RETURNING id INTO v_job_id;

    RETURN v_job_id;
END;
$$;

-- Function: Queue options scrape for all watchlist symbols
CREATE OR REPLACE FUNCTION queue_all_watchlist_options_scrape()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
    v_count INTEGER := 0;
BEGIN
    FOR v_symbol IN
        SELECT DISTINCT s.ticker
        FROM watchlist_items wi
        JOIN symbols s ON s.id = wi.symbol_id
    LOOP
        PERFORM queue_options_scrape(v_symbol);
        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$;

-- Trigger: Auto-queue options scrape when symbol added to watchlist
CREATE OR REPLACE FUNCTION auto_queue_options_scrape()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
BEGIN
    SELECT ticker INTO v_symbol
    FROM symbols
    WHERE id = NEW.symbol_id;

    IF v_symbol IS NOT NULL THEN
        PERFORM queue_options_scrape(v_symbol);
    END IF;

    RETURN NEW;
END;
$$;

-- Add trigger to watchlist_items
DROP TRIGGER IF EXISTS trigger_watchlist_options_scrape ON watchlist_items;
CREATE TRIGGER trigger_watchlist_options_scrape
    AFTER INSERT ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION auto_queue_options_scrape();

-- Note: pg_cron scheduling should be set up via Supabase Dashboard
-- or GitHub Actions for more reliability
-- Dashboard: Database > Extensions > pg_cron > Schedule a job

-- The cron expression for daily at 4:30 PM ET (21:30 UTC) on weekdays:
-- '30 21 * * 1-5'
--
-- SQL to run:
-- SELECT queue_all_watchlist_options_scrape();

-- Function to trigger options scrape via edge function
CREATE OR REPLACE FUNCTION trigger_options_scrape_edge_function()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Queue jobs for all watchlist symbols
    PERFORM queue_all_watchlist_options_scrape();

    -- Note: The actual HTTP call to the edge function should be done
    -- via pg_net or an external scheduler (GitHub Actions, etc.)
    RAISE NOTICE 'Options scrape jobs queued for all watchlist symbols';
END;
$$;

-- View: Latest options scrape status per symbol
CREATE OR REPLACE VIEW latest_options_scrape_status AS
SELECT DISTINCT ON (symbol)
    symbol,
    status,
    options_count,
    created_at,
    completed_at,
    error_message
FROM options_scrape_jobs
ORDER BY symbol, created_at DESC;

GRANT SELECT ON latest_options_scrape_status TO authenticated;

-- Add comment
COMMENT ON TABLE options_scrape_jobs IS 'Tracks options scraping jobs from Tradier API';
COMMENT ON FUNCTION queue_options_scrape IS 'Queue an options scrape job for a symbol';
COMMENT ON FUNCTION queue_all_watchlist_options_scrape IS 'Queue options scrape for all watchlist symbols';
