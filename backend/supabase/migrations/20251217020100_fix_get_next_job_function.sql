-- Fix the get_next_ranking_job function to resolve ambiguous column reference

DROP FUNCTION IF EXISTS get_next_ranking_job();

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
    SELECT rj.id, rj.symbol, rj.created_at INTO job_record
    FROM ranking_jobs rj
    WHERE rj.status = 'pending'
      AND rj.retry_count < rj.max_retries
    ORDER BY rj.priority DESC, rj.created_at ASC
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
