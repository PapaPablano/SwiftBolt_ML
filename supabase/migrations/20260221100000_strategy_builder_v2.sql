-- Strategy Builder Tables (v2)
-- Migration: strategy_builder_v1
-- Skip old ts_strategies, create new strategy_* tables

-- User strategies table (new)
CREATE TABLE IF NOT EXISTS strategy_user_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  name TEXT NOT NULL,
  description TEXT,
  config JSONB NOT NULL DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE strategy_user_strategies ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own user strategies"
  ON strategy_user_strategies FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own user strategies"
  ON strategy_user_strategies FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own user strategies"
  ON strategy_user_strategies FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own user strategies"
  ON strategy_user_strategies FOR DELETE
  USING (auth.uid() = user_id);

-- Backtest job queue
CREATE TABLE IF NOT EXISTS strategy_backtest_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID,
  symbol TEXT NOT NULL DEFAULT 'AAPL',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  parameters JSONB DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  error_message TEXT,
  result_id UUID,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_user_status
  ON strategy_backtest_jobs(user_id, status, created_at DESC);

-- Enable RLS
ALTER TABLE strategy_backtest_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own backtest jobs"
  ON strategy_backtest_jobs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own backtest jobs"
  ON strategy_backtest_jobs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own backtest jobs"
  ON strategy_backtest_jobs FOR UPDATE
  USING (auth.uid() = user_id);

-- Backtest results
CREATE TABLE IF NOT EXISTS strategy_backtest_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID,
  metrics JSONB NOT NULL,
  trades JSONB DEFAULT '[]',
  equity_curve JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE strategy_backtest_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Results viewable via jobs"
  ON strategy_backtest_results FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_backtest_jobs
      WHERE strategy_backtest_jobs.id = job_id
      AND strategy_backtest_jobs.user_id = auth.uid()
    )
  );

-- Function to claim pending job
CREATE OR REPLACE FUNCTION claim_pending_backtest_job()
RETURNS UUID AS $$
DECLARE
  job_id UUID;
BEGIN
  UPDATE strategy_backtest_jobs
  SET status = 'running', started_at = NOW()
  WHERE id = (
    SELECT id FROM strategy_backtest_jobs
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING id INTO job_id;
  
  RETURN job_id;
END;
$$ LANGUAGE plpgsql;
