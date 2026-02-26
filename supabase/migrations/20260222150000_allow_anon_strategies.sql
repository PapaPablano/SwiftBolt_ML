-- Allow anon/demo users to use strategy tables without auth
-- Root cause: auth.uid() is NULL for unauthenticated requests,
-- so all existing "auth.uid() = user_id" policies block every INSERT from the web app.

-- ── strategy_user_strategies ────────────────────────────────────────────────
-- Drop the auth-only policies that block unauthenticated inserts
DROP POLICY IF EXISTS "Users can view their own user strategies"   ON strategy_user_strategies;
DROP POLICY IF EXISTS "Users can insert their own user strategies"  ON strategy_user_strategies;
DROP POLICY IF EXISTS "Users can update their own user strategies"  ON strategy_user_strategies;
DROP POLICY IF EXISTS "Users can delete their own user strategies"  ON strategy_user_strategies;

-- Re-add with anon fallback: authenticated users see their own rows;
-- unauthenticated (user_id IS NULL) rows are public to anon key.
CREATE POLICY "select_own_or_anon_strategies"
  ON strategy_user_strategies FOR SELECT
  USING (
    auth.uid() = user_id          -- authenticated owner
    OR user_id IS NULL            -- anon/demo rows
  );

CREATE POLICY "insert_own_or_anon_strategies"
  ON strategy_user_strategies FOR INSERT
  WITH CHECK (
    auth.uid() = user_id          -- authenticated owner
    OR user_id IS NULL            -- anon/demo insert
  );

CREATE POLICY "update_own_or_anon_strategies"
  ON strategy_user_strategies FOR UPDATE
  USING (
    auth.uid() = user_id
    OR user_id IS NULL
  );

CREATE POLICY "delete_own_or_anon_strategies"
  ON strategy_user_strategies FOR DELETE
  USING (
    auth.uid() = user_id
    OR user_id IS NULL
  );

-- ── strategy_backtest_jobs ──────────────────────────────────────────────────
DROP POLICY IF EXISTS "Users can view their own backtest jobs"   ON strategy_backtest_jobs;
DROP POLICY IF EXISTS "Users can insert their own backtest jobs"  ON strategy_backtest_jobs;
DROP POLICY IF EXISTS "Users can update their own backtest jobs"  ON strategy_backtest_jobs;

CREATE POLICY "select_own_or_anon_jobs"
  ON strategy_backtest_jobs FOR SELECT
  USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "insert_own_or_anon_jobs"
  ON strategy_backtest_jobs FOR INSERT
  WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "update_own_or_anon_jobs"
  ON strategy_backtest_jobs FOR UPDATE
  USING (auth.uid() = user_id OR user_id IS NULL);

-- ── strategy_backtest_results ───────────────────────────────────────────────
-- Results are read-only from the client (written by the worker)
DROP POLICY IF EXISTS "Results viewable via jobs" ON strategy_backtest_results;

CREATE POLICY "select_results_via_jobs_or_anon"
  ON strategy_backtest_results FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM strategy_backtest_jobs j
      WHERE j.id = job_id
        AND (j.user_id = auth.uid() OR j.user_id IS NULL)
    )
  );
