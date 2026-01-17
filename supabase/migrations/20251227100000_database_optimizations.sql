-- ============================================================================
-- Database Optimizations Migration
-- Migration: 20251227100000_database_optimizations.sql
-- ============================================================================
-- This migration implements production-grade database optimizations:
-- 1. Retention/archival policies with pg_cron scheduling
-- 2. Composite indexes for high-cardinality query patterns
-- 3. Enhanced RLS with SECURITY DEFINER worker functions
-- 4. Scheduled maintenance (VACUUM, ANALYZE)
-- 5. Partitioning strategy preparation for options_price_history
-- ============================================================================

-- ============================================================================
-- SECTION 1: Enable Required Extensions
-- ============================================================================

-- pg_cron for scheduled jobs (must be enabled in Supabase dashboard if not already)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- pg_stat_statements for query analysis (useful for identifying slow queries)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ============================================================================
-- SECTION 2: Enhanced Composite Indexes
-- ============================================================================

-- Job Queue: Ensure composite index covers all job types and processing order
CREATE INDEX IF NOT EXISTS idx_job_queue_type_status_priority
ON job_queue(job_type, status, priority ASC, created_at ASC)
WHERE status IN ('pending', 'processing');

-- Job Queue: Index for monitoring stale processing jobs
CREATE INDEX IF NOT EXISTS idx_job_queue_stale_check
ON job_queue(status, started_at)
WHERE status = 'processing';

-- Ranking Jobs: Compound index for status + priority + created ordering
-- Note: Already exists as idx_ranking_jobs_pending, adding symbol for faster lookups
CREATE INDEX IF NOT EXISTS idx_ranking_jobs_symbol_status
ON ranking_jobs(symbol, status);

-- Ranking Jobs: Index for stale job detection
CREATE INDEX IF NOT EXISTS idx_ranking_jobs_stale_check
ON ranking_jobs(status, started_at)
WHERE status = 'running';

-- Forecast Jobs: Composite index (if forecast_jobs table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'forecast_jobs') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_forecast_jobs_status_priority
                 ON forecast_jobs(status, priority ASC, created_at ASC)
                 WHERE status = ''pending''';

        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_forecast_jobs_stale_check
                 ON forecast_jobs(status, started_at)
                 WHERE status = ''running''';
    END IF;
END $$;

-- Options Price History: Add generated snapshot_date to avoid non-immutable expression in index
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'options_price_history' AND column_name = 'snapshot_date'
    ) THEN
        -- Use immutable expression (timezone is immutable; direct ::date cast on timestamptz is only stable)
        ALTER TABLE options_price_history
        ADD COLUMN snapshot_date DATE GENERATED ALWAYS AS (timezone('UTC', snapshot_at)::date) STORED;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_options_price_history_partition_key
ON options_price_history(snapshot_date, underlying_symbol_id);

-- Options Price History: Index for expiry-based queries (common pattern)
CREATE INDEX IF NOT EXISTS idx_options_price_history_expiry_analysis
ON options_price_history(expiry, underlying_symbol_id, side, snapshot_at DESC);

-- ML Forecasts: Index for evaluation queries
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'ml_forecasts' AND column_name = 'run_at') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_ml_forecasts_evaluation
                 ON ml_forecasts(symbol_id, horizon, run_at DESC)';
    END IF;
END $$;

-- ============================================================================
-- SECTION 3: Retention Policy Configuration
-- ============================================================================

-- Create retention_policies table to document and configure retention
CREATE TABLE IF NOT EXISTS retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL UNIQUE,
    retention_days INTEGER NOT NULL,
    archive_enabled BOOLEAN DEFAULT false,
    archive_table_name TEXT,
    last_cleanup_at TIMESTAMPTZ,
    rows_deleted_last_run INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert retention policies for key tables
INSERT INTO retention_policies (table_name, retention_days, archive_enabled, archive_table_name)
VALUES
    ('options_price_history', 90, false, NULL),
    ('ranking_jobs', 7, false, NULL),
    ('forecast_jobs', 7, false, NULL),
    ('job_queue', 7, false, NULL),
    ('forecast_evaluations', 365, true, 'forecast_evaluations_archive'),
    ('scanner_alerts', 30, false, NULL),
    ('news_items', 90, false, NULL)
ON CONFLICT (table_name) DO UPDATE
SET retention_days = EXCLUDED.retention_days,
    updated_at = NOW();

-- Enable RLS on retention_policies
ALTER TABLE retention_policies ENABLE ROW LEVEL SECURITY;

