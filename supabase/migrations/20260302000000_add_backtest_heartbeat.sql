-- Add heartbeat_at column for worker liveness tracking
-- and partial index for efficient stale job detection.

ALTER TABLE strategy_backtest_jobs
  ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

-- Partial index: only index running jobs for stale cleanup queries
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_stale
  ON strategy_backtest_jobs(started_at)
  WHERE status = 'running';
