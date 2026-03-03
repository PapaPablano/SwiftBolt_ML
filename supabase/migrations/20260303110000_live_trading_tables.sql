-- Live Trading Tables — Positions, trades, and strategy config for real execution
-- Migration: 20260303110000_live_trading_tables
-- Date: 2026-03-03
-- Feature: Live Trading Executor via TradeStation

-- ============================================================================
-- 1. ADD LIVE TRADING COLUMNS TO STRATEGIES
-- ============================================================================
ALTER TABLE strategy_user_strategies
  ADD COLUMN IF NOT EXISTS live_trading_enabled      BOOLEAN      DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS live_risk_pct             DECIMAL(5,4) DEFAULT 0.02
    CHECK (live_risk_pct > 0 AND live_risk_pct <= 0.10),
  ADD COLUMN IF NOT EXISTS live_daily_loss_limit_pct DECIMAL(5,4) DEFAULT 0.05
    CHECK (live_daily_loss_limit_pct > 0 AND live_daily_loss_limit_pct <= 0.20),
  ADD COLUMN IF NOT EXISTS live_max_positions        INT          DEFAULT 5
    CHECK (live_max_positions > 0 AND live_max_positions <= 20),
  ADD COLUMN IF NOT EXISTS live_max_position_pct     DECIMAL(5,4) DEFAULT 0.02
    CHECK (live_max_position_pct > 0 AND live_max_position_pct <= 0.10),
  ADD COLUMN IF NOT EXISTS live_trading_paused       BOOLEAN      DEFAULT FALSE;

