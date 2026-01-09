-- Migration: Clean up invalid historical intraday job runs
-- Problem: job_runs table contains intraday fetch jobs for historical dates
-- Tradier only provides data for TODAY, so these jobs will always fail
-- Solution: Delete queued/failed job runs where:
--   - job_type = 'fetch_intraday'
--   - slice_to is before TODAY

-- Clean up historical intraday job runs
DELETE FROM job_runs
WHERE job_type = 'fetch_intraday'
  AND DATE(slice_to) < CURRENT_DATE
  AND status IN ('queued', 'failed', 'running');

-- Log the cleanup
DO $$
DECLARE
  deleted_count INTEGER;
BEGIN
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RAISE NOTICE 'Cleaned up % historical intraday job runs', deleted_count;
END $$;

COMMENT ON TABLE job_runs IS
'Job execution tracking.
NOTE: Intraday jobs (fetch_intraday) should only have slice_to >= CURRENT_DATE
because Tradier only provides intraday data for TODAY.';
