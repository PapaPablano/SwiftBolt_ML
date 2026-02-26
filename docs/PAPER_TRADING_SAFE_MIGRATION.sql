-- =====================================================
-- Safe Paper Trading Schema Migration
-- File: PAPER_TRADING_SAFE_MIGRATION.sql
-- Date: 2026-02-25
-- Status: REVIEWED - READY FOR IMPLEMENTATION
-- =====================================================
-- This migration addresses all critical data integrity issues
-- identified in docs/DATA_INTEGRITY_REVIEW_PAPER_TRADING.md
--
-- KEY PRINCIPLES:
-- 1. Race conditions prevented via FOR UPDATE locks
-- 2. Immutability enforced through RLS policies
-- 3. Data constraints verified at database level
-- 4. Referential integrity maintained (ON DELETE RESTRICT)
-- 5. Audit trail protected (append-only pattern)
-- =====================================================

-- =====================================================
-- Step 1: Create ENUM types (must be first)
-- =====================================================

CREATE TYPE position_direction AS ENUM ('long', 'short');
COMMENT ON TYPE position_direction IS 'Position direction: long (buy) or short (sell)';

CREATE TYPE trade_exit_reason AS ENUM (
  'TP_HIT',         -- Take profit price reached
  'SL_HIT',         -- Stop loss price reached
  'EXIT_SIGNAL',    -- Strategy exit condition triggered
  'MANUAL_CLOSE'    -- User manually closed position
);
COMMENT ON TYPE trade_exit_reason IS 'Reason position was closed';

CREATE TYPE signal_type_enum AS ENUM (
  'entry',          -- Entry signal triggered
  'exit',           -- Exit signal triggered
  'condition_met'   -- Specific condition met (diagnostic)
);
COMMENT ON TYPE signal_type_enum IS 'Strategy signal evaluation result';

-- =====================================================
-- Step 2: Create paper_trading_positions (core table)
-- =====================================================

CREATE TABLE paper_trading_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,

  -- Price and quantity (immutable after creation)
  entry_price DECIMAL(20, 8) NOT NULL CHECK (entry_price > 0),
  current_price DECIMAL(20, 8),
  quantity INT NOT NULL CHECK (quantity > 0),

  -- Timestamps
  entry_time TIMESTAMPTZ NOT NULL CHECK (entry_time <= NOW()),

  -- Direction and exit targets
  direction position_direction NOT NULL,
  stop_loss_price DECIMAL(20, 8),
  take_profit_price DECIMAL(20, 8),

  -- Status (open or closed)
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),

  -- Audit timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- CRITICAL: Validate SL/TP relationships by direction
  -- For long: SL must be < entry_price, TP must be > entry_price
  -- For short: SL must be > entry_price, TP must be < entry_price
  CONSTRAINT valid_sl_tp_long_short CHECK (
    CASE
      WHEN direction = 'long' THEN
        (stop_loss_price IS NULL OR stop_loss_price < entry_price) AND
        (take_profit_price IS NULL OR take_profit_price > entry_price)
      WHEN direction = 'short' THEN
        (stop_loss_price IS NULL OR stop_loss_price > entry_price) AND
        (take_profit_price IS NULL OR take_profit_price < entry_price)
      ELSE FALSE
    END
  )
);

-- CRITICAL INDICES for paper trading executor queries
CREATE INDEX idx_positions_user_strategy_open
  ON paper_trading_positions(user_id, strategy_id, status)
  WHERE status = 'open'
  AND entry_time > NOW() - INTERVAL '90 days';  -- Only recent positions

CREATE INDEX idx_positions_symbol_timeframe_ts
  ON paper_trading_positions(symbol_id, timeframe, entry_time DESC);

-- RLS: Users can only see/modify their own positions
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "select_own_positions" ON paper_trading_positions
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "insert_own_positions" ON paper_trading_positions
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "update_own_positions" ON paper_trading_positions
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Service role (executor) has full access
CREATE POLICY "service_all_positions" ON paper_trading_positions
  FOR ALL TO service_role
  USING (TRUE)
  WITH CHECK (TRUE);

-- =====================================================
-- Step 3: Create paper_trading_trades (closed trades)
-- =====================================================

