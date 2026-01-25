-- ============================================================================
-- Phase 1 Migration #1: Convert TIMESTAMP to TIMESTAMPTZ
-- ============================================================================
-- Date: January 25, 2026
-- Purpose: Fix timezone-unaware timestamps in ohlc_bars_v2 table
-- Risk Level: Low
-- Rollback: Revert with opposite type conversion
-- ============================================================================

-- Start transaction (can ROLLBACK if issues)
BEGIN TRANSACTION;

-- ============================================================================
-- Step 1: Verify current state
-- ============================================================================
-- Check current column types before migration
SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'ohlc_bars_v2'
  AND column_name IN ('ts', 'fetched_at', 'created_at', 'updated_at')
ORDER BY column_name;

-- ============================================================================
-- Step 2: Convert TIMESTAMP columns to TIMESTAMPTZ
-- ============================================================================
-- Convert all timestamp columns, assuming they contain UTC times
ALTER TABLE ohlc_bars_v2
  ALTER COLUMN ts TYPE TIMESTAMPTZ USING ts AT TIME ZONE 'UTC',
  ALTER COLUMN fetched_at TYPE TIMESTAMPTZ USING fetched_at AT TIME ZONE 'UTC',
  ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
  ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- ============================================================================
-- Step 3: Verify conversion successful
-- ============================================================================
-- Check that columns are now TIMESTAMPTZ
SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'ohlc_bars_v2'
  AND column_name IN ('ts', 'fetched_at', 'created_at', 'updated_at')
ORDER BY column_name;

-- Sample data verification
SELECT
  ts,
  fetched_at,
  created_at,
  updated_at
FROM ohlc_bars_v2
LIMIT 5;

-- ============================================================================
-- Step 4: Verify indexes still work
-- ============================================================================
-- Check that indexes on these columns are still functional
SELECT
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename = 'ohlc_bars_v2'
  AND (indexdef LIKE '%ts%' OR indexdef LIKE '%created_at%')
LIMIT 10;

-- ============================================================================
-- Step 5: Test queries work correctly
-- ============================================================================
-- Verify timezone-aware queries work
EXPLAIN ANALYZE
SELECT * FROM ohlc_bars_v2
WHERE ts > NOW() - INTERVAL '7 days'
  AND ts < NOW()
ORDER BY ts DESC
LIMIT 100;

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================
-- If no errors above, commit the changes
-- If any errors, ROLLBACK will undo all changes
COMMIT;

-- ============================================================================
-- Post-Migration Verification (run after COMMIT)
-- ============================================================================
-- This section runs AFTER the transaction commits successfully

-- Verify row count unchanged
SELECT COUNT(*) as total_rows FROM ohlc_bars_v2;

-- Verify no NULL timestamps appeared
SELECT
  SUM(CASE WHEN ts IS NULL THEN 1 ELSE 0 END) as null_ts_count,
  SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END) as null_created_at_count
FROM ohlc_bars_v2;

-- Sample different data ranges to verify timezone handling
SELECT
  DATE(ts) as date,
  COUNT(*) as count,
  MIN(ts) as earliest,
  MAX(ts) as latest
FROM ohlc_bars_v2
GROUP BY DATE(ts)
ORDER BY DATE(ts) DESC
LIMIT 10;

-- ============================================================================
-- SUCCESS INDICATORS
-- ============================================================================
-- ✅ All 4 columns converted from TIMESTAMP to TIMESTAMPTZ
-- ✅ No rows were deleted
-- ✅ No NULL values appeared
-- ✅ Indexes still functional
-- ✅ Queries return correct results
-- ✅ Timezone information preserved (assumed UTC)

-- ============================================================================
-- NOTES FOR FUTURE REFERENCE
-- ============================================================================
-- This migration assumes all TIMESTAMP values were in UTC.
-- If your system used a different timezone, you may need to adjust the
-- 'UTC' parameter in the USING clause to match your actual timezone.
--
-- The conversion uses AT TIME ZONE 'UTC' which tells PostgreSQL to interpret
-- the naive TIMESTAMP as if it were in UTC, then convert to TIMESTAMPTZ.
--
-- All downstream code that reads these timestamps should automatically
-- handle the timezone information without changes.
-- ============================================================================
