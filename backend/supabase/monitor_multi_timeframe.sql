-- Multi-Timeframe Monitoring Queries
-- Use these queries to monitor backfill progress and coverage across timeframes

-- ============================================================================
-- 1. Check Coverage Across All Timeframes for Specific Symbols
-- ============================================================================

SELECT 
  s.ticker,
  COUNT(*) FILTER (WHERE o.timeframe = 'm15') as m15_bars,
  COUNT(*) FILTER (WHERE o.timeframe = 'h1') as h1_bars,
  COUNT(*) FILTER (WHERE o.timeframe = 'h4') as h4_bars,
  MIN(o.timestamp) FILTER (WHERE o.timeframe = 'm15') as m15_earliest,
  MAX(o.timestamp) FILTER (WHERE o.timeframe = 'm15') as m15_latest,
  MIN(o.timestamp) FILTER (WHERE o.timeframe = 'h1') as h1_earliest,
  MAX(o.timestamp) FILTER (WHERE o.timeframe = 'h1') as h1_latest,
  MIN(o.timestamp) FILTER (WHERE o.timeframe = 'h4') as h4_earliest,
  MAX(o.timestamp) FILTER (WHERE o.timeframe = 'h4') as h4_latest
FROM symbols s
LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id AND o.timeframe IN ('m15', 'h1', 'h4')
WHERE s.ticker IN ('AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL')
GROUP BY s.ticker
ORDER BY s.ticker;

-- ============================================================================
-- 2. Job Processing Stats by Timeframe (Last Hour)
-- ============================================================================

SELECT * FROM get_timeframe_job_stats(1);

-- ============================================================================
-- 3. Active Job Definitions by Timeframe
-- ============================================================================

SELECT 
  timeframe,
  COUNT(*) as total_jobs,
  COUNT(*) FILTER (WHERE enabled = true) as enabled_jobs,
  AVG(priority) as avg_priority,
  MIN(priority) as min_priority,
  MAX(priority) as max_priority
FROM job_definitions
WHERE timeframe IN ('m15', 'h1', 'h4')
GROUP BY timeframe
ORDER BY 
  CASE timeframe 
    WHEN 'h1' THEN 1 
    WHEN 'h4' THEN 2 
    WHEN 'm15' THEN 3 
  END;

-- ============================================================================
-- 4. Coverage Status Summary
-- ============================================================================

SELECT 
  timeframe,
  COUNT(*) as symbols_with_coverage,
  AVG(EXTRACT(EPOCH FROM (to_ts - from_ts)) / 86400.0) as avg_coverage_days,
  MIN(last_success_at) as oldest_fetch,
  MAX(last_success_at) as newest_fetch,
  SUM(last_rows_written) as total_bars_written
FROM coverage_status
WHERE timeframe IN ('m15', 'h1', 'h4')
GROUP BY timeframe
ORDER BY 
  CASE timeframe 
    WHEN 'h1' THEN 1 
    WHEN 'h4' THEN 2 
    WHEN 'm15' THEN 3 
  END;

-- ============================================================================
-- 5. User Symbol Tracking Summary
-- ============================================================================

SELECT 
  source,
  COUNT(DISTINCT symbol_id) as unique_symbols,
  COUNT(*) as total_tracking_entries,
  AVG(priority) as avg_priority,
  MIN(created_at) as first_tracked,
  MAX(updated_at) as last_updated
FROM user_symbol_tracking
GROUP BY source
ORDER BY avg_priority DESC;

-- ============================================================================
-- 6. Detailed Symbol Coverage Report (Use for specific symbol)
-- ============================================================================

-- Example: Check AAPL coverage across all timeframes
SELECT * FROM get_symbol_timeframe_coverage('AAPL');

-- ============================================================================
-- 7. Recent Job Runs with Errors
-- ============================================================================

SELECT 
  jr.symbol,
  jr.timeframe,
  jr.status,
  jr.error_message,
  jr.error_code,
  jr.attempt,
  jr.created_at,
  jr.finished_at,
  EXTRACT(EPOCH FROM (jr.finished_at - jr.started_at)) as duration_seconds