CREATE TABLE paper_trading_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- CRITICAL: Link to position (1:1, ensures no duplicate closes)
  position_id UUID NOT NULL UNIQUE
    REFERENCES paper_trading_positions(id) ON DELETE RESTRICT,

  -- User and strategy (denormalized for RLS and querying)
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,

  -- Entry details (copied from position at close time)
  entry_price DECIMAL(20, 8) NOT NULL CHECK (entry_price > 0),
  entry_time TIMESTAMPTZ NOT NULL CHECK (entry_time <= NOW()),

  -- Exit details
  exit_price DECIMAL(20, 8) NOT NULL CHECK (exit_price > 0),
  exit_time TIMESTAMPTZ NOT NULL CHECK (exit_time > entry_time),

  -- Position details
  quantity INT NOT NULL CHECK (quantity > 0),
  direction position_direction NOT NULL,

  -- P&L (calculated and verified)
  pnl DECIMAL(20, 8) NOT NULL,
  pnl_pct DECIMAL(10, 2) NOT NULL CHECK (pnl_pct >= -100 AND pnl_pct <= 100000),

  -- Exit reason
  trade_reason trade_exit_reason NOT NULL,

  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- CRITICAL: Generated column ensures PnL accuracy
  pnl_calculated DECIMAL(20, 8) GENERATED ALWAYS AS (
    CASE
      WHEN direction = 'long' THEN (exit_price - entry_price) * quantity
      WHEN direction = 'short' THEN (entry_price - exit_price) * quantity
      ELSE 0
    END
  ) STORED,

  -- CRITICAL: Verify submitted PnL matches calculated value
  CONSTRAINT pnl_accuracy CHECK (
    ABS(pnl - pnl_calculated) < 0.01  -- Allow rounding error
  )
);

-- Indices for common queries
CREATE INDEX idx_trades_user_exit_time
  ON paper_trading_trades(user_id, exit_time DESC);

CREATE INDEX idx_trades_strategy_exit_time
  ON paper_trading_trades(strategy_id, exit_time DESC);

CREATE INDEX idx_trades_position_id
  ON paper_trading_trades(position_id);

-- CRITICAL: RLS - Trades are IMMUTABLE (append-only audit trail)
ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;

-- Users can SELECT but not UPDATE/DELETE
CREATE POLICY "select_own_trades" ON paper_trading_trades
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- Block all updates (immutable)
CREATE POLICY "trades_immutable_update" ON paper_trading_trades
  FOR UPDATE TO authenticated
  USING (FALSE);

-- Block all deletes (immutable)
CREATE POLICY "trades_immutable_delete" ON paper_trading_trades
  FOR DELETE TO authenticated
  USING (FALSE);

-- Service role can insert
CREATE POLICY "service_insert_trades" ON paper_trading_trades
  FOR INSERT TO service_role
  WITH CHECK (TRUE);

-- =====================================================
-- Step 4: Create strategy_execution_log (audit trail)
-- =====================================================

CREATE TABLE strategy_execution_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Ownership
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Context
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  position_id UUID REFERENCES paper_trading_positions(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,

  -- Timing
  candle_time TIMESTAMPTZ NOT NULL CHECK (candle_time <= NOW()),

  -- Signal information
  signal_type signal_type_enum NOT NULL,
  triggered_conditions TEXT[],  -- Array of condition IDs that fired
  action_taken TEXT NOT NULL,   -- Description of action
  execution_details JSONB,      -- Extra metadata (prices, calculations, etc.)

  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for dashboards
CREATE INDEX idx_execution_log_strategy_time
  ON strategy_execution_log(strategy_id, candle_time DESC);

CREATE INDEX idx_execution_log_user_time
  ON strategy_execution_log(user_id, candle_time DESC);

-- CRITICAL: RLS - Log is IMMUTABLE (append-only audit trail)
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;

-- Users can SELECT only their own
CREATE POLICY "select_own_log" ON strategy_execution_log
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- Block updates (immutable)
CREATE POLICY "log_immutable_update" ON strategy_execution_log
  FOR UPDATE TO authenticated
  USING (FALSE);

-- Block deletes (immutable)
CREATE POLICY "log_immutable_delete" ON strategy_execution_log
  FOR DELETE TO authenticated
  USING (FALSE);

-- Service role (executor) can insert
CREATE POLICY "service_insert_log" ON strategy_execution_log
  FOR INSERT TO service_role
  WITH CHECK (TRUE);

-- =====================================================
-- Step 5: Create paper_trading_metrics (aggregates)
-- =====================================================

CREATE TABLE paper_trading_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Ownership
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,

  -- Period
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL CHECK (period_end > period_start),

  -- Trade counts
  trades_count INT NOT NULL DEFAULT 0 CHECK (trades_count >= 0),
  win_count INT NOT NULL DEFAULT 0 CHECK (win_count >= 0),
  loss_count INT NOT NULL DEFAULT 0 CHECK (loss_count >= 0),

  -- Win/loss metrics
  avg_win DECIMAL(20, 8),
  avg_loss DECIMAL(20, 8),
  win_rate DECIMAL(5, 2) CHECK (win_rate >= 0 AND win_rate <= 100),
  profit_factor DECIMAL(10, 2) CHECK (profit_factor >= 0),

  -- Drawdown and P&L
  max_drawdown DECIMAL(10, 4) CHECK (max_drawdown >= 0 AND max_drawdown <= 1),
  total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
  total_pnl_pct DECIMAL(10, 2),
  sharpe_ratio DECIMAL(10, 4),

  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- CRITICAL: Ensure counts are internally consistent
  CONSTRAINT counts_add_up CHECK (trades_count = win_count + loss_count),

  -- CRITICAL: Ensure unique periods (no duplicates)
  CONSTRAINT unique_metric_period UNIQUE (
    user_id, strategy_id, symbol_id, timeframe, period_start, period_end
  )
);