-- Only service_role can modify retention policies
CREATE POLICY "retention_policies_service_role_all" ON retention_policies
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "retention_policies_authenticated_read" ON retention_policies
    FOR SELECT USING (true);

-- ============================================================================
-- SECTION 4: Enhanced Cleanup Functions
-- ============================================================================

-- Master cleanup function that respects retention policies
CREATE OR REPLACE FUNCTION run_retention_cleanup()
RETURNS TABLE (
    table_name TEXT,
    rows_deleted INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_policy RECORD;
    v_deleted INTEGER;
    v_sql TEXT;
BEGIN
    FOR v_policy IN SELECT * FROM retention_policies WHERE retention_days > 0 LOOP
        v_deleted := 0;

        -- Handle each table with its specific timestamp column
        CASE v_policy.table_name
            WHEN 'options_price_history' THEN
                DELETE FROM options_price_history
                WHERE snapshot_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                GET DIAGNOSTICS v_deleted = ROW_COUNT;

            WHEN 'ranking_jobs' THEN
                DELETE FROM ranking_jobs
                WHERE status IN ('completed', 'failed')
                AND completed_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                GET DIAGNOSTICS v_deleted = ROW_COUNT;

            WHEN 'job_queue' THEN
                DELETE FROM job_queue
                WHERE status IN ('completed', 'failed')
                AND completed_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                GET DIAGNOSTICS v_deleted = ROW_COUNT;

            WHEN 'forecast_jobs' THEN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'forecast_jobs') THEN
                    DELETE FROM forecast_jobs
                    WHERE status IN ('completed', 'failed')
                    AND completed_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                    GET DIAGNOSTICS v_deleted = ROW_COUNT;
                END IF;

            WHEN 'scanner_alerts' THEN
                DELETE FROM scanner_alerts
                WHERE (expires_at IS NOT NULL AND expires_at < NOW())
                OR created_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                GET DIAGNOSTICS v_deleted = ROW_COUNT;

            WHEN 'news_items' THEN
                DELETE FROM news_items
                WHERE fetched_at < NOW() - (v_policy.retention_days || ' days')::INTERVAL;
                GET DIAGNOSTICS v_deleted = ROW_COUNT;

            ELSE
                -- Skip unknown tables
                CONTINUE;
        END CASE;

        -- Update retention policy stats
        UPDATE retention_policies
        SET last_cleanup_at = NOW(),
            rows_deleted_last_run = v_deleted,
            updated_at = NOW()
        WHERE retention_policies.table_name = v_policy.table_name;

        -- Return results
        table_name := v_policy.table_name;
        rows_deleted := v_deleted;
        RETURN NEXT;
    END LOOP;
END;
$$;

-- Function to detect and reset stale jobs (stuck in processing/running)
CREATE OR REPLACE FUNCTION reset_stale_jobs(p_stale_minutes INTEGER DEFAULT 30)
RETURNS TABLE (
    queue_name TEXT,
    jobs_reset INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_reset INTEGER;
BEGIN
    -- Reset stale job_queue entries
    UPDATE job_queue
    SET status = 'pending',
        started_at = NULL,
        attempts = attempts  -- Don't increment on stale reset
    WHERE status = 'processing'
    AND started_at < NOW() - (p_stale_minutes || ' minutes')::INTERVAL;
    GET DIAGNOSTICS v_reset = ROW_COUNT;

    queue_name := 'job_queue';
    jobs_reset := v_reset;
    RETURN NEXT;

    -- Reset stale ranking_jobs
    UPDATE ranking_jobs
    SET status = 'pending',
        started_at = NULL
    WHERE status = 'running'
    AND started_at < NOW() - (p_stale_minutes || ' minutes')::INTERVAL
    AND retry_count < max_retries;
    GET DIAGNOSTICS v_reset = ROW_COUNT;

    queue_name := 'ranking_jobs';
    jobs_reset := v_reset;
    RETURN NEXT;

    -- Reset stale forecast_jobs if exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'forecast_jobs') THEN
        UPDATE forecast_jobs
        SET status = 'pending',
            started_at = NULL
        WHERE status = 'running'
        AND started_at < NOW() - (p_stale_minutes || ' minutes')::INTERVAL
        AND retry_count < max_retries;
        GET DIAGNOSTICS v_reset = ROW_COUNT;

        queue_name := 'forecast_jobs';
        jobs_reset := v_reset;
        RETURN NEXT;
    END IF;
END;
$$;

-- ============================================================================
-- SECTION 5: SECURITY DEFINER Worker Functions
-- ============================================================================

