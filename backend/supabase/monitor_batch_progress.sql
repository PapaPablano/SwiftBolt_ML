-- Monitor Batch Job Progress
-- Run this periodically to track batch backfill progress

SELECT 
  CASE 
    WHEN jd.symbols_array IS NOT NULL THEN 'BATCH'
    ELSE 'SINGLE'
  END as job_mode,
  jd.timeframe,
  jr.status,
  COUNT(*) as jobs,
  SUM(jr.rows_written) as total_bars,
  MIN(jr.created_at) as oldest_job,
  MAX(jr.updated_at) as latest_update
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbols_array IS NOT NULL
  AND jd.timeframe = 'h1'
  AND jr.created_at > now() - interval '1 hour'
GROUP BY 
  CASE WHEN jd.symbols_array IS NOT NULL THEN 'BATCH' ELSE 'SINGLE' END,
  jd.timeframe, 
  jr.status
ORDER BY jr.status;

-- Show recent successful jobs
SELECT 
  jd.symbol,
  jsonb_array_length(jd.symbols_array) as symbols_count,
  jr.rows_written,
  jr.finished_at,
  jr.finished_at - jr.started_at as duration
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbols_array IS NOT NULL
  AND jd.timeframe = 'h1'
  AND jr.status = 'success'
ORDER BY jr.finished_at DESC
LIMIT 10;

-- Show any failed jobs
SELECT 
  jd.symbol,
  jsonb_array_length(jd.symbols_array) as symbols_count,
  jr.error_message,
  jr.finished_at
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbols_array IS NOT NULL
  AND jd.timeframe = 'h1'
  AND jr.status = 'failed'
ORDER BY jr.finished_at DESC
LIMIT 10;
