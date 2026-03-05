-- Add live trading and paper trading control columns to strategy_user_strategies.
-- These are referenced by the strategies Edge Function's handleUpdate / StrategyRow interface
-- but were never added when the table was created in strategy_builder_v2.

ALTER TABLE strategy_user_strategies
  ADD COLUMN IF NOT EXISTS paper_trading_enabled   BOOLEAN   NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS live_trading_enabled    BOOLEAN   NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS live_risk_pct           NUMERIC   NOT NULL DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS live_daily_loss_limit_pct NUMERIC NOT NULL DEFAULT 5.0,
  ADD COLUMN IF NOT EXISTS live_max_positions      INTEGER   NOT NULL DEFAULT 5,
  ADD COLUMN IF NOT EXISTS live_max_position_pct   NUMERIC   NOT NULL DEFAULT 20.0,
  ADD COLUMN IF NOT EXISTS live_trading_paused     BOOLEAN   NOT NULL DEFAULT false;