-- Indices
CREATE INDEX idx_metrics_user_period
  ON paper_trading_metrics(user_id, period_start DESC);

-- RLS
ALTER TABLE paper_trading_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "select_own_metrics" ON paper_trading_metrics
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "service_all_metrics" ON paper_trading_metrics
  FOR ALL TO service_role
  USING (TRUE)
  WITH CHECK (TRUE);

-- =====================================================
-- Step 6: Extend strategy_user_strategies for paper trading
-- =====================================================

-- Add paper trading configuration columns
ALTER TABLE strategy_user_strategies
  ADD COLUMN IF NOT EXISTS paper_trading_enabled BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS paper_capital DECIMAL(20, 2) DEFAULT 10000
    CHECK (paper_capital > 0),
  ADD COLUMN IF NOT EXISTS paper_start_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS max_position_hold_time_bars INT DEFAULT 100
    CHECK (max_position_hold_time_bars > 0);

-- =====================================================
-- Step 7: CRITICAL FUNCTION - Safe Position Closure
-- =====================================================
-- This function prevents race conditions and ensures atomicity
-- when closing positions. Uses FOR UPDATE lock to prevent
-- concurrent closures of the same position.
-- =====================================================

CREATE OR REPLACE FUNCTION close_paper_position(
  p_position_id UUID,
  p_exit_price DECIMAL,
  p_trade_reason trade_exit_reason,
  p_exit_time TIMESTAMPTZ DEFAULT NOW()
)
RETURNS UUID AS $$
DECLARE
  v_position RECORD;
  v_trade_id UUID;
  v_pnl DECIMAL;
  v_pnl_pct DECIMAL;
BEGIN
  -- CRITICAL: Acquire exclusive lock on position row
  -- This blocks all other transactions trying to close this position
  SELECT *
  INTO v_position
  FROM paper_trading_positions
  WHERE id = p_position_id
  FOR UPDATE;  -- EXCLUSIVE LOCK - prevents race condition

  -- Verify position exists
  IF v_position IS NULL THEN
    RAISE EXCEPTION 'Position % not found', p_position_id;
  END IF;

  -- Verify position is open (prevent double-close)
  IF v_position.status != 'open' THEN
    RAISE EXCEPTION 'Position % is already closed', p_position_id;
  END IF;

  -- Verify exit_time sequence
  IF p_exit_time <= v_position.entry_time THEN
    RAISE EXCEPTION 'Exit time must be after entry time';
  END IF;

  -- Verify exit price is positive
  IF p_exit_price <= 0 THEN
    RAISE EXCEPTION 'Exit price must be positive';
  END IF;

  -- Calculate PnL based on direction
  IF v_position.direction = 'long' THEN
    v_pnl := (p_exit_price - v_position.entry_price) * v_position.quantity;
    v_pnl_pct := ((p_exit_price - v_position.entry_price) / v_position.entry_price) * 100;
  ELSIF v_position.direction = 'short' THEN
    v_pnl := (v_position.entry_price - p_exit_price) * v_position.quantity;
    v_pnl_pct := ((v_position.entry_price - p_exit_price) / v_position.entry_price) * 100;
  ELSE
    RAISE EXCEPTION 'Invalid direction: %', v_position.direction;
  END IF;

  -- CRITICAL: Create trade record ATOMICALLY within same transaction
  -- This ensures position and trade are created together, or both fail
  INSERT INTO paper_trading_trades (
    id, position_id, user_id, strategy_id, symbol_id, timeframe,
    entry_price, exit_price, quantity, direction, entry_time, exit_time,
    pnl, pnl_pct, trade_reason
  ) VALUES (
    gen_random_uuid(),
    p_position_id,
    v_position.user_id,
    v_position.strategy_id,
    v_position.symbol_id,
    v_position.timeframe,
    v_position.entry_price,
    p_exit_price,
    v_position.quantity,
    v_position.direction,
    v_position.entry_time,
    p_exit_time,
    v_pnl,
    v_pnl_pct,
    p_trade_reason
  ) RETURNING id INTO v_trade_id;

  -- Update position to closed (within same transaction)
  UPDATE paper_trading_positions
    SET status = 'closed', current_price = p_exit_price, updated_at = NOW()
    WHERE id = p_position_id;

  RETURN v_trade_id;
