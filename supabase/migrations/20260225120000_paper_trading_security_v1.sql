-- Paper Trading Security & Data Integrity Migration
-- Implements: RLS policies, CHECK constraints, race condition prevention
-- Date: 2026-02-25
-- Status: Blocks deployment without these protections

-- ============================================================================
-- 1. PAPER TRADING POSITIONS TABLE
-- ============================================================================
-- Tracks open positions in paper trading
-- Uses status='open' for optimistic locking to prevent race conditions
CREATE TABLE IF NOT EXISTS paper_trading_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL,
  symbol_id UUID NOT NULL,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL(12,4) NOT NULL CHECK (entry_price > 0),
  current_price DECIMAL(12,4),
  quantity INT NOT NULL CHECK (quantity > 0 AND quantity <= 1000),
  entry_time TIMESTAMPTZ NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  stop_loss_price DECIMAL(12,4) NOT NULL CHECK (stop_loss_price > 0),
  take_profit_price DECIMAL(12,4) NOT NULL CHECK (take_profit_price > 0),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'pending_entry', 'partial_fill')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Constraint: For long positions, SL < entry < TP
  CONSTRAINT long_position_levels CHECK (
    (direction = 'long' AND stop_loss_price < entry_price AND entry_price < take_profit_price)
    OR
    (direction = 'short' AND take_profit_price < entry_price AND entry_price < stop_loss_price)
  )
);

