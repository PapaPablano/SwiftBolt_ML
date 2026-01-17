-- Migration: Trigger options backfill when symbol added to watchlist
-- This ensures new watchlist symbols get immediate options data capture

-- Create a job queue table for options backfill if not exists
CREATE TABLE IF NOT EXISTS options_backfill_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for pending jobs
CREATE INDEX IF NOT EXISTS idx_options_backfill_pending 
ON options_backfill_jobs(status, created_at) 
WHERE status = 'pending';

-- Enable RLS
ALTER TABLE options_backfill_jobs ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "options_backfill_service_all" ON options_backfill_jobs
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- Function to queue options backfill when symbol added to watchlist
CREATE OR REPLACE FUNCTION queue_options_backfill_on_watchlist_add()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_ticker TEXT;
    v_existing_job UUID;
BEGIN
    -- Get the ticker for this symbol
    SELECT ticker INTO v_ticker
    FROM symbols
    WHERE id = NEW.symbol_id;
    
    IF v_ticker IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Check if there's already a pending job for this symbol
    SELECT id INTO v_existing_job
    FROM options_backfill_jobs
    WHERE symbol_id = NEW.symbol_id
      AND status = 'pending';
    
    -- Only queue if no pending job exists
    IF v_existing_job IS NULL THEN
        INSERT INTO options_backfill_jobs (symbol_id, ticker, status)
        VALUES (NEW.symbol_id, v_ticker, 'pending');
        
        RAISE NOTICE 'Queued options backfill for %', v_ticker;
    END IF;
    
    RETURN NEW;
END;
$$;

-- Trigger: Queue backfill when symbol added to watchlist
DROP TRIGGER IF EXISTS trigger_options_backfill_on_watchlist_add ON watchlist_items;
CREATE TRIGGER trigger_options_backfill_on_watchlist_add
    AFTER INSERT ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION queue_options_backfill_on_watchlist_add();

COMMENT ON FUNCTION queue_options_backfill_on_watchlist_add IS 
'Automatically queues options backfill job when a symbol is added to any watchlist';

-- Function to get next pending backfill job (for worker)
CREATE OR REPLACE FUNCTION get_next_options_backfill_job()
RETURNS TABLE (
    job_id UUID,
    symbol_id UUID,
    ticker TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    UPDATE options_backfill_jobs
    SET status = 'processing',
        started_at = NOW()
    WHERE id = (
        SELECT id
        FROM options_backfill_jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING 
        options_backfill_jobs.id as job_id,
        options_backfill_jobs.symbol_id,
        options_backfill_jobs.ticker;
END;
$$;

-- Function to complete a backfill job
CREATE OR REPLACE FUNCTION complete_options_backfill_job(p_job_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE options_backfill_jobs
    SET status = 'completed',
        completed_at = NOW()
    WHERE id = p_job_id;
END;
$$;

-- Function to fail a backfill job
CREATE OR REPLACE FUNCTION fail_options_backfill_job(p_job_id UUID, p_error TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE options_backfill_jobs
    SET status = 'failed',
        error_message = p_error,
        completed_at = NOW()
    WHERE id = p_job_id;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_next_options_backfill_job TO service_role;
GRANT EXECUTE ON FUNCTION complete_options_backfill_job TO service_role;
GRANT EXECUTE ON FUNCTION fail_options_backfill_job TO service_role;

COMMENT ON TABLE options_backfill_jobs IS 
'Queue for options backfill jobs triggered by watchlist additions';