-- Wrapper for workers to claim jobs without needing service_role access
CREATE OR REPLACE FUNCTION worker_claim_job(p_job_type TEXT DEFAULT NULL)
RETURNS TABLE (
    job_id UUID,
    job_type TEXT,
    symbol TEXT,
    payload JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Delegate to existing claim_next_job function
    RETURN QUERY SELECT * FROM claim_next_job(p_job_type);
END;
$$;

-- Wrapper for workers to complete jobs
CREATE OR REPLACE FUNCTION worker_complete_job(p_job_id UUID, p_success BOOLEAN, p_error TEXT DEFAULT NULL)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM complete_job(p_job_id, p_success, p_error);
END;
$$;

-- Wrapper for workers to get ranking jobs
CREATE OR REPLACE FUNCTION worker_get_ranking_job()
RETURNS TABLE (
    job_id UUID,
    symbol TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY SELECT * FROM get_next_ranking_job();
END;
$$;

-- Wrapper for workers to complete ranking jobs
CREATE OR REPLACE FUNCTION worker_complete_ranking_job(p_job_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM complete_ranking_job(p_job_id);
END;
$$;

-- Wrapper for workers to fail ranking jobs
CREATE OR REPLACE FUNCTION worker_fail_ranking_job(p_job_id UUID, p_error_msg TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM fail_ranking_job(p_job_id, p_error_msg);
END;
$$;

-- Grant execute permissions to authenticated users (workers)
GRANT EXECUTE ON FUNCTION worker_claim_job TO authenticated;
GRANT EXECUTE ON FUNCTION worker_complete_job TO authenticated;
GRANT EXECUTE ON FUNCTION worker_get_ranking_job TO authenticated;
GRANT EXECUTE ON FUNCTION worker_complete_ranking_job TO authenticated;
GRANT EXECUTE ON FUNCTION worker_fail_ranking_job TO authenticated;

-- ============================================================================
-- SECTION 6: pg_cron Scheduled Maintenance Jobs
-- ============================================================================

-- Note: pg_cron jobs must be created by a superuser or the cron schema owner
-- These commands may need to be run via Supabase dashboard SQL editor if migration fails

DO $$
BEGIN
    -- Only create cron jobs if pg_cron extension is available
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN

        -- Schedule retention cleanup - runs daily at 3 AM UTC
        PERFORM cron.schedule(
            'retention-cleanup',
            '0 3 * * *',
            'SELECT * FROM run_retention_cleanup()'
        );

        -- Schedule stale job reset - runs every 15 minutes
        PERFORM cron.schedule(
            'stale-job-reset',
            '*/15 * * * *',
            'SELECT * FROM reset_stale_jobs(30)'
        );

        -- Schedule VACUUM ANALYZE on high-churn tables - runs daily at 4 AM UTC
        PERFORM cron.schedule(
            'vacuum-analyze-daily',
            '0 4 * * *',
            'VACUUM ANALYZE options_price_history, job_queue, ranking_jobs, ml_forecasts'
        );

        -- Schedule full VACUUM on weekends - runs Sundays at 5 AM UTC
        PERFORM cron.schedule(
            'vacuum-full-weekly',
            '0 5 * * 0',
            'VACUUM (VERBOSE, ANALYZE) options_price_history'
        );

        RAISE NOTICE 'pg_cron jobs scheduled successfully';
    ELSE
        RAISE NOTICE 'pg_cron extension not available - skipping cron job setup';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Could not schedule pg_cron jobs: %. You may need to run these via Supabase dashboard.', SQLERRM;
END $$;

-- ============================================================================
-- SECTION 7: Partitioning Strategy Documentation
-- ============================================================================

-- FUTURE PARTITIONING STRATEGY FOR options_price_history
-- When table exceeds 5-10M rows, implement range partitioning:
--
-- Step 1: Create partitioned table
-- CREATE TABLE options_price_history_partitioned (
--     LIKE options_price_history INCLUDING ALL
-- ) PARTITION BY RANGE (snapshot_at);
--
-- Step 2: Create monthly partitions
-- CREATE TABLE options_price_history_y2025m01
--     PARTITION OF options_price_history_partitioned
--     FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ... (repeat for each month)
--
-- Step 3: Migrate data in batches
-- INSERT INTO options_price_history_partitioned SELECT * FROM options_price_history;
--
-- Step 4: Swap tables
-- ALTER TABLE options_price_history RENAME TO options_price_history_old;
-- ALTER TABLE options_price_history_partitioned RENAME TO options_price_history;
--
-- Step 5: Create auto-partition function to create new monthly partitions

-- Create function to generate partition DDL (for future use)
CREATE OR REPLACE FUNCTION generate_partition_ddl(
    p_table_name TEXT,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_ddl TEXT := '';
    v_current DATE := p_start_date;
    v_next DATE;
    v_partition_name TEXT;
BEGIN
    WHILE v_current < p_end_date LOOP
        v_next := v_current + INTERVAL '1 month';
        v_partition_name := p_table_name || '_y' || to_char(v_current, 'YYYY') || 'm' || to_char(v_current, 'MM');

        v_ddl := v_ddl || format(
            E'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I_partitioned\n    FOR VALUES FROM (%L) TO (%L);\n\n',
            v_partition_name,
            p_table_name,
            v_current,
            v_next
        );

        v_current := v_next;
    END LOOP;

    RETURN v_ddl;
END;
$$;

-- ============================================================================
-- SECTION 8: Monitoring Views
-- ============================================================================

-- View for table sizes and row counts (useful for monitoring growth)
CREATE OR REPLACE VIEW v_table_stats AS
SELECT
    schemaname,
    relname as table_name,
    n_live_tup as estimated_row_count,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as table_size,
    pg_size_pretty(pg_indexes_size(relid)) as index_size,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC;

-- View for job queue health monitoring
CREATE OR REPLACE VIEW v_job_queue_health AS
SELECT
    'job_queue' as queue_name,
    status,
    COUNT(*) as job_count,
    MIN(created_at) as oldest_job,
    MAX(created_at) as newest_job,
    AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, NOW()) - created_at))) as avg_duration_seconds
FROM job_queue
GROUP BY status
UNION ALL
SELECT
    'ranking_jobs' as queue_name,
    status::TEXT,
    COUNT(*) as job_count,
    MIN(created_at) as oldest_job,
    MAX(created_at) as newest_job,
    AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, NOW()) - created_at))) as avg_duration_seconds
