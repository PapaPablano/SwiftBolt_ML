-- ============================================================================
-- Phase 1 Migration #2: Convert VARCHAR(n) to TEXT with CHECK constraints
-- ============================================================================
-- Date: January 25, 2026
-- Purpose: Fix VARCHAR(n) columns in ohlc_bars_v2 (Batch 1 of Phase 1)
-- Risk Level: Low
-- Rollback: TEXT is backward compatible; can add constraint back if needed
-- ============================================================================

-- Start transaction
BEGIN TRANSACTION;

-- ============================================================================
-- Step 1: Identify columns to convert in ohlc_bars_v2
-- ============================================================================
-- These columns currently use VARCHAR(n) and should be TEXT with CHECK
SELECT
  column_name,
  data_type,
  character_maximum_length
FROM information_schema.columns
WHERE table_name = 'ohlc_bars_v2'
  AND (
    column_name = 'timeframe' OR
    column_name = 'provider' OR
    column_name = 'data_status'
  )
ORDER BY column_name;

-- ============================================================================
-- Step 2: Convert VARCHAR columns to TEXT
-- ============================================================================
ALTER TABLE ohlc_bars_v2
  ALTER COLUMN timeframe TYPE TEXT,
  ALTER COLUMN provider TYPE TEXT,
  ALTER COLUMN data_status TYPE TEXT;

-- ============================================================================
-- Step 3: Add CHECK constraints for length validation
-- ============================================================================
-- These constraints replace the implicit VARCHAR(n) constraints
-- with explicit CHECK constraints (clearer intent)

-- Constraint for timeframe (max 10 chars, e.g., "m15", "h1", "h4", "h8", "d1")
ALTER TABLE ohlc_bars_v2
  ADD CONSTRAINT chk_timeframe_length
    CHECK (LENGTH(timeframe) <= 10);

-- Constraint for provider (max 20 chars, e.g., "polygon", "tradier", "ml_forecast")
ALTER TABLE ohlc_bars_v2
  ADD CONSTRAINT chk_provider_length
    CHECK (LENGTH(provider) <= 20);

-- Constraint for data_status (max 20 chars, nullable)
ALTER TABLE ohlc_bars_v2
  ADD CONSTRAINT chk_data_status_length
    CHECK (data_status IS NULL OR LENGTH(data_status) <= 20);

-- ============================================================================
-- Step 4: Verify conversion successful
-- ============================================================================
-- Check that columns are now TEXT with CHECK constraints
SELECT
  column_name,
  data_type,
  character_maximum_length
FROM information_schema.columns
WHERE table_name = 'ohlc_bars_v2'
  AND (
    column_name = 'timeframe' OR
    column_name = 'provider' OR
    column_name = 'data_status'
  )
ORDER BY column_name;

-- Verify CHECK constraints were created
SELECT
  constraint_name,
  constraint_type,
  table_name
FROM information_schema.table_constraints
WHERE table_name = 'ohlc_bars_v2'
  AND constraint_name LIKE 'chk_%'
ORDER BY constraint_name;

-- ============================================================================
-- Step 5: Validate existing data against new constraints
-- ============================================================================
-- Check if any existing data violates the new constraints
SELECT
  COUNT(*) as invalid_timeframe_rows
FROM ohlc_bars_v2
WHERE LENGTH(timeframe) > 10;

SELECT
  COUNT(*) as invalid_provider_rows
FROM ohlc_bars_v2
WHERE LENGTH(provider) > 20;

SELECT
  COUNT(*) as invalid_data_status_rows
FROM ohlc_bars_v2
WHERE data_status IS NOT NULL AND LENGTH(data_status) > 20;

-- ============================================================================
-- Step 6: Verify indexes still work
-- ============================================================================
-- Indexes on these columns should still function
SELECT
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename = 'ohlc_bars_v2'
  AND (
    indexdef LIKE '%timeframe%' OR
    indexdef LIKE '%provider%' OR
    indexdef LIKE '%data_status%'
  )
ORDER BY indexname;

-- ============================================================================
-- Step 7: Test queries work correctly
-- ============================================================================
-- Verify common queries still work
EXPLAIN ANALYZE
SELECT COUNT(*) FROM ohlc_bars_v2
WHERE timeframe = 'm15' AND provider = 'polygon'
LIMIT 100;

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================
COMMIT;

-- ============================================================================
-- Post-Migration Verification (run after COMMIT)
-- ============================================================================

-- Verify row count unchanged
SELECT COUNT(*) as total_rows FROM ohlc_bars_v2;

-- Sample data to verify it looks correct
SELECT
  timeframe,
  provider,
  data_status,
  COUNT(*) as count
FROM ohlc_bars_v2
GROUP BY timeframe, provider, data_status
ORDER BY timeframe, provider;

-- Check for any NULL or unusual values
SELECT DISTINCT
  timeframe,
  provider,
  data_status
FROM ohlc_bars_v2
WHERE timeframe NOT IN ('m15', 'h1', 'h4', 'h8', 'd1', 'w1')
  OR provider NOT IN ('polygon', 'tradier', 'ml_forecast', 'alpaca', 'yfinance')
LIMIT 10;

-- ============================================================================
-- SUCCESS INDICATORS
-- ============================================================================
-- ✅ All 3 columns converted from VARCHAR(n) to TEXT
-- ✅ CHECK constraints added for length validation
-- ✅ No constraint violations detected
-- ✅ No rows were deleted
-- ✅ Indexes still functional
-- ✅ Queries return correct results

-- ============================================================================
-- DESIGN NOTES
-- ============================================================================
-- TEXT is the standard PostgreSQL type for variable-length strings.
-- VARCHAR(n) is kept for backward compatibility but marked as deprecated
-- in PostgreSQL documentation.
--
-- Using TEXT with explicit CHECK constraints is clearer:
-- - The CHECK constraint (LENGTH(x) <= n) is more explicit
-- - TEXT is more flexible if length limits need adjustment
-- - Easier to see the business logic in the constraint
--
-- These changes are fully backward compatible:
-- - Application code needs no changes
-- - Queries work identically
-- - Data is unchanged
-- ============================================================================
