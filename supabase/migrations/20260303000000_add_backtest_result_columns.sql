-- Add missing columns to strategy_backtest_results
-- The worker inserts validation, monthly_returns, rolling_metrics, drawdown_series
-- but these columns were not in the original schema.

ALTER TABLE strategy_backtest_results
  ADD COLUMN IF NOT EXISTS validation       JSONB,
  ADD COLUMN IF NOT EXISTS monthly_returns  JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS rolling_metrics  JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS drawdown_series  JSONB DEFAULT '[]';
