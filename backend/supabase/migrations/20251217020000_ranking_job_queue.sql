-- ============================================================================
-- Ranking Job Queue Table
-- Migration: 20251217020000_ranking_job_queue.sql
-- ============================================================================
-- This table implements a simple job queue for options ranking jobs.
-- Jobs are inserted by the trigger-ranking-job Edge Function and
-- processed by a worker (Python script or external service).

-- Job status enum
CREATE TYPE job_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- ranking_jobs table
CREATE TABLE ranking_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    status job_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,

    -- Metadata
    requested_by TEXT, -- Optional: track who requested the job
    priority INTEGER NOT NULL DEFAULT 0 -- Higher priority = processed first
);

-- Indexes for efficient job queue queries
CREATE INDEX idx_ranking_jobs_status ON ranking_jobs(status);
CREATE INDEX idx_ranking_jobs_created ON ranking_jobs(created_at DESC);
CREATE INDEX idx_ranking_jobs_pending ON ranking_jobs(status, priority DESC, created_at ASC)
    WHERE status = 'pending';

-- Function to get next pending job (for workers)
CREATE OR REPLACE FUNCTION get_next_ranking_job()
RETURNS TABLE (
    job_id UUID,
    symbol TEXT,
    created_at TIMESTAMPTZ
) AS $$
DECLARE
    job_record RECORD;
BEGIN
    -- Get the highest priority pending job
    SELECT id, symbol, created_at INTO job_record
    FROM ranking_jobs
    WHERE status = 'pending'
      AND retry_count < max_retries
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED; -- Lock the job so other workers don't pick it up

    IF job_record.id IS NOT NULL THEN
        -- Update job to 'running'
        UPDATE ranking_jobs
        SET status = 'running',
            started_at = NOW()
        WHERE id = job_record.id;

        -- Return the job details
        RETURN QUERY SELECT job_record.id, job_record.symbol, job_record.created_at;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to mark job as completed
CREATE OR REPLACE FUNCTION complete_ranking_job(job_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE ranking_jobs
    SET status = 'completed',
        completed_at = NOW()
    WHERE id = job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to mark job as failed
CREATE OR REPLACE FUNCTION fail_ranking_job(job_id UUID, error_msg TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE ranking_jobs
    SET status = 'failed',
        completed_at = NOW(),
        error_message = error_msg,
        retry_count = retry_count + 1
    WHERE id = job_id;

    -- If retries remain, reset to pending after 1 minute
    UPDATE ranking_jobs
    SET status = 'pending',
        started_at = NULL,
        completed_at = NULL
    WHERE id = job_id
      AND retry_count < max_retries;
END;
$$ LANGUAGE plpgsql;

-- Auto-cleanup: Delete completed/failed jobs older than 7 days
-- (Optional: You can set up pg_cron to run this periodically)
CREATE OR REPLACE FUNCTION cleanup_old_ranking_jobs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM ranking_jobs
    WHERE status IN ('completed', 'failed')
      AND completed_at < NOW() - INTERVAL '7 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
