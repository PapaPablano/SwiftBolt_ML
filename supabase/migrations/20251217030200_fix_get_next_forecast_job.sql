-- Fix ambiguous column reference in get_next_forecast_job function

CREATE OR REPLACE FUNCTION get_next_forecast_job()
RETURNS TABLE (
    job_id UUID,
    symbol TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_job_id UUID;
    v_symbol TEXT;
BEGIN
    -- Get highest priority pending job and mark as running
    UPDATE forecast_jobs
    SET
        status = 'running',
        started_at = NOW()
    WHERE id = (
        SELECT id
        FROM forecast_jobs
        WHERE status = 'pending'
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, forecast_jobs.symbol INTO v_job_id, v_symbol;

    RETURN QUERY SELECT v_job_id, v_symbol;
END;
$$;
