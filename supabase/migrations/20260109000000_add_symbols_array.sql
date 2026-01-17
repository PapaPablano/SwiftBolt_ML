-- Add symbols_array column for batch job support (Phase 2)
-- Allows storing multiple symbols per job for efficient Alpaca multi-symbol API calls

ALTER TABLE job_definitions 
ADD COLUMN IF NOT EXISTS symbols_array jsonb;

-- Index for efficient querying of batch jobs
CREATE INDEX IF NOT EXISTS idx_job_definitions_symbols_array 
ON job_definitions USING gin(symbols_array);

-- Add batch tracking columns
ALTER TABLE job_definitions
ADD COLUMN IF NOT EXISTS batch_number integer,
ADD COLUMN IF NOT EXISTS total_batches integer;

COMMENT ON COLUMN job_definitions.symbols_array IS 'Array of symbols for batch jobs (Phase 2). Legacy jobs use single symbol field.';
COMMENT ON COLUMN job_definitions.batch_number IS 'Batch number in sequence (e.g., 1 of 100)';
COMMENT ON COLUMN job_definitions.total_batches IS 'Total number of batches in this backfill run';