-- ============================================================================
-- 2. LIVE TRADING POSITIONS
-- ============================================================================
-- Mirrors paper_trading_positions with added broker columns.
-- Status includes pending_bracket for the dangerous window between
-- entry fill and bracket placement (P1 #085).

CREATE TABLE IF NOT EXISTS live_trading_positions (
  id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id          UUID         NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id            UUID         NOT NULL,
  timeframe            TEXT         NOT NULL,
  entry_price          DECIMAL(12,4) NOT NULL CHECK (entry_price > 0),
  current_price        DECIMAL(12,4),
  quantity             INT          NOT NULL CHECK (quantity > 0 AND quantity <= 10000),
  entry_time           TIMESTAMPTZ  NOT NULL,
  direction            TEXT         NOT NULL CHECK (direction IN ('long', 'short')),
  stop_loss_price      DECIMAL(12,4) NOT NULL CHECK (stop_loss_price > 0),
  take_profit_price    DECIMAL(12,4) NOT NULL CHECK (take_profit_price > 0),
  status               TEXT         NOT NULL DEFAULT 'pending_entry'
                         CHECK (status IN (
                           'pending_entry',
                           'pending_bracket',
                           'open',
                           'pending_close',
                           'closed',
                           'cancelled'
                         )),
  broker_order_id      TEXT,
  broker_sl_order_id   TEXT,
  broker_tp_order_id   TEXT,
  account_id           TEXT         NOT NULL,
  asset_type           TEXT         NOT NULL DEFAULT 'STOCK'
                         CHECK (asset_type IN ('STOCK', 'FUTURE')),
  contract_multiplier  DECIMAL(12,4) DEFAULT 1.0 CHECK (contract_multiplier > 0),
  pnl                  DECIMAL(12,4),
  close_reason         TEXT CHECK (close_reason IN (
                         'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
                         'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
                         'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED'
                       )),
  exit_time            TIMESTAMPTZ,
  exit_price           DECIMAL(12,4),
  order_submitted_at   TIMESTAMPTZ,
  execution_venue      TEXT         NOT NULL DEFAULT 'tradestation',
  order_type           TEXT         NOT NULL DEFAULT 'market'
                         CHECK (order_type IN ('market', 'limit', 'bracket')),
  broker_fill_price    DECIMAL(12,4),
  created_at           TIMESTAMPTZ  DEFAULT NOW(),
  updated_at           TIMESTAMPTZ  DEFAULT NOW(),

  -- SL/TP ordering constraint based on direction
  CONSTRAINT live_position_levels CHECK (
    (direction = 'long'  AND stop_loss_price < entry_price AND entry_price < take_profit_price) OR
    (direction = 'short' AND take_profit_price < entry_price AND entry_price < stop_loss_price)
  ),

  -- Temporal ordering: exit must be after entry
  CONSTRAINT live_exit_after_entry CHECK (
    exit_time IS NULL OR exit_time > entry_time
  )
);

-- Prevent duplicate active positions (P1 #088: TOCTOU double-entry prevention)
CREATE UNIQUE INDEX IF NOT EXISTS idx_live_positions_active_unique
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');

-- Query indexes
CREATE INDEX IF NOT EXISTS idx_live_positions_user_strategy
  ON live_trading_positions (user_id, strategy_id, symbol_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_live_positions_status
  ON live_trading_positions (status, user_id);

CREATE INDEX IF NOT EXISTS idx_live_positions_broker_order
  ON live_trading_positions (broker_order_id) WHERE broker_order_id IS NOT NULL;

-- Daily loss query index (for circuit breaker)
CREATE INDEX IF NOT EXISTS idx_live_positions_daily_loss
  ON live_trading_positions (user_id, exit_time DESC)
  WHERE status = 'closed';

-- ============================================================================
-- 3. RLS FOR LIVE POSITIONS
-- ============================================================================
ALTER TABLE live_trading_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "live_positions_user_select" ON live_trading_positions
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "live_positions_user_insert" ON live_trading_positions
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "live_positions_user_update" ON live_trading_positions
  FOR UPDATE USING (auth.uid() = user_id);

-- No DELETE policy — positions are closed, not deleted.

-- ============================================================================
-- 4. LIVE TRADING TRADES (IMMUTABLE AUDIT TRAIL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS live_trading_trades (
  id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID         NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
  strategy_id       UUID         NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  position_id       UUID         NOT NULL REFERENCES live_trading_positions(id),
  symbol            TEXT         NOT NULL,
  direction         TEXT         NOT NULL CHECK (direction IN ('long', 'short')),
  entry_price       DECIMAL(12,4) NOT NULL,
  exit_price        DECIMAL(12,4) NOT NULL,
  quantity          INT          NOT NULL,
  pnl               DECIMAL(12,4) NOT NULL,
  pnl_pct           DECIMAL(8,4),
  close_reason      TEXT         NOT NULL,
  broker_order_id   TEXT,
  entry_time        TIMESTAMPTZ  NOT NULL,
  exit_time         TIMESTAMPTZ  NOT NULL CHECK (exit_time > entry_time),
  order_submitted_at TIMESTAMPTZ,
  execution_venue   TEXT         NOT NULL DEFAULT 'tradestation',
  broker_fill_price DECIMAL(12,4),
  contract_multiplier DECIMAL(12,4) DEFAULT 1.0,
  asset_type        TEXT         DEFAULT 'STOCK',
  created_at        TIMESTAMPTZ  DEFAULT NOW()
);

-- Indices for historical queries
CREATE INDEX IF NOT EXISTS idx_live_trades_user_strategy
  ON live_trading_trades (user_id, strategy_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_live_trades_user_date
  ON live_trading_trades (user_id, exit_time DESC);

-- ============================================================================
-- 5. IMMUTABILITY TRIGGER
-- ============================================================================
-- Prevent UPDATE and DELETE on live_trading_trades (financial audit trail).

CREATE OR REPLACE FUNCTION prevent_live_trade_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'live_trading_trades records are immutable';
END;
$$;

CREATE TRIGGER live_trades_immutable_row
  BEFORE UPDATE OR DELETE ON live_trading_trades
  FOR EACH ROW EXECUTE FUNCTION prevent_live_trade_mutation();

-- Also block TRUNCATE (P2 #100: statement-level gap)
CREATE OR REPLACE FUNCTION prevent_live_trade_truncate()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'TRUNCATE on live_trading_trades is not allowed';
END;
$$;

CREATE TRIGGER live_trades_no_truncate
  BEFORE TRUNCATE ON live_trading_trades
  EXECUTE FUNCTION prevent_live_trade_truncate();

-- ============================================================================
-- 6. RLS FOR LIVE TRADES
-- ============================================================================
ALTER TABLE live_trading_trades ENABLE ROW LEVEL SECURITY;

CREATE POLICY "live_trades_user_select" ON live_trading_trades
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "live_trades_user_insert" ON live_trading_trades
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Explicit deny UPDATE/DELETE via RLS (belt-and-suspenders with trigger)
CREATE POLICY "live_trades_no_update" ON live_trading_trades
  FOR UPDATE USING (FALSE);

CREATE POLICY "live_trades_no_delete" ON live_trading_trades
  FOR DELETE USING (FALSE);
