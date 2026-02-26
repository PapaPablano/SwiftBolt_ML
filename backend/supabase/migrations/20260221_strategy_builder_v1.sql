-- Strategy Builder Tables
-- Migration: strategy_builder_v1
-- Created: 2026-02-21

-- User strategies table
CREATE TABLE IF NOT EXISTS strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  config JSONB NOT NULL DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- RLS Policies for strategies
CREATE POLICY "Users can view their own strategies"
  ON strategies FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own strategies"
  ON strategies FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own strategies"
  ON strategies FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own strategies"
  ON strategies FOR DELETE
  USING (auth.uid() = user_id);

-- Backtest job queue
CREATE TABLE IF NOT EXISTS strategy_backtest_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID REFERENCES strategies(id) ON DELETE CASCADE,
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

-- Index for job polling
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_user_status
  ON strategy_backtest_jobs(user_id, status, created_at DESC);

-- Enable RLS
ALTER TABLE strategy_backtest_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own backtest jobs"
  ON strategy_backtest_jobs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own backtest jobs"
  ON strategy_backtest_jobs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own backtest jobs"
  ON strategy_backtest_jobs FOR UPDATE
  USING (auth.uid() = user_id);

-- Backtest results storage
CREATE TABLE IF NOT EXISTS strategy_backtest_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES strategy_backtest_jobs(id) ON DELETE CASCADE,
  metrics JSONB NOT NULL,
  trades JSONB DEFAULT '[]',
  equity_curve JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE strategy_backtest_results ENABLE ROW LEVEL SECURITY;

-- RLS: Results accessible via job ownership
CREATE POLICY "Results viewable via jobs"
  ON strategy_backtest_results FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_backtest_jobs
      WHERE strategy_backtest_jobs.id = job_id
      AND strategy_backtest_jobs.user_id = auth.uid()
    )
  );

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_strategy_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-updating timestamp
CREATE TRIGGER strategy_updated_at
  BEFORE UPDATE ON strategies
  FOR EACH ROW
  EXECUTE FUNCTION update_strategy_timestamp();

-- Function to claim pending job (for worker)
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

COMMENT ON TABLE strategies IS 'User-defined trading strategies with entry/exit conditions';
COMMENT ON TABLE strategy_backtest_jobs IS 'Queue for backtest jobs with status tracking';
COMMENT ON TABLE strategy_backtest_results IS 'Stored results from backtest runs';
