-- Fix FK constraints for demo mode: keep columns nullable, re-add as nullable FKs
-- strategy_backtest_jobs: user_id nullable, FK to auth.users when present
ALTER TABLE strategy_backtest_jobs DROP CONSTRAINT IF EXISTS strategy_backtest_jobs_user_id_fkey;
ALTER TABLE strategy_backtest_jobs ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE strategy_backtest_jobs
  ADD CONSTRAINT strategy_backtest_jobs_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- strategy_backtest_results: job_id nullable FK to strategy_backtest_jobs
ALTER TABLE strategy_backtest_results DROP CONSTRAINT IF EXISTS strategy_backtest_results_job_id_fkey;
ALTER TABLE strategy_backtest_results
  ADD CONSTRAINT strategy_backtest_results_job_id_fkey
  FOREIGN KEY (job_id) REFERENCES strategy_backtest_jobs(id) ON DELETE CASCADE;
