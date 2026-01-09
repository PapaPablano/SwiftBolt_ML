-- Migration: Deprecate symbol TEXT columns in favor of symbol_id UUID
-- This is an OPTIONAL migration to complete the transition to UUID-based foreign keys
-- Run this ONLY after verifying all application code has been updated to use symbol_id

-- ============================================================================
-- PHASE 1: Make symbol_id NOT NULL (enforce referential integrity)
-- ============================================================================

-- Only uncomment these after confirming all rows have symbol_id populated
-- and all application code has been updated

-- ALTER TABLE backfill_jobs ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE coverage_status ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE forecast_jobs ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE ga_optimization_runs ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE ga_strategy_params ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE job_definitions ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE job_queue ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE options_scrape_jobs ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE provider_checkpoints ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE ranking_jobs ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE supertrend_signals ALTER COLUMN symbol_id SET NOT NULL;
-- ALTER TABLE backfill_chunks ALTER COLUMN symbol_id SET NOT NULL;

-- ============================================================================
-- PHASE 2: Create views for backward compatibility
-- ============================================================================

-- These views maintain the old interface while using the new symbol_id column
-- This allows gradual migration of application code

CREATE OR REPLACE VIEW backfill_jobs_v2 AS
SELECT 
    bj.*,
    s.ticker as symbol_ticker
FROM backfill_jobs bj
LEFT JOIN symbols s ON bj.symbol_id = s.id;

CREATE OR REPLACE VIEW coverage_status_v2 AS
SELECT 
    cs.*,
    s.ticker as symbol_ticker
FROM coverage_status cs
LEFT JOIN symbols s ON cs.symbol_id = s.id;

CREATE OR REPLACE VIEW forecast_jobs_v2 AS
SELECT 
    fj.*,
    s.ticker as symbol_ticker
FROM forecast_jobs fj
LEFT JOIN symbols s ON fj.symbol_id = s.id;

CREATE OR REPLACE VIEW ga_optimization_runs_v2 AS
SELECT 
    gor.*,
    s.ticker as symbol_ticker
FROM ga_optimization_runs gor
LEFT JOIN symbols s ON gor.symbol_id = s.id;

CREATE OR REPLACE VIEW ga_strategy_params_v2 AS
SELECT 
    gsp.*,
    s.ticker as symbol_ticker
FROM ga_strategy_params gsp
LEFT JOIN symbols s ON gsp.symbol_id = s.id;

CREATE OR REPLACE VIEW job_definitions_v2 AS
SELECT 
    jd.*,
    s.ticker as symbol_ticker
FROM job_definitions jd
LEFT JOIN symbols s ON jd.symbol_id = s.id;

CREATE OR REPLACE VIEW job_queue_v2 AS
SELECT 
    jq.*,
    s.ticker as symbol_ticker
FROM job_queue jq
LEFT JOIN symbols s ON jq.symbol_id = s.id;

CREATE OR REPLACE VIEW options_scrape_jobs_v2 AS
SELECT 
    osj.*,
    s.ticker as symbol_ticker
FROM options_scrape_jobs osj
LEFT JOIN symbols s ON osj.symbol_id = s.id;

CREATE OR REPLACE VIEW provider_checkpoints_v2 AS
SELECT 
    pc.*,
    s.ticker as symbol_ticker
FROM provider_checkpoints pc
LEFT JOIN symbols s ON pc.symbol_id = s.id;

CREATE OR REPLACE VIEW ranking_jobs_v2 AS
SELECT 
    rj.*,
    s.ticker as symbol_ticker
FROM ranking_jobs rj
LEFT JOIN symbols s ON rj.symbol_id = s.id;

CREATE OR REPLACE VIEW supertrend_signals_v2 AS
SELECT 
    ss.*,
    s.ticker as symbol_ticker
FROM supertrend_signals ss
LEFT JOIN symbols s ON ss.symbol_id = s.id;

CREATE OR REPLACE VIEW backfill_chunks_v2 AS
SELECT 
    bc.*,
    s.ticker as symbol_ticker
FROM backfill_chunks bc
LEFT JOIN symbols s ON bc.symbol_id = s.id;

-- ============================================================================
-- PHASE 3: Drop sync triggers (after application code is updated)
-- ============================================================================