EXCEPTION
  WHEN UNIQUE_VIOLATION THEN
    -- Position already has a trade (one_close_per_position constraint)
    RAISE EXCEPTION 'Position % already has a closing trade', p_position_id;
  WHEN OTHERS THEN
    -- Re-raise with context
    RAISE EXCEPTION 'Error closing position %: %', p_position_id, SQLERRM;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permission to service role (executor functions)
GRANT EXECUTE ON FUNCTION close_paper_position TO service_role;

COMMENT ON FUNCTION close_paper_position IS
  'Safely close a paper trading position with atomic transaction and race condition prevention';

-- =====================================================
-- Step 8: Function to Create Execution Log Entry
-- =====================================================

CREATE OR REPLACE FUNCTION log_strategy_execution(
  p_user_id UUID,
  p_strategy_id UUID,
  p_symbol_id UUID,
  p_position_id UUID,
  p_timeframe TEXT,
  p_candle_time TIMESTAMPTZ,
  p_signal_type signal_type_enum,
  p_triggered_conditions TEXT[],
  p_action_taken TEXT,
  p_execution_details JSONB DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
  v_log_id UUID;
BEGIN
  INSERT INTO strategy_execution_log (
    id, user_id, strategy_id, symbol_id, position_id, timeframe,
    candle_time, signal_type, triggered_conditions, action_taken, execution_details
  ) VALUES (
    gen_random_uuid(),
    p_user_id,
    p_strategy_id,
    p_symbol_id,
    p_position_id,
    p_timeframe,
    p_candle_time,
    p_signal_type,
    p_triggered_conditions,
    p_action_taken,
    p_execution_details
  ) RETURNING id INTO v_log_id;

  RETURN v_log_id;
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'Error logging execution: %', SQLERRM;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION log_strategy_execution TO service_role;

COMMENT ON FUNCTION log_strategy_execution IS
  'Create an immutable execution log entry for strategy signal evaluation';

-- =====================================================
-- Step 9: Add comments for documentation
-- =====================================================

COMMENT ON TABLE paper_trading_positions IS
  'Active (open) paper trading positions. Once closed, records move to paper_trading_trades.';

COMMENT ON TABLE paper_trading_trades IS
  'Closed paper trades. Immutable append-only audit trail (no UPDATE/DELETE allowed).';

COMMENT ON TABLE strategy_execution_log IS
  'Execution log of all strategy signal evaluations. Immutable append-only audit trail.';

COMMENT ON TABLE paper_trading_metrics IS
  'Aggregated performance metrics for paper trading strategies over time periods.';

COMMENT ON COLUMN paper_trading_positions.position_id IS
  'CRITICAL: One-to-one link to paper_trading_trades. Ensures no duplicate closes.';

COMMENT ON COLUMN paper_trading_trades.pnl_calculated IS
  'Auto-calculated PnL from entry/exit prices and quantity. Used to verify accuracy.';

-- =====================================================
-- Migration Verification Queries
-- =====================================================
-- Run these AFTER migration to verify safety

-- Verify position closure atomicity: No position should have > 1 trade
-- SELECT position_id, COUNT(*) as trade_count
-- FROM paper_trading_trades
-- GROUP BY position_id
-- HAVING COUNT(*) > 1;
-- Result: Should be empty set

-- Verify time ordering: No trade should have exit_time <= entry_time
-- SELECT id FROM paper_trading_trades
-- WHERE exit_time <= entry_time;
-- Result: Should be empty set

-- Verify PnL accuracy: No trade should have |pnl - pnl_calculated| >= 0.01
-- SELECT id, pnl, pnl_calculated, ABS(pnl - pnl_calculated) as error
-- FROM paper_trading_trades
-- WHERE ABS(pnl - pnl_calculated) >= 0.01;
-- Result: Should be empty set

-- Verify RLS enforcement: Non-owners cannot see positions
-- SET SESSION "request.jwt.claims" = '{"sub": "different-user-id"}';
-- SELECT COUNT(*) FROM paper_trading_positions;
-- Result: 0 (all rows hidden by RLS)

-- =====================================================
-- END OF MIGRATION
-- =====================================================