FROM ranking_jobs
GROUP BY status;

-- Grant read access to monitoring views
GRANT SELECT ON v_table_stats TO authenticated;
GRANT SELECT ON v_job_queue_health TO authenticated;

-- ============================================================================
-- SECTION 9: Extension Cleanup Notes
-- ============================================================================

-- Document required vs optional extensions
COMMENT ON EXTENSION pg_cron IS 'Required for scheduled maintenance jobs';
COMMENT ON EXTENSION pg_stat_statements IS 'Optional - useful for query performance analysis';

-- List of extensions that should be reviewed in production:
-- REQUIRED:
--   - uuid-ossp (for gen_random_uuid)
--   - pgcrypto (for cryptographic functions)
--   - pg_cron (for scheduled jobs - this migration)
--
-- OPTIONAL (can be removed if not used):
--   - pg_stat_statements (query analysis)
--   - postgis (geospatial - only if using location data)
--   - pg_trgm (text search - only if using fuzzy search)
--
-- To list all enabled extensions:
-- SELECT * FROM pg_extension ORDER BY extname;
--
-- To remove unused extension:
-- DROP EXTENSION IF EXISTS <extension_name>;

-- ============================================================================
-- SECTION 10: Manual pg_cron Setup Commands
-- ============================================================================

-- If pg_cron setup failed in Section 6, run these commands manually via Supabase SQL Editor:
--
-- SELECT cron.schedule('retention-cleanup', '0 3 * * *', 'SELECT * FROM run_retention_cleanup()');
-- SELECT cron.schedule('stale-job-reset', '*/15 * * * *', 'SELECT * FROM reset_stale_jobs(30)');
-- SELECT cron.schedule('vacuum-analyze-daily', '0 4 * * *', 'VACUUM ANALYZE options_price_history, job_queue, ranking_jobs, ml_forecasts');
-- SELECT cron.schedule('vacuum-full-weekly', '0 5 * * 0', 'VACUUM (VERBOSE, ANALYZE) options_price_history');
--
-- To view scheduled jobs:
-- SELECT * FROM cron.job;
--
-- To view job run history:
-- SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;
--
-- To unschedule a job:
-- SELECT cron.unschedule('job-name');

COMMENT ON FUNCTION run_retention_cleanup IS 'Master cleanup function that enforces retention policies across all configured tables';
COMMENT ON FUNCTION reset_stale_jobs IS 'Resets jobs stuck in processing/running state beyond the stale threshold';
COMMENT ON TABLE retention_policies IS 'Configuration table for data retention policies';