-- Uncomment these after all application code uses symbol_id instead of symbol TEXT

-- DROP TRIGGER IF EXISTS sync_backfill_jobs_symbol_id ON backfill_jobs;
-- DROP TRIGGER IF EXISTS sync_coverage_status_symbol_id ON coverage_status;
-- DROP TRIGGER IF EXISTS sync_forecast_jobs_symbol_id ON forecast_jobs;
-- DROP TRIGGER IF EXISTS sync_ga_optimization_runs_symbol_id ON ga_optimization_runs;
-- DROP TRIGGER IF EXISTS sync_ga_strategy_params_symbol_id ON ga_strategy_params;
-- DROP TRIGGER IF EXISTS sync_job_definitions_symbol_id ON job_definitions;
-- DROP TRIGGER IF EXISTS sync_job_queue_symbol_id ON job_queue;
-- DROP TRIGGER IF EXISTS sync_options_scrape_jobs_symbol_id ON options_scrape_jobs;
-- DROP TRIGGER IF EXISTS sync_provider_checkpoints_symbol_id ON provider_checkpoints;
-- DROP TRIGGER IF EXISTS sync_ranking_jobs_symbol_id ON ranking_jobs;
-- DROP TRIGGER IF EXISTS sync_supertrend_signals_symbol_id ON supertrend_signals;
-- DROP TRIGGER IF EXISTS sync_backfill_chunks_symbol_id ON backfill_chunks;

-- DROP FUNCTION IF EXISTS sync_symbol_id_from_ticker();

-- ============================================================================
-- PHASE 4: Drop symbol TEXT columns (FINAL STEP - irreversible)
-- ============================================================================

-- ⚠️ WARNING: Only run this after ALL of the following are complete:
-- 1. All application code updated to use symbol_id
-- 2. All queries updated to use symbol_id
-- 3. All Edge Functions updated to use symbol_id
-- 4. Thorough testing in staging environment
-- 5. Backup of production database created

-- ALTER TABLE backfill_jobs DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE coverage_status DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE forecast_jobs DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE ga_optimization_runs DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE ga_strategy_params DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE job_definitions DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE job_queue DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE options_scrape_jobs DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE provider_checkpoints DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE ranking_jobs DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE supertrend_signals DROP COLUMN IF EXISTS symbol;
-- ALTER TABLE backfill_chunks DROP COLUMN IF EXISTS symbol;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON VIEW backfill_jobs_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW coverage_status_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW forecast_jobs_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW ga_optimization_runs_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW ga_strategy_params_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW job_definitions_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW job_queue_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW options_scrape_jobs_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW provider_checkpoints_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW ranking_jobs_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW supertrend_signals_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';
COMMENT ON VIEW backfill_chunks_v2 IS 'Backward-compatible view that includes symbol ticker from symbols table';

-- ============================================================================
-- MIGRATION CHECKLIST
-- ============================================================================

-- Before running PHASE 1 (NOT NULL constraints):
-- [ ] Verify all rows have symbol_id populated (run verification queries)
-- [ ] Update application code to populate symbol_id on INSERT
-- [ ] Test in staging environment

-- Before running PHASE 3 (Drop triggers):
-- [ ] Verify no application code writes to symbol TEXT column
-- [ ] Update all INSERT/UPDATE statements to use symbol_id
-- [ ] Test in staging environment

-- Before running PHASE 4 (Drop columns):
-- [ ] Verify no application code reads from symbol TEXT column
-- [ ] Update all SELECT statements to use symbol_id or views
-- [ ] Full regression testing in staging
-- [ ] Create production database backup
-- [ ] Schedule maintenance window
-- [ ] Have rollback plan ready

-- ============================================================================
-- ROLLBACK PLAN (if needed)
-- ============================================================================

-- If you need to rollback PHASE 1 (NOT NULL):
-- ALTER TABLE [table_name] ALTER COLUMN symbol_id DROP NOT NULL;

-- If you need to rollback PHASE 3 (triggers):
-- Re-run the trigger creation section from migration 20260109010000

-- If you need to rollback PHASE 4 (dropped columns):
-- This is NOT reversible - you must restore from backup
-- Always test in staging first!
