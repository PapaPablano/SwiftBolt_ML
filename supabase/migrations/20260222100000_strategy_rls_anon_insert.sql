-- RLS: Allow unauthenticated (anon) inserts for strategy tables
-- Root cause: auth.uid() is NULL for anon requests; "auth.uid() = user_id" fails for INSERT.
-- Two-path: (1) anon can insert/select/update/delete rows where user_id IS NULL;
--           (2) authenticated users keep existing policies (own user_id only).

-- strategy_user_strategies: anon can insert rows with user_id NULL
CREATE POLICY "Anon can insert user strategies with null user_id"
  ON strategy_user_strategies FOR INSERT
  WITH CHECK (auth.uid() IS NULL AND user_id IS NULL);

-- Anon can select/update/delete only rows they "own" (user_id IS NULL)
CREATE POLICY "Anon can select user strategies with null user_id"
  ON strategy_user_strategies FOR SELECT
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can update user strategies with null user_id"
  ON strategy_user_strategies FOR UPDATE
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can delete user strategies with null user_id"
  ON strategy_user_strategies FOR DELETE
  USING (auth.uid() IS NULL AND user_id IS NULL);

-- strategy_backtest_jobs: anon can insert/select/update rows with user_id NULL
CREATE POLICY "Anon can insert backtest jobs with null user_id"
  ON strategy_backtest_jobs FOR INSERT
  WITH CHECK (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can select backtest jobs with null user_id"
  ON strategy_backtest_jobs FOR SELECT
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can update backtest jobs with null user_id"
  ON strategy_backtest_jobs FOR UPDATE
  USING (auth.uid() IS NULL AND user_id IS NULL);
