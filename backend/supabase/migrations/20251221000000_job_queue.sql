-- Job queue for async processing of ML forecasts and other background tasks
CREATE TABLE IF NOT EXISTS job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,  -- 'forecast', 'backfill', 'ranking'
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    priority INTEGER NOT NULL DEFAULT 5,  -- 1 = highest, 10 = lowest
    payload JSONB DEFAULT '{}',
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Index for efficient job polling
CREATE INDEX IF NOT EXISTS idx_job_queue_pending ON job_queue(status, priority, created_at) 
WHERE status = 'pending';

-- Index for symbol lookups
CREATE INDEX IF NOT EXISTS idx_job_queue_symbol ON job_queue(symbol, job_type);

-- Function to get next pending job and mark it as processing
CREATE OR REPLACE FUNCTION claim_next_job(p_job_type TEXT DEFAULT NULL)
RETURNS TABLE (
    job_id UUID,
    job_type TEXT,
    symbol TEXT,
    payload JSONB
) AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- Select and lock the next pending job
    SELECT j.id INTO v_job_id
    FROM job_queue j
    WHERE j.status = 'pending'
      AND (p_job_type IS NULL OR j.job_type = p_job_type)
      AND j.attempts < j.max_attempts
    ORDER BY j.priority ASC, j.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF v_job_id IS NULL THEN
        RETURN;
    END IF;
    
    -- Mark as processing
    UPDATE job_queue
    SET status = 'processing',
        started_at = NOW(),
        attempts = attempts + 1
    WHERE id = v_job_id;
    
    -- Return the job details
    RETURN QUERY
    SELECT j.id, j.job_type, j.symbol, j.payload
    FROM job_queue j
    WHERE j.id = v_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to mark job as completed
CREATE OR REPLACE FUNCTION complete_job(p_job_id UUID, p_success BOOLEAN, p_error TEXT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
    UPDATE job_queue
    SET status = CASE WHEN p_success THEN 'completed' ELSE 'failed' END,
        completed_at = NOW(),
        error_message = p_error
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON job_queue TO authenticated;
GRANT ALL ON job_queue TO service_role;
