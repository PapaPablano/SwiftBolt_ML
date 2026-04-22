-- Restrict anon strategy mutations: require authentication for UPDATE/DELETE
-- Previously, anon users (user_id IS NULL) could mutate any anon row.
-- Now only authenticated owners can UPDATE or DELETE their strategies.
-- INSERT and SELECT remain unchanged (anon can still create and read).

-- ── strategy_user_strategies ────────────────────────────────────────────────

-- Drop existing UPDATE/DELETE policies that allow anon mutation
DROP POLICY IF EXISTS "update_own_or_anon_strategies" ON strategy_user_strategies;
DROP POLICY IF EXISTS "delete_own_or_anon_strategies" ON strategy_user_strategies;

-- Recreate with auth-only (no anon mutation)
CREATE POLICY "update_own_strategies"
  ON strategy_user_strategies FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "delete_own_strategies"
  ON strategy_user_strategies FOR DELETE
  USING (auth.uid() = user_id);

-- ── strategy_backtest_jobs ──────────────────────────────────────────────────

-- Drop existing UPDATE policy that allows anon mutation
DROP POLICY IF EXISTS "update_own_or_anon_jobs" ON strategy_backtest_jobs;

-- Recreate with auth-only (no anon mutation)
CREATE POLICY "update_own_jobs"
  ON strategy_backtest_jobs FOR UPDATE
  USING (auth.uid() = user_id);
