-- Fix Batch Job Queue
-- This script clears old queued jobs and ensures batch jobs are ready to execute

-- Step 1: Clear old single-symbol queued jobs that are blocking the queue
DELETE FROM job_runs
WHERE status = 'queued'
  AND job_def_id IN (
    SELECT id FROM job_definitions 
    WHERE symbols_array IS NULL AND timeframe = 'h1'
  );

-- Step 2: Reset any failed batch jobs to queued status
UPDATE job_runs
SET status = 'queued',
    started_at = NULL,
    finished_at = NULL,
    error_message = NULL,
    updated_at = now()
WHERE job_def_id IN (
  SELECT id FROM job_definitions 
  WHERE symbols_array IS NOT NULL AND timeframe = 'h1'
)
AND status IN ('failed', 'running');

-- Step 3: Verify batch jobs are ready
SELECT 
  CASE 
    WHEN jd.symbols_array IS NOT NULL THEN 'batch'
    ELSE 'single'
  END as job_mode,
  jd.timeframe,
  jr.status,
  COUNT(*) as job_count,
  SUM(jr.rows_written) as total_bars
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.timeframe = 'h1'
GROUP BY 
  CASE WHEN jd.symbols_array IS NOT NULL THEN 'batch' ELSE 'single' END,
  jd.timeframe, 
  jr.status
ORDER BY job_mode, jr.status;

-- Step 4: Show next jobs that will be claimed
SELECT 
  jr.id,
  jd.symbol,
  CASE 
    WHEN jd.symbols_array IS NOT NULL THEN 'BATCH (' || jsonb_array_length(jd.symbols_array) || ' symbols)'
    ELSE 'SINGLE'
  END as job_mode,
  jd.timeframe,
  jr.status,
  jr.created_at
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jr.status = 'queued'
ORDER BY jr.created_at ASC
LIMIT 10;
