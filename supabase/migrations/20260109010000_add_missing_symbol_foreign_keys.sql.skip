-- Migration: Add missing symbol_id foreign keys to tables using TEXT symbol columns
-- Problem: 11 tables store symbol as TEXT without referential integrity
-- Solution: Add symbol_id UUID columns with proper foreign key constraints

-- ============================================================================
-- STEP 1: Add symbol_id columns to tables missing them
-- ============================================================================

-- backfill_jobs
ALTER TABLE backfill_jobs 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- coverage_status
ALTER TABLE coverage_status 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- forecast_jobs
ALTER TABLE forecast_jobs 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- ga_optimization_runs
ALTER TABLE ga_optimization_runs 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- ga_strategy_params
ALTER TABLE ga_strategy_params 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- job_definitions
ALTER TABLE job_definitions 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- job_queue
ALTER TABLE job_queue 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- options_scrape_jobs
ALTER TABLE options_scrape_jobs 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- provider_checkpoints
ALTER TABLE provider_checkpoints 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- ranking_jobs
ALTER TABLE ranking_jobs 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- supertrend_signals
ALTER TABLE supertrend_signals 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- backfill_chunks (stores symbol TEXT from parent job)
ALTER TABLE backfill_chunks 
ADD COLUMN IF NOT EXISTS symbol_id UUID;

-- ============================================================================
-- STEP 2: Populate symbol_id columns by joining with symbols table
-- ============================================================================

-- backfill_jobs
UPDATE backfill_jobs bj
SET symbol_id = s.id
FROM symbols s
WHERE bj.symbol = s.ticker
  AND bj.symbol_id IS NULL;

-- coverage_status
UPDATE coverage_status cs
SET symbol_id = s.id
FROM symbols s
WHERE cs.symbol = s.ticker
  AND cs.symbol_id IS NULL;

-- forecast_jobs
UPDATE forecast_jobs fj
SET symbol_id = s.id
FROM symbols s
WHERE fj.symbol = s.ticker
  AND fj.symbol_id IS NULL;

-- ga_optimization_runs
UPDATE ga_optimization_runs gor
SET symbol_id = s.id
FROM symbols s
WHERE gor.symbol = s.ticker
  AND gor.symbol_id IS NULL;

-- ga_strategy_params
UPDATE ga_strategy_params gsp
SET symbol_id = s.id
FROM symbols s
WHERE gsp.symbol = s.ticker
  AND gsp.symbol_id IS NULL;

-- job_definitions
UPDATE job_definitions jd
SET symbol_id = s.id
FROM symbols s
WHERE jd.symbol = s.ticker
  AND jd.symbol_id IS NULL;

-- job_queue
UPDATE job_queue jq
SET symbol_id = s.id
FROM symbols s
WHERE jq.symbol = s.ticker
  AND jq.symbol_id IS NULL;

-- options_scrape_jobs
UPDATE options_scrape_jobs osj
SET symbol_id = s.id
FROM symbols s
WHERE osj.symbol = s.ticker
  AND osj.symbol_id IS NULL;

-- provider_checkpoints
UPDATE provider_checkpoints pc
SET symbol_id = s.id
FROM symbols s
WHERE pc.symbol = s.ticker
  AND pc.symbol_id IS NULL;

-- ranking_jobs
UPDATE ranking_jobs rj
SET symbol_id = s.id
FROM symbols s
WHERE rj.symbol = s.ticker
  AND rj.symbol_id IS NULL;

-- supertrend_signals
UPDATE supertrend_signals ss
SET symbol_id = s.id
FROM symbols s
WHERE ss.symbol = s.ticker
  AND ss.symbol_id IS NULL;

-- backfill_chunks
UPDATE backfill_chunks bc
SET symbol_id = s.id
FROM symbols s
WHERE bc.symbol = s.ticker
  AND bc.symbol_id IS NULL;

-- ============================================================================
-- STEP 3: Add foreign key constraints
-- ============================================================================

-- backfill_jobs
ALTER TABLE backfill_jobs
ADD CONSTRAINT backfill_jobs_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- coverage_status
ALTER TABLE coverage_status
ADD CONSTRAINT coverage_status_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- forecast_jobs
ALTER TABLE forecast_jobs
ADD CONSTRAINT forecast_jobs_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- ga_optimization_runs
ALTER TABLE ga_optimization_runs
ADD CONSTRAINT ga_optimization_runs_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- ga_strategy_params
ALTER TABLE ga_strategy_params
ADD CONSTRAINT ga_strategy_params_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- job_definitions
ALTER TABLE job_definitions
ADD CONSTRAINT job_definitions_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- job_queue
ALTER TABLE job_queue
ADD CONSTRAINT job_queue_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- options_scrape_jobs
ALTER TABLE options_scrape_jobs
ADD CONSTRAINT options_scrape_jobs_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- provider_checkpoints
ALTER TABLE provider_checkpoints
ADD CONSTRAINT provider_checkpoints_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- ranking_jobs
ALTER TABLE ranking_jobs
ADD CONSTRAINT ranking_jobs_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- supertrend_signals
ALTER TABLE supertrend_signals
ADD CONSTRAINT supertrend_signals_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- backfill_chunks
ALTER TABLE backfill_chunks
ADD CONSTRAINT backfill_chunks_symbol_id_fkey 
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 4: Create indexes for foreign key columns (performance optimization)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_backfill_jobs_symbol_id ON backfill_jobs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_coverage_status_symbol_id ON coverage_status(symbol_id);
CREATE INDEX IF NOT EXISTS idx_forecast_jobs_symbol_id ON forecast_jobs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_ga_optimization_runs_symbol_id ON ga_optimization_runs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_ga_strategy_params_symbol_id ON ga_strategy_params(symbol_id);
CREATE INDEX IF NOT EXISTS idx_job_definitions_symbol_id ON job_definitions(symbol_id);
CREATE INDEX IF NOT EXISTS idx_job_queue_symbol_id ON job_queue(symbol_id);
CREATE INDEX IF NOT EXISTS idx_options_scrape_jobs_symbol_id ON options_scrape_jobs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_provider_checkpoints_symbol_id ON provider_checkpoints(symbol_id);
CREATE INDEX IF NOT EXISTS idx_ranking_jobs_symbol_id ON ranking_jobs(symbol_id);
CREATE INDEX IF NOT EXISTS idx_supertrend_signals_symbol_id ON supertrend_signals(symbol_id);
CREATE INDEX IF NOT EXISTS idx_backfill_chunks_symbol_id ON backfill_chunks(symbol_id);