FROM job_runs jr
WHERE jr.status = 'failed'
  AND jr.created_at > now() - interval '1 hour'
  AND jr.timeframe IN ('m15', 'h1', 'h4')
ORDER BY jr.created_at DESC
LIMIT 20;

-- ============================================================================
-- 8. Top Priority Symbols Awaiting Backfill
-- ============================================================================

SELECT 
  jd.symbol,
  jd.timeframe,
  jd.priority,
  jd.enabled,
  cs.last_success_at,
  cs.from_ts,
  cs.to_ts,
  COALESCE(pending.pending_jobs, 0) as pending_jobs,
  COALESCE(running.running_jobs, 0) as running_jobs
FROM job_definitions jd
LEFT JOIN coverage_status cs ON cs.symbol = jd.symbol AND cs.timeframe = jd.timeframe
LEFT JOIN (
  SELECT symbol, timeframe, COUNT(*) as pending_jobs
  FROM job_runs
  WHERE status = 'queued'
  GROUP BY symbol, timeframe
) pending ON pending.symbol = jd.symbol AND pending.timeframe = jd.timeframe
LEFT JOIN (
  SELECT symbol, timeframe, COUNT(*) as running_jobs
  FROM job_runs
  WHERE status = 'running'
  GROUP BY symbol, timeframe
) running ON running.symbol = jd.symbol AND running.timeframe = jd.timeframe
WHERE jd.enabled = true
  AND jd.timeframe IN ('m15', 'h1', 'h4')
ORDER BY jd.priority DESC, jd.symbol, jd.timeframe
LIMIT 50;

-- ============================================================================
-- 9. Backfill Progress for Watchlist Symbols
-- ============================================================================

SELECT 
  ust.source,
  s.ticker,
  ust.priority,
  COUNT(DISTINCT o.id) FILTER (WHERE o.timeframe = 'm15') as m15_bars,
  COUNT(DISTINCT o.id) FILTER (WHERE o.timeframe = 'h1') as h1_bars,
  COUNT(DISTINCT o.id) FILTER (WHERE o.timeframe = 'h4') as h4_bars,
  COUNT(DISTINCT jr.id) FILTER (WHERE jr.status = 'queued') as queued_jobs,
  COUNT(DISTINCT jr.id) FILTER (WHERE jr.status = 'running') as running_jobs,
  COUNT(DISTINCT jr.id) FILTER (WHERE jr.status = 'success') as completed_jobs,
  MAX(jr.finished_at) as last_job_finish
FROM user_symbol_tracking ust
JOIN symbols s ON ust.symbol_id = s.id
LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id AND o.timeframe IN ('m15', 'h1', 'h4')
LEFT JOIN job_runs jr ON jr.symbol = s.ticker AND jr.created_at > ust.created_at
GROUP BY ust.source, s.ticker, ust.priority
ORDER BY ust.priority DESC, s.ticker;

-- ============================================================================
-- 10. System Health Check
-- ============================================================================

WITH timeframe_stats AS (
  SELECT 
    timeframe,
    COUNT(*) FILTER (WHERE status = 'success') as success_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
    COUNT(*) FILTER (WHERE status = 'running') as running_count,
    COUNT(*) FILTER (WHERE status = 'queued') as queued_count
  FROM job_runs
  WHERE created_at > now() - interval '1 hour'
    AND timeframe IN ('m15', 'h1', 'h4')
  GROUP BY timeframe
)
SELECT 
  timeframe,
  success_count,
  failed_count,
  running_count,
  queued_count,
  CASE 
    WHEN success_count + failed_count = 0 THEN 0
    ELSE ROUND((success_count::numeric / (success_count + failed_count)) * 100, 2)
  END as success_rate_pct,
  CASE
    WHEN success_count > 10 AND success_rate_pct > 90 THEN '✅ Healthy'
    WHEN success_count > 5 AND success_rate_pct > 75 THEN '⚠️ Degraded'
    ELSE '❌ Unhealthy'
  END as health_status
FROM timeframe_stats
ORDER BY 
  CASE timeframe 
    WHEN 'h1' THEN 1 
    WHEN 'h4' THEN 2 
    WHEN 'm15' THEN 3 
  END;
