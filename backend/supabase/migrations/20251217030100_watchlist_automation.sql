-- Migration: Watchlist Job Automation
-- Auto-triggers ML forecast and options ranking jobs when symbols are added to watchlists
-- Adds job status tracking for user visibility

-- Create forecast_jobs table (similar to ranking_jobs)
CREATE TABLE IF NOT EXISTS forecast_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    priority INTEGER NOT NULL DEFAULT 5,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_forecast_jobs_status ON forecast_jobs(status) WHERE status IN ('pending', 'running');
CREATE INDEX idx_forecast_jobs_symbol ON forecast_jobs(symbol);
CREATE INDEX idx_forecast_jobs_created ON forecast_jobs(created_at);

-- Enable RLS
ALTER TABLE forecast_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Authenticated users can view jobs
CREATE POLICY "Forecast jobs are readable by authenticated users"
    ON forecast_jobs
    FOR SELECT
    TO authenticated
    USING (true);

-- RLS Policy: Service role can manage jobs
CREATE POLICY "Service role can manage forecast jobs"
    ON forecast_jobs
    FOR ALL
    USING (auth.role() = 'service_role');

-- Function: Get next forecast job (atomic)
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

-- Function: Complete forecast job
CREATE OR REPLACE FUNCTION complete_forecast_job(p_job_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE forecast_jobs
    SET
        status = 'completed',
        completed_at = NOW()
    WHERE id = p_job_id;
END;
$$;

-- Function: Fail forecast job (with retry logic)
CREATE OR REPLACE FUNCTION fail_forecast_job(p_job_id UUID, p_error_message TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_retry_count INTEGER;
    v_max_retries INTEGER;
BEGIN
    SELECT retry_count, max_retries
    INTO v_retry_count, v_max_retries
    FROM forecast_jobs
    WHERE id = p_job_id;

    IF v_retry_count < v_max_retries THEN
        -- Retry: reset to pending and increment retry count
        UPDATE forecast_jobs
        SET
            status = 'pending',
            retry_count = retry_count + 1,
            error_message = p_error_message,
            started_at = NULL
        WHERE id = p_job_id;
    ELSE
        -- Max retries reached: mark as failed
        UPDATE forecast_jobs
        SET
            status = 'failed',
            error_message = p_error_message,
            completed_at = NOW()
        WHERE id = p_job_id;
    END IF;
END;
$$;

-- Function: Cleanup old forecast jobs
CREATE OR REPLACE FUNCTION cleanup_old_forecast_jobs()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_deleted INTEGER;
BEGIN
    DELETE FROM forecast_jobs
    WHERE created_at < NOW() - INTERVAL '7 days'
    AND status IN ('completed', 'failed');

    GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;

    RETURN v_rows_deleted;
END;
$$;

-- Function: Auto-trigger jobs when symbol added to watchlist
CREATE OR REPLACE FUNCTION auto_trigger_symbol_jobs()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_symbol TEXT;
BEGIN
    -- Get symbol ticker from symbols table
    SELECT ticker INTO v_symbol
    FROM symbols
    WHERE id = NEW.symbol_id;

    IF v_symbol IS NOT NULL THEN
        -- Create forecast job (idempotent - check if not already queued)
        INSERT INTO forecast_jobs (symbol, priority)
        SELECT v_symbol, 7
        WHERE NOT EXISTS (
            SELECT 1 FROM forecast_jobs
            WHERE symbol = v_symbol
            AND status IN ('pending', 'running')
        );

        -- Create ranking job (idempotent)
        INSERT INTO ranking_jobs (symbol, priority)
        SELECT v_symbol, 7
        WHERE NOT EXISTS (
            SELECT 1 FROM ranking_jobs
            WHERE symbol = v_symbol
            AND status IN ('pending', 'running')
        );
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger: Auto-create jobs when watchlist item added
CREATE TRIGGER trigger_watchlist_item_jobs
    AFTER INSERT ON watchlist_items
    FOR EACH ROW
    EXECUTE FUNCTION auto_trigger_symbol_jobs();

-- Function: Get job status for symbol
CREATE OR REPLACE FUNCTION get_symbol_job_status(p_symbol TEXT)
RETURNS TABLE (
    job_type TEXT,
    status TEXT,
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    (
        -- Get latest forecast job
        SELECT
            'forecast'::TEXT as job_type,
            fj.status,
            fj.created_at,
            fj.completed_at,
            fj.error_message
        FROM forecast_jobs fj
        WHERE fj.symbol = p_symbol
        ORDER BY fj.created_at DESC
        LIMIT 1
    )
    UNION ALL
    (
        -- Get latest ranking job
        SELECT
            'ranking'::TEXT as job_type,
            rj.status,
            rj.created_at,
            rj.completed_at,
            rj.error_message
        FROM ranking_jobs rj
        WHERE rj.symbol = p_symbol
        ORDER BY rj.created_at DESC
        LIMIT 1
    );
END;
$$;

-- View: Combined job status for all symbols
CREATE OR REPLACE VIEW symbol_job_status AS
WITH forecast_status AS (
    SELECT DISTINCT ON (s.ticker)
        s.id as symbol_id,
        s.ticker as symbol,
        'forecast'::TEXT as job_type,
        fj.status::TEXT as status,
        fj.created_at,
        fj.completed_at,
        fj.error_message
    FROM symbols s
    LEFT JOIN forecast_jobs fj ON fj.symbol = s.ticker
    ORDER BY s.ticker, fj.created_at DESC
),
ranking_status AS (
    SELECT DISTINCT ON (s.ticker)
        s.id as symbol_id,
        s.ticker as symbol,
        'ranking'::TEXT as job_type,
        rj.status::TEXT as status,
        rj.created_at,
        rj.completed_at,
        rj.error_message
    FROM symbols s
    LEFT JOIN ranking_jobs rj ON rj.symbol = s.ticker
    ORDER BY s.ticker, rj.created_at DESC
)
SELECT * FROM forecast_status
UNION ALL
SELECT * FROM ranking_status;

-- Grant access
GRANT SELECT ON symbol_job_status TO authenticated;

COMMENT ON TABLE forecast_jobs IS 'Queue for ML forecast generation jobs';
COMMENT ON FUNCTION auto_trigger_symbol_jobs IS 'Automatically creates forecast and ranking jobs when symbol added to watchlist';
COMMENT ON FUNCTION get_symbol_job_status IS 'Returns latest job status for a given symbol';
COMMENT ON VIEW symbol_job_status IS 'Combined view of forecast and ranking job statuses for all symbols';