-- Create index for common queries (user_id first for RLS filtering)
CREATE INDEX IF NOT EXISTS idx_paper_positions_user_strategy
  ON paper_trading_positions(user_id, strategy_id, symbol_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_positions_status
  ON paper_trading_positions(status, user_id);

-- Enable RLS
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;

-- RLS: Users can only access their own positions
CREATE POLICY "Users can view their own paper positions"
  ON paper_trading_positions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own paper positions"
  ON paper_trading_positions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own paper positions"
  ON paper_trading_positions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own paper positions"
  ON paper_trading_positions FOR DELETE
  USING (auth.uid() = user_id);

-- ============================================================================
-- 2. PAPER TRADING TRADES TABLE
-- ============================================================================
-- Immutable audit trail of closed trades
-- APPEND-ONLY: RLS prevents modification of closed trades
CREATE TABLE IF NOT EXISTS paper_trading_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
  strategy_id UUID NOT NULL,
  symbol_id UUID NOT NULL,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL(12,4) NOT NULL CHECK (entry_price > 0),
  exit_price DECIMAL(12,4) NOT NULL CHECK (exit_price > 0),
  quantity INT NOT NULL CHECK (quantity > 0 AND quantity <= 1000),
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  entry_time TIMESTAMPTZ NOT NULL,
  exit_time TIMESTAMPTZ NOT NULL CHECK (exit_time > entry_time),
  pnl DECIMAL(12,2) NOT NULL,
  pnl_pct DECIMAL(7,4) NOT NULL,
  close_reason TEXT NOT NULL CHECK (close_reason IN ('SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE', 'GAP_FORCED_CLOSE')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for historical queries
CREATE INDEX IF NOT EXISTS idx_paper_trades_user_strategy
  ON paper_trading_trades(user_id, strategy_id, symbol_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_trades_user_date
  ON paper_trading_trades(user_id, created_at DESC);

-- Enable RLS
ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;

-- RLS: Users can view their own trades
CREATE POLICY "Users can view their own paper trades"
  ON paper_trading_trades FOR SELECT
  USING (auth.uid() = user_id);

-- RLS: Users can INSERT trades (executor on their behalf)
CREATE POLICY "Users can insert their own paper trades"
  ON paper_trading_trades FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- RLS: Users CANNOT UPDATE/DELETE trades (immutable audit trail)
-- Prevents modifying closed trade results to hide losses
CREATE POLICY "No updates to paper trades (immutable)"
  ON paper_trading_trades FOR UPDATE
  USING (FALSE);

CREATE POLICY "No deletes to paper trades (immutable)"
  ON paper_trading_trades FOR DELETE
  USING (FALSE);

-- ============================================================================
-- 3. STRATEGY EXECUTION LOG
-- ============================================================================
-- Append-only log of when/why strategies triggered
-- Used for debugging divergence between backtest and paper trading
CREATE TABLE IF NOT EXISTS strategy_execution_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL,
  symbol_id UUID NOT NULL,
  timeframe TEXT NOT NULL,
  candle_time TIMESTAMPTZ NOT NULL,
  signal_type TEXT NOT NULL CHECK (signal_type IN ('entry', 'exit', 'condition_met', 'sl_triggered', 'tp_triggered', 'error')),
  triggered_conditions UUID[] DEFAULT '{}',
  action_taken TEXT,
  execution_details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for historical queries
CREATE INDEX IF NOT EXISTS idx_execution_log_user_strategy
  ON strategy_execution_log(user_id, strategy_id, candle_time DESC);

-- Enable RLS
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;

-- RLS: Users can only view their own execution logs
CREATE POLICY "Users can view their own execution logs"
  ON strategy_execution_log FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own execution logs"
  ON strategy_execution_log FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- No updates or deletes (append-only audit trail)
CREATE POLICY "No updates to execution logs (immutable)"
  ON strategy_execution_log FOR UPDATE
  USING (FALSE);

CREATE POLICY "No deletes to execution logs (immutable)"
  ON strategy_execution_log FOR DELETE
  USING (FALSE);

-- ============================================================================
-- 4. PAPER TRADING METRICS
-- ============================================================================
-- Aggregated performance metrics per strategy/symbol/timeframe
CREATE TABLE IF NOT EXISTS paper_trading_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL,
  symbol_id UUID NOT NULL,
  timeframe TEXT NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL CHECK (period_end > period_start),
  trades_count INT DEFAULT 0 CHECK (trades_count >= 0),
  win_count INT DEFAULT 0 CHECK (win_count >= 0),
  loss_count INT DEFAULT 0 CHECK (loss_count >= 0),
  avg_win DECIMAL(12,2),
  avg_loss DECIMAL(12,2),
  win_rate DECIMAL(5,2) CHECK (win_rate >= 0 AND win_rate <= 100),
  profit_factor DECIMAL(7,2) CHECK (profit_factor >= 0),
  max_drawdown DECIMAL(7,4) CHECK (max_drawdown >= -100 AND max_drawdown <= 0),
  total_pnl DECIMAL(12,2),
  total_pnl_pct DECIMAL(7,4),
  sharpe_ratio DECIMAL(7,4),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user metrics queries
CREATE INDEX IF NOT EXISTS idx_metrics_user_strategy
  ON paper_trading_metrics(user_id, strategy_id, period_end DESC);

-- Enable RLS
ALTER TABLE paper_trading_metrics ENABLE ROW LEVEL SECURITY;

-- RLS: Users can view their own metrics
CREATE POLICY "Users can view their own metrics"
  ON paper_trading_metrics FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own metrics"
  ON paper_trading_metrics FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own metrics"
  ON paper_trading_metrics FOR UPDATE
  USING (auth.uid() = user_id);

-- ============================================================================
-- 5. ENHANCE EXISTING STRATEGY TABLE
-- ============================================================================
-- Add paper trading fields to strategy_user_strategies
ALTER TABLE strategy_user_strategies ADD COLUMN IF NOT EXISTS paper_trading_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE strategy_user_strategies ADD COLUMN IF NOT EXISTS paper_capital DECIMAL(12,2) DEFAULT 10000.00 CHECK (paper_capital > 0);
ALTER TABLE strategy_user_strategies ADD COLUMN IF NOT EXISTS paper_start_date TIMESTAMPTZ;
ALTER TABLE strategy_user_strategies ADD COLUMN IF NOT EXISTS slippage_pct DECIMAL(5,4) DEFAULT 2.0 CHECK (slippage_pct >= 0.01 AND slippage_pct <= 5.0);

-- ============================================================================
-- 6. SAFE POSITION CLOSURE FUNCTION
-- ============================================================================
-- Implements optimistic locking to prevent race conditions
-- Only closes if status is still 'open' (prevents double-close phantom trades)
CREATE OR REPLACE FUNCTION close_paper_position(
  p_position_id UUID,
  p_exit_price DECIMAL,
  p_close_reason TEXT
) RETURNS JSONB AS $$
DECLARE
  v_position RECORD;
  v_pnl DECIMAL;
  v_pnl_pct DECIMAL;
  v_result JSONB;
BEGIN
  -- Fetch position with lock to prevent concurrent updates
  SELECT * INTO v_position FROM paper_trading_positions
  WHERE id = p_position_id AND status = 'open'
  FOR UPDATE;

  -- Check if position still exists and is open (race condition check)
  IF v_position IS NULL THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', 'Position already closed or not found',
      'code', 'RACE_CONDITION'
    );
  END IF;

  -- Calculate P&L
  IF v_position.direction = 'long' THEN
    v_pnl := (p_exit_price - v_position.entry_price) * v_position.quantity;
    v_pnl_pct := ((p_exit_price - v_position.entry_price) / v_position.entry_price) * 100;
  ELSE
    v_pnl := (v_position.entry_price - p_exit_price) * v_position.quantity;
    v_pnl_pct := ((v_position.entry_price - p_exit_price) / v_position.entry_price) * 100;
  END IF;

  -- Update position to closed
  UPDATE paper_trading_positions
  SET
    status = 'closed',
    current_price = p_exit_price,
    updated_at = NOW()
  WHERE id = p_position_id;

  -- Insert closed trade (append-only audit trail)
  INSERT INTO paper_trading_trades (
    user_id, strategy_id, symbol_id, timeframe,
    entry_price, exit_price, quantity, direction,
    entry_time, exit_time, pnl, pnl_pct, close_reason
  ) VALUES (
    v_position.user_id, v_position.strategy_id, v_position.symbol_id, v_position.timeframe,
    v_position.entry_price, p_exit_price, v_position.quantity, v_position.direction,
    v_position.entry_time, NOW(), v_pnl, v_pnl_pct, p_close_reason
  );

  RETURN jsonb_build_object(
    'success', true,
    'pnl', v_pnl,
    'pnl_pct', v_pnl_pct,
    'close_reason', p_close_reason
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute to authenticated users only
GRANT EXECUTE ON FUNCTION close_paper_position TO authenticated;

-- ============================================================================
-- 7. ANONYMOUS USER SUPPORT (for demo mode)
-- ============================================================================
-- Allow anonymous users to use paper trading with user_id = NULL
CREATE POLICY "Anon can insert paper positions with null user_id"
  ON paper_trading_positions FOR INSERT
  WITH CHECK (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can view paper positions with null user_id"
  ON paper_trading_positions FOR SELECT
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can update paper positions with null user_id"
  ON paper_trading_positions FOR UPDATE
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can insert paper trades with null user_id"
  ON paper_trading_trades FOR INSERT
  WITH CHECK (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can view paper trades with null user_id"
  ON paper_trading_trades FOR SELECT
  USING (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can insert execution logs with null user_id"
  ON strategy_execution_log FOR INSERT
  WITH CHECK (auth.uid() IS NULL AND user_id IS NULL);

CREATE POLICY "Anon can view execution logs with null user_id"
  ON strategy_execution_log FOR SELECT
  USING (auth.uid() IS NULL AND user_id IS NULL);

-- ============================================================================
-- 8. MIGRATION VERIFICATION QUERIES
-- ============================================================================
-- These queries can be run to verify migration applied correctly:
-- SELECT * FROM information_schema.tables WHERE table_name LIKE 'paper_trading_%';
-- SELECT constraint_name, constraint_type FROM information_schema.table_constraints WHERE table_name = 'paper_trading_positions';
-- SELECT * FROM pg_policies WHERE tablename LIKE 'paper_trading_%';