-- ============================================================================
-- STEP 5: Add NOT NULL constraints (after data is populated)
-- ============================================================================

-- Only add NOT NULL if the table requires it (some tables may have NULL symbols)
-- We'll be conservative and allow NULLs for now to avoid breaking existing data

-- ============================================================================
-- STEP 6: Create helper function to sync symbol_id when symbol TEXT changes
-- ============================================================================

CREATE OR REPLACE FUNCTION sync_symbol_id_from_ticker()
RETURNS TRIGGER AS $$
BEGIN
  -- If symbol TEXT column is updated, sync symbol_id
  IF NEW.symbol IS NOT NULL AND (OLD.symbol IS NULL OR NEW.symbol != OLD.symbol) THEN
    SELECT id INTO NEW.symbol_id
    FROM symbols
    WHERE ticker = NEW.symbol;
    
    -- If symbol not found, raise warning but allow insert/update
    IF NEW.symbol_id IS NULL THEN
      RAISE WARNING 'Symbol % not found in symbols table', NEW.symbol;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with both symbol TEXT and symbol_id UUID
CREATE TRIGGER sync_backfill_jobs_symbol_id
  BEFORE INSERT OR UPDATE ON backfill_jobs
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_coverage_status_symbol_id
  BEFORE INSERT OR UPDATE ON coverage_status
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_forecast_jobs_symbol_id
  BEFORE INSERT OR UPDATE ON forecast_jobs
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ga_optimization_runs_symbol_id
  BEFORE INSERT OR UPDATE ON ga_optimization_runs
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ga_strategy_params_symbol_id
  BEFORE INSERT OR UPDATE ON ga_strategy_params
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_job_definitions_symbol_id
  BEFORE INSERT OR UPDATE ON job_definitions
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_job_queue_symbol_id
  BEFORE INSERT OR UPDATE ON job_queue
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_options_scrape_jobs_symbol_id
  BEFORE INSERT OR UPDATE ON options_scrape_jobs
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_provider_checkpoints_symbol_id
  BEFORE INSERT OR UPDATE ON provider_checkpoints
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ranking_jobs_symbol_id
  BEFORE INSERT OR UPDATE ON ranking_jobs
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_supertrend_signals_symbol_id
  BEFORE INSERT OR UPDATE ON supertrend_signals
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

CREATE TRIGGER sync_backfill_chunks_symbol_id
  BEFORE INSERT OR UPDATE ON backfill_chunks
  FOR EACH ROW
  EXECUTE FUNCTION sync_symbol_id_from_ticker();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN backfill_jobs.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN coverage_status.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN forecast_jobs.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN ga_optimization_runs.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN ga_strategy_params.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN job_definitions.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN job_queue.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN options_scrape_jobs.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN provider_checkpoints.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN ranking_jobs.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN supertrend_signals.symbol_id IS 'Foreign key to symbols table for referential integrity';
COMMENT ON COLUMN backfill_chunks.symbol_id IS 'Foreign key to symbols table for referential integrity';

COMMENT ON FUNCTION sync_symbol_id_from_ticker() IS 
'Automatically syncs symbol_id UUID when symbol TEXT column is inserted/updated. 
Maintains backward compatibility while enforcing referential integrity.';

-- ============================================================================
-- VERIFICATION QUERIES (for testing)
-- ============================================================================

-- Run these queries after migration to verify:
-- 
-- 1. Check for NULL symbol_ids (should investigate these):
-- SELECT 'backfill_jobs' as table_name, COUNT(*) as null_count FROM backfill_jobs WHERE symbol_id IS NULL
-- UNION ALL
-- SELECT 'coverage_status', COUNT(*) FROM coverage_status WHERE symbol_id IS NULL
-- UNION ALL
-- SELECT 'forecast_jobs', COUNT(*) FROM forecast_jobs WHERE symbol_id IS NULL
-- ... (repeat for all tables)
--
-- 2. Verify foreign key constraints exist:
-- SELECT tc.table_name, tc.constraint_name, tc.constraint_type
-- FROM information_schema.table_constraints tc
-- WHERE tc.constraint_type = 'FOREIGN KEY'
--   AND tc.table_name IN ('backfill_jobs', 'coverage_status', 'forecast_jobs', 
--                         'ga_optimization_runs', 'ga_strategy_params', 'job_definitions',
--                         'job_queue', 'options_scrape_jobs', 'provider_checkpoints',
--                         'ranking_jobs', 'supertrend_signals', 'backfill_chunks')
-- ORDER BY tc.table_name;
--
-- 3. Test cascade delete (in dev environment only):
-- DELETE FROM symbols WHERE ticker = 'TEST_SYMBOL';
-- -- Should cascade delete all related records in the 12 tables
