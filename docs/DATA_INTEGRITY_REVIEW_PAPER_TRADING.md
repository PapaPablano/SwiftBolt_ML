# Data Integrity Review: Paper Trading Schema

**Reviewer:** Data Integrity Guardian
**Date:** 2026-02-25
**Status:** Critical Issues Identified
**Severity:** HIGH

---

## Executive Summary

The proposed paper trading schema introduces **4 critical data integrity risks** and **11 medium-risk issues** that must be addressed before production deployment. The primary concerns are:

1. **Race conditions** on position transitions (concurrent updates causing phantom trades)
2. **Incomplete transaction boundaries** (partial failures orphaning positions)
3. **Missing audit trail enforcement** (ability to modify/delete closed trades)
4. **Referential integrity gaps** (dangling records after cascade deletes)
5. **Missing constraints** on PnL calculations (allowing nonsensical values)

This review provides specific remediation strategies with migration safety guidelines.

---

## Table 1: `paper_trading_positions` - Critical Issues

### Issue 1.1: CRITICAL - Race Condition on Position Status Transitions

**Problem:** Multiple concurrent processes can see the same position as "open", both attempting to close it.

```sql
-- Current vulnerable sequence (Race Condition)
-- Process A (SL Hit)              Process B (Exit Signal)
SELECT * FROM paper_trading_positions
  WHERE strategy_id = $1 AND status = 'open'
                            SELECT * FROM paper_trading_positions
                              WHERE strategy_id = $1 AND status = 'open'

-- Both see same position, both try to close
UPDATE paper_trading_positions SET status = 'closed' WHERE id = $pos_id
                            UPDATE paper_trading_positions SET status = 'closed' WHERE id = $pos_id
                            -- One succeeds, one silently fails

-- Result: Trade recorded at SL price AND exit signal price (phantom trade)
```

**Impact:** HIGH
- Two trades created from one position
- P&L misstated (double counting profit/loss)
- Dashboard shows duplicate exits
- Regulatory audit trail corrupted

**Mitigation Strategy:**

```sql
-- Use advisory locks for atomic state transitions
-- Option A: Pessimistic Lock (PostgreSQL FOR UPDATE)

BEGIN TRANSACTION;
  -- Lock row exclusively until transaction ends
  SELECT id, status, stop_loss_price, take_profit_price
  FROM paper_trading_positions
  WHERE id = $pos_id
  FOR UPDATE;  -- CRITICAL: Blocks concurrent reads/writes

  -- Check conditions (now guaranteed no concurrent update)
  IF (check_sl_hit OR check_tp_hit OR check_exit_signal) THEN
    UPDATE paper_trading_positions
    SET status = 'closed', updated_at = NOW()
    WHERE id = $pos_id;

    INSERT INTO paper_trading_trades (...) VALUES (...);
  END IF;
COMMIT;

-- Option B: Database-Level Constraint (Recommended)
-- Add NOT NULL position_id to paper_trading_trades with foreign key
-- Each position can have at most ONE closed trade record
-- This prevents application-level bugs from creating duplicates
```

**Recommended Fix:**

Add constraint to prevent duplicate trades per position:

```sql
ALTER TABLE paper_trading_trades
  ADD COLUMN position_id UUID REFERENCES paper_trading_positions(id);

ALTER TABLE paper_trading_trades
  ADD CONSTRAINT one_close_per_position UNIQUE (position_id);
```

---

### Issue 1.2: HIGH - Missing Transaction Boundaries (Partial Failure)

**Problem:** Entry transaction not atomic—position created but entry_price fails to update.

```sql
-- Current vulnerable code (IMPLIED from schema)
INSERT INTO paper_trading_positions (...) VALUES (...);
-- Network failure here?

UPDATE paper_trading_positions
SET entry_price = calculated_entry_price
WHERE id = $pos_id;
-- If this fails, position stuck with NULL entry_price
```

**Impact:** HIGH
- Positions in invalid state (entry_price = NULL)
- Cannot calculate P&L
- Manual intervention required
- Unknown number of affected trades

**Mitigation Strategy:**

Enforce NOT NULL constraint and require atomic insert:

```sql
-- Migration to add NOT NULL constraint
ALTER TABLE paper_trading_positions
  ALTER COLUMN entry_price SET NOT NULL;

-- Code MUST insert with all required fields in single statement
INSERT INTO paper_trading_positions (
  id, user_id, strategy_id, symbol_id, timeframe,
  entry_price,  -- MUST be provided, not updated later
  current_price, quantity, entry_time, direction,
  stop_loss_price, take_profit_price, status,
  created_at, updated_at
) VALUES (
  gen_random_uuid(),
  $user_id,
  $strategy_id,
  $symbol_id,
  $timeframe,
  $entry_price,  -- Calculated and passed in, not NULL
  $entry_price,  -- current_price = entry_price at open
  $quantity,
  NOW(),
  $direction,
  $sl_price,
  $tp_price,
  'open',
  NOW(),
  NOW()
);
```

---

### Issue 1.3: HIGH - Missing Constraint: Quantity Must Be Positive

**Problem:** Schema allows negative quantities, resulting in nonsensical positions.

```sql
-- Current allows this (wrong):
INSERT INTO paper_trading_positions (quantity) VALUES (-100);
-- Position is now "short 100", but could have been typo
-- No audit trail of intent
```

**Impact:** MEDIUM
- Confusing position semantics (negative qty = short?)
- Break even calculations fail
- Backtest vs paper comparison confused

**Mitigation Strategy:**

```sql
ALTER TABLE paper_trading_positions
  ADD CONSTRAINT qty_must_be_positive CHECK (quantity > 0);
```

---

### Issue 1.4: HIGH - Missing Constraint: Price Relationships

**Problem:** Stop loss can be above entry (long), take profit below entry—nonsensical.

```sql
-- Current allows this (wrong):
INSERT INTO paper_trading_positions (
  entry_price = 100,
  stop_loss_price = 105,     -- Long with SL above entry?
  take_profit_price = 95,    -- TP below entry?
  direction = 'long'
) VALUES (...);
```

**Impact:** MEDIUM
- Immediate SL/TP hit on entry (trades close instantly)
- Risk management defeated
- Execution logic breaks

**Mitigation Strategy:**

```sql
-- Add constraints based on direction
ALTER TABLE paper_trading_positions
  ADD CONSTRAINT sl_tp_long CHECK (
    CASE
      WHEN direction = 'long' THEN
        (stop_loss_price IS NULL OR stop_loss_price < entry_price) AND
        (take_profit_price IS NULL OR take_profit_price > entry_price)
      WHEN direction = 'short' THEN
        (stop_loss_price IS NULL OR stop_loss_price > entry_price) AND
        (take_profit_price IS NULL OR take_profit_price < entry_price)
      ELSE TRUE
    END
  );
```

---

### Issue 1.5: MEDIUM - Missing Constraint: Direction Enum

**Problem:** `direction TEXT NOT NULL CHECK (direction IN ('long', 'short'))` is weak—app can pass 'LONG' or 'Long'.

**Impact:** LOW (just case sensitivity)
- Filtering by direction fails
- Enum type safer

**Mitigation Strategy:**

```sql
-- Create ENUM type
CREATE TYPE position_direction AS ENUM ('long', 'short');

-- Migrate data
ALTER TABLE paper_trading_positions
  ALTER COLUMN direction TYPE position_direction USING direction::position_direction;
```

---

### Issue 1.6: MEDIUM - Missing Index: Queries for Open Positions

**Problem:** No index on (user_id, strategy_id, status).

```sql
-- This query runs FULL TABLE SCAN without index
SELECT * FROM paper_trading_positions
WHERE user_id = $user_id
AND strategy_id = $strategy_id
AND status = 'open';
```

**Impact:** MEDIUM
- At 10k positions, query takes 100ms+
- Dashboard latency
- Paper trading executor slow at scale

**Mitigation Strategy:**

```sql
CREATE INDEX idx_paper_positions_user_strategy_status
  ON paper_trading_positions(user_id, strategy_id, status DESC)
  WHERE status = 'open';  -- Partial index (fast)
```

---

## Table 2: `paper_trading_trades` - Critical Issues

### Issue 2.1: CRITICAL - Immutability Not Enforced (Data Tampering Risk)

**Problem:** Schema allows UPDATE/DELETE on closed trades. Analyst can modify P&L after closing.

```sql
-- Current vulnerability:
UPDATE paper_trading_trades
SET pnl = 50000,  -- Modified after execution!
    pnl_pct = 100.0
WHERE id = $trade_id;

DELETE FROM paper_trading_trades WHERE exit_time < NOW() - INTERVAL '30 days';
-- Erased trade history
```

**Impact:** CRITICAL
- Audit trail destroyed
- P&L metrics unreliable
- Regulatory/compliance issue
- Cannot trust backtest vs paper comparison

**Mitigation Strategy:**

Implement append-only pattern with RLS:

```sql
-- Disable UPDATE/DELETE via RLS
CREATE POLICY "paper_trades_immutable_delete"
  ON paper_trading_trades FOR DELETE
  USING (FALSE);  -- Block all deletes

CREATE POLICY "paper_trades_immutable_update"
  ON paper_trading_trades FOR UPDATE
  USING (FALSE);  -- Block all updates

-- Only service_role can insert (via executor function)
CREATE POLICY "paper_trades_insert_service"
  ON paper_trading_trades FOR INSERT
  TO service_role
  WITH CHECK (TRUE);

-- Users can read
CREATE POLICY "paper_trades_select_own"
  ON paper_trading_trades FOR SELECT
  USING (auth.uid() = user_id);
```

---

### Issue 2.2: HIGH - PnL Calculation Constraints Missing

**Problem:** No constraints on pnl/pnl_pct relationship. Can insert nonsensical values.

```sql
-- Current allows this (wrong):
INSERT INTO paper_trading_trades (
  entry_price = 100,
  exit_price = 100,
  quantity = 10,
  direction = 'long',
  pnl = 50000,          -- $5000 P&L from no price movement!
  pnl_pct = 50.0        -- 50% return from zero move?
) VALUES (...);
```

**Impact:** MEDIUM
- Metrics unreliable
- Dashboard shows false performance
- Strategy comparison meaningless

**Mitigation Strategy:**

```sql
-- Calculated column (PostgreSQL 12+) with CHECK constraint
ALTER TABLE paper_trading_trades
  ADD COLUMN pnl_calculated DECIMAL GENERATED ALWAYS AS (
    CASE
      WHEN direction = 'long' THEN (exit_price - entry_price) * quantity
      WHEN direction = 'short' THEN (entry_price - exit_price) * quantity
      ELSE 0
    END
  ) STORED;

-- Verify submitted pnl matches calculated
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT pnl_matches_calculation CHECK (
    ABS(pnl - pnl_calculated) < 0.01  -- Allow rounding error
  );

-- Similar for pnl_pct
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT pnl_pct_valid CHECK (
    pnl_pct >= -100.0 AND pnl_pct <= 10000.0  -- Reasonable bounds
  );
```

---

### Issue 2.3: HIGH - Missing Constraint: Time Sequence

**Problem:** exit_time can be before entry_time.

```sql
-- Current allows this (wrong):
INSERT INTO paper_trading_trades (
  entry_time = '2026-02-25 15:00:00',
  exit_time = '2026-02-25 14:00:00',  -- Closed before opened!
) VALUES (...);
```

**Impact:** MEDIUM
- Nonsensical trade duration
- Filters like "trades from last 7 days" broken
- Dashboard shows impossible data

**Mitigation Strategy:**

```sql
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT exit_after_entry CHECK (exit_time > entry_time);
```

---

### Issue 2.4: MEDIUM - Missing Constraint: Status Enum

**Problem:** status TEXT, not an ENUM. Allows typos like 'CLOSED', 'Closed', 'closed '.

**Impact:** LOW
- Filtering by status fails
- Enum safer

**Mitigation Strategy:**

```sql
CREATE TYPE trade_reason AS ENUM ('TP_HIT', 'SL_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE');

ALTER TABLE paper_trading_trades
  ALTER COLUMN trade_reason TYPE trade_reason USING trade_reason::trade_reason;
```

---

### Issue 2.5: MEDIUM - Missing Index: Queries for Recent Trades

**Problem:** No index for historical trade queries.

```sql
-- This query runs FULL TABLE SCAN
SELECT * FROM paper_trading_trades
WHERE user_id = $user_id
AND exit_time > NOW() - INTERVAL '7 days'
ORDER BY exit_time DESC;
```

**Impact:** MEDIUM
- Dashboard slow on large trade history
- Pagination inefficient

**Mitigation Strategy:**

```sql
CREATE INDEX idx_paper_trades_user_exit_time
  ON paper_trading_trades(user_id, exit_time DESC);
```

---

### Issue 2.6: MEDIUM - Missing Referential Integrity

**Problem:** No foreign key link to `paper_trading_positions`. If position deleted, trade orphaned.

```sql
-- Currently:
REFERENCES strategy_user_strategies(id)  -- ✓ Good
REFERENCES symbols(id)                   -- ✓ Good
-- Missing:
REFERENCES paper_trading_positions(id)   -- ✗ Orphan risk
```

**Impact:** MEDIUM
- Orphaned trades if position accidentally deleted
- Cannot query position details from trade
- Audit trail incomplete

**Mitigation Strategy:**

```sql
-- Add foreign key (already recommended in Issue 1.1)
ALTER TABLE paper_trading_trades
  ADD COLUMN position_id UUID NOT NULL
  REFERENCES paper_trading_positions(id) ON DELETE RESTRICT;
  -- ON DELETE RESTRICT prevents position deletion while trade exists

-- Create index for JOIN queries
CREATE INDEX idx_paper_trades_position_id
  ON paper_trading_trades(position_id);
```

---

## Table 3: `strategy_execution_log` - Issues

### Issue 3.1: HIGH - Immutability Not Enforced

**Problem:** Execution log allows DELETE/UPDATE. Should be append-only audit trail.

**Impact:** HIGH
- Audit trail can be tampered with
- Regulatory issue
- Cannot debug when/why signal triggered

**Mitigation Strategy:**

```sql
-- Same append-only pattern as paper_trading_trades
CREATE POLICY "execution_log_immutable_delete"
  ON strategy_execution_log FOR DELETE
  USING (FALSE);

CREATE POLICY "execution_log_immutable_update"
  ON strategy_execution_log FOR UPDATE
  USING (FALSE);

-- Only service_role (executor) can insert
CREATE POLICY "execution_log_insert_service"
  ON strategy_execution_log FOR INSERT
  TO service_role
  WITH CHECK (TRUE);

-- Users can read their own
CREATE POLICY "execution_log_select_own"
  ON strategy_execution_log FOR SELECT
  USING (auth.uid() = user_id);
```

---

### Issue 3.2: HIGH - Missing Constraint: Signal Type Enum

**Problem:** signal_type TEXT NOT NULL CHECK (...) is weak.

**Impact:** LOW
- Case sensitivity issues
- Enum safer

**Mitigation Strategy:**

```sql
CREATE TYPE signal_type AS ENUM ('entry', 'exit', 'condition_met');

ALTER TABLE strategy_execution_log
  ALTER COLUMN signal_type TYPE signal_type USING signal_type::signal_type;
```

---

### Issue 3.3: MEDIUM - Missing Index: Queries by Strategy and Time

**Problem:** No index for fetching execution log for a strategy.

**Impact:** MEDIUM
- Dashboard fetch slow
- Debugging slow

**Mitigation Strategy:**

```sql
CREATE INDEX idx_execution_log_strategy_time
  ON strategy_execution_log(strategy_id, candle_time DESC);
```

---

### Issue 3.4: MEDIUM - Missing Constraint: Timestamp Ordering

**Problem:** candle_time can be in future.

**Impact:** LOW
- Debug logs show impossible data
- Should not be future-dated

**Mitigation Strategy:**

```sql
ALTER TABLE strategy_execution_log
  ADD CONSTRAINT candle_time_not_future CHECK (candle_time <= NOW());
```

---

## Table 4: `paper_trading_metrics` - Issues

### Issue 4.1: HIGH - Calculated Metrics Not Verified

**Problem:** All metrics (win_rate, sharpe_ratio, etc.) are freely writeable. No constraint that they're accurate.

```sql
-- Current allows:
INSERT INTO paper_trading_metrics (
  win_rate = 95.0,      -- Claim 95% win rate
  sharpe_ratio = 100.0, -- Claim 100 Sharpe (impossible)
  max_drawdown = 0.1    -- Claim no drawdown
) VALUES (...);
-- But what if only 1 trade? win_rate meaningless
-- What if only 2 wins, 0 losses? 100% but with no data
```

**Impact:** HIGH
- Metrics unreliable
- Dashboard shows false performance
- Strategy comparison broken

**Mitigation Strategy:**

Option A (Strict): Calculated column

```sql
-- Drop all manually-written metric columns
-- Replace with MATERIALIZED VIEW that computes from paper_trading_trades

CREATE MATERIALIZED VIEW paper_trading_metrics_view AS
SELECT
  user_id,
  strategy_id,
  symbol_id,
  timeframe,
  period_start,
  period_end,
  COUNT(*) as trades_count,
  SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_count,
  SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as loss_count,
  AVG(CASE WHEN pnl > 0 THEN pnl ELSE NULL END) as avg_win,
  AVG(CASE WHEN pnl <= 0 THEN pnl ELSE NULL END) as avg_loss,
  (SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*)) * 100 as win_rate,
  -- ... more calculated fields
FROM paper_trading_trades
WHERE exit_time BETWEEN period_start AND period_end
GROUP BY user_id, strategy_id, symbol_id, timeframe, period_start, period_end;

-- Refresh periodically (via cron)
-- Users query the view, not the table
```

Option B (Pragmatic): Validation in application

- Executor function MUST calculate metrics, not accept user input
- Only service_role can INSERT
- Trigger validates on INSERT

---

### Issue 4.2: HIGH - Period Boundaries Can Overlap

**Problem:** Two metric records can cover same period for same strategy/symbol.

```sql
-- Current allows:
INSERT INTO paper_trading_metrics (period_start = '2026-02-01', period_end = '2026-02-07') ...;
INSERT INTO paper_trading_metrics (period_start = '2026-02-01', period_end = '2026-02-07') ...;
-- Duplicate metrics for same period
```

**Impact:** MEDIUM
- Dashboard shows multiple conflicting values
- Unclear which is correct

**Mitigation Strategy:**

```sql
-- Add unique constraint on period + strategy
ALTER TABLE paper_trading_metrics
  ADD CONSTRAINT unique_metric_period UNIQUE (
    user_id, strategy_id, symbol_id, timeframe,
    period_start, period_end
  );
```

---

### Issue 4.3: MEDIUM - Missing Index: Fetch for Dashboard

**Problem:** No index on (user_id, period_start DESC).

**Impact:** MEDIUM
- Dashboard query slow

**Mitigation Strategy:**

```sql
CREATE INDEX idx_paper_metrics_user_period
  ON paper_trading_metrics(user_id, period_start DESC);
```

---

## Cascading Delete Risks

### Issue 5.1: CRITICAL - Position Cascades to Trades, Breaking Referential Integrity

**Problem:** If position deleted, cascade could orphan strategy_execution_log records.

```sql
-- If paper_trading_positions has ON DELETE CASCADE to paper_trading_trades:
DELETE FROM paper_trading_positions WHERE id = $pos_id;
-- → Cascades to paper_trading_trades, deleting all evidence of trade
-- → But strategy_execution_log still references this position
-- → Orphaned log entries (inconsistent)
```

**Impact:** HIGH
- Audit trail inconsistent
- Data integrity broken

**Mitigation Strategy:**

```sql
-- Use ON DELETE RESTRICT instead of CASCADE
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT fk_trades_position
  FOREIGN KEY (position_id) REFERENCES paper_trading_positions(id)
  ON DELETE RESTRICT;
  -- Prevents position deletion if trades reference it
  -- Forces explicit cleanup

-- Similar for execution_log:
ALTER TABLE strategy_execution_log
  ADD CONSTRAINT fk_execution_log_position
  FOREIGN KEY (position_id) REFERENCES paper_trading_positions(id)
  ON DELETE RESTRICT;
```

---

## Row-Level Security (RLS) Gaps

### Issue 6.1: HIGH - Paper Trading Tables Missing RLS Policies

**Problem:** Plan doesn't specify RLS. Without it, users can see each other's paper trades.

**Impact:** CRITICAL
- Privacy violation (user A sees user B's strategies)
- Regulatory issue
- Untrustworthy system

**Mitigation Strategy:**

```sql
-- Enable RLS on all paper trading tables
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trading_metrics ENABLE ROW LEVEL SECURITY;

-- paper_trading_positions: users can only see their own
CREATE POLICY "positions_select_own" ON paper_trading_positions
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "positions_insert_own" ON paper_trading_positions
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "positions_update_own" ON paper_trading_positions
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- paper_trading_trades: users can only see their own
CREATE POLICY "trades_select_own" ON paper_trading_trades
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "trades_insert_own" ON paper_trading_trades
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- strategy_execution_log: users can only see their own
CREATE POLICY "execution_log_select_own" ON strategy_execution_log
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "execution_log_insert_service" ON strategy_execution_log
  FOR INSERT TO service_role
  USING (TRUE);  -- Service role (executor) can insert for any user

-- paper_trading_metrics: users can only see their own
CREATE POLICY "metrics_select_own" ON paper_trading_metrics
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);
```

---

## Migration Safety Considerations

### Issue 7.1: Schema Changes on Large Tables

**Risk:** If adding NOT NULL columns to `paper_trading_trades` with millions of rows:

```sql
-- SLOW: Full table rewrite
ALTER TABLE paper_trading_trades
  ADD COLUMN position_id UUID NOT NULL;
-- → Locks table during migration, blocking reads/writes
```

**Mitigation:**

```sql
-- Migration in phases:

-- Phase 1: Add nullable column
ALTER TABLE paper_trading_trades
  ADD COLUMN position_id UUID;

-- Phase 2: Backfill (with application code)
-- Query existing positions, link trades to positions by symbol+entry_time match

-- Phase 3: Add constraint
ALTER TABLE paper_trading_trades
  ALTER COLUMN position_id SET NOT NULL;

-- Phase 4: Verify no NULLs remain (CHECK)
-- Then add foreign key
ALTER TABLE paper_trading_trades
  ADD CONSTRAINT fk_position_id
  FOREIGN KEY (position_id) REFERENCES paper_trading_positions(id);
```

---

## Recommended Complete Safe Migration

```sql
-- =====================================================
-- MIGRATION: 20260225000000_paper_trading_safe_schema.sql
-- =====================================================

-- Step 1: Create ENUM types first
CREATE TYPE position_direction AS ENUM ('long', 'short');
CREATE TYPE trade_exit_reason AS ENUM ('TP_HIT', 'SL_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE');
CREATE TYPE signal_type_enum AS ENUM ('entry', 'exit', 'condition_met');

-- Step 2: Create paper_trading_positions with all constraints
CREATE TABLE paper_trading_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL(20, 8) NOT NULL CHECK (entry_price > 0),
  current_price DECIMAL(20, 8),
  quantity INT NOT NULL CHECK (quantity > 0),
  entry_time TIMESTAMPTZ NOT NULL CHECK (entry_time <= NOW()),
  direction position_direction NOT NULL,
  stop_loss_price DECIMAL(20, 8),
  take_profit_price DECIMAL(20, 8),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Validate SL/TP relationships
  CONSTRAINT valid_sl_tp CHECK (
    CASE
      WHEN direction = 'long' THEN
        (stop_loss_price IS NULL OR stop_loss_price < entry_price) AND
        (take_profit_price IS NULL OR take_profit_price > entry_price)
      WHEN direction = 'short' THEN
        (stop_loss_price IS NULL OR stop_loss_price > entry_price) AND
        (take_profit_price IS NULL OR take_profit_price < entry_price)
    END
  )
);

-- Indices
CREATE INDEX idx_positions_user_strategy_status
  ON paper_trading_positions(user_id, strategy_id, status) WHERE status = 'open';
CREATE INDEX idx_positions_symbol_timeframe
  ON paper_trading_positions(symbol_id, timeframe, entry_time DESC);

-- RLS
ALTER TABLE paper_trading_positions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "select_own_positions" ON paper_trading_positions
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "insert_own_positions" ON paper_trading_positions
  FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "update_own_positions" ON paper_trading_positions
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Step 3: Create paper_trading_trades with all constraints
CREATE TABLE paper_trading_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  position_id UUID NOT NULL UNIQUE REFERENCES paper_trading_positions(id) ON DELETE RESTRICT,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,
  entry_price DECIMAL(20, 8) NOT NULL CHECK (entry_price > 0),
  exit_price DECIMAL(20, 8) NOT NULL CHECK (exit_price > 0),
  quantity INT NOT NULL CHECK (quantity > 0),
  direction position_direction NOT NULL,
  entry_time TIMESTAMPTZ NOT NULL CHECK (entry_time <= NOW()),
  exit_time TIMESTAMPTZ NOT NULL CHECK (exit_time > entry_time),
  pnl DECIMAL(20, 8) NOT NULL,
  pnl_pct DECIMAL(10, 2) NOT NULL CHECK (pnl_pct >= -100 AND pnl_pct <= 100000),
  trade_reason trade_exit_reason NOT NULL,
  pnl_calculated DECIMAL(20, 8) GENERATED ALWAYS AS (
    CASE
      WHEN direction = 'long' THEN (exit_price - entry_price) * quantity
      WHEN direction = 'short' THEN (entry_price - exit_price) * quantity
    END
  ) STORED,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Validate PnL matches calculation (with rounding tolerance)
  CONSTRAINT pnl_accuracy CHECK (ABS(pnl - pnl_calculated) < 0.01)
);

-- Indices
CREATE INDEX idx_trades_user_exit_time
  ON paper_trading_trades(user_id, exit_time DESC);
CREATE INDEX idx_trades_strategy
  ON paper_trading_trades(strategy_id, exit_time DESC);

-- RLS: Immutable (append-only)
ALTER TABLE paper_trading_trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "select_own_trades" ON paper_trading_trades
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "trades_not_deletable" ON paper_trading_trades
  FOR DELETE USING (FALSE);
CREATE POLICY "trades_not_updatable" ON paper_trading_trades
  FOR UPDATE USING (FALSE);

-- Step 4: strategy_execution_log
CREATE TABLE strategy_execution_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  position_id UUID REFERENCES paper_trading_positions(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,
  candle_time TIMESTAMPTZ NOT NULL CHECK (candle_time <= NOW()),
  signal_type signal_type_enum NOT NULL,
  triggered_conditions TEXT[],
  action_taken TEXT NOT NULL,
  execution_details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices
CREATE INDEX idx_execution_log_strategy_time
  ON strategy_execution_log(strategy_id, candle_time DESC);

-- RLS: Immutable (append-only)
ALTER TABLE strategy_execution_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "select_own_log" ON strategy_execution_log
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "log_not_deletable" ON strategy_execution_log
  FOR DELETE USING (FALSE);
CREATE POLICY "log_not_updatable" ON strategy_execution_log
  FOR UPDATE USING (FALSE);

-- Step 5: paper_trading_metrics (use materialized view approach)
CREATE TABLE paper_trading_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
  timeframe TEXT NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL CHECK (period_end > period_start),
  trades_count INT NOT NULL DEFAULT 0 CHECK (trades_count >= 0),
  win_count INT NOT NULL DEFAULT 0 CHECK (win_count >= 0),
  loss_count INT NOT NULL DEFAULT 0 CHECK (loss_count >= 0),
  avg_win DECIMAL(20, 8),
  avg_loss DECIMAL(20, 8),
  win_rate DECIMAL(5, 2) CHECK (win_rate >= 0 AND win_rate <= 100),
  profit_factor DECIMAL(10, 2) CHECK (profit_factor >= 0),
  max_drawdown DECIMAL(10, 4) CHECK (max_drawdown >= 0 AND max_drawdown <= 1),
  total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
  total_pnl_pct DECIMAL(10, 2),
  sharpe_ratio DECIMAL(10, 4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Unique period per strategy
  CONSTRAINT unique_metric_period UNIQUE (
    user_id, strategy_id, symbol_id, timeframe, period_start, period_end
  ),

  -- Ensure win/loss counts match total
  CONSTRAINT counts_add_up CHECK (trades_count = win_count + loss_count)
);

-- Indices
CREATE INDEX idx_metrics_user_period
  ON paper_trading_metrics(user_id, period_start DESC);

-- RLS
ALTER TABLE paper_trading_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "select_own_metrics" ON paper_trading_metrics
  FOR SELECT USING (auth.uid() = user_id);

-- Step 6: Extend strategy_user_strategies for paper trading
ALTER TABLE strategy_user_strategies
  ADD COLUMN paper_trading_enabled BOOLEAN DEFAULT FALSE,
  ADD COLUMN paper_capital DECIMAL(20, 2) DEFAULT 10000 CHECK (paper_capital > 0),
  ADD COLUMN paper_start_date TIMESTAMPTZ,
  ADD COLUMN max_position_hold_time_bars INT DEFAULT 100 CHECK (max_position_hold_time_bars > 0);

-- Step 7: Function to safely transition position to closed (prevents race condition)
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
BEGIN
  -- Lock position row exclusively
  SELECT * INTO v_position FROM paper_trading_positions
    WHERE id = p_position_id
    FOR UPDATE;

  -- Verify position is open (prevent double-close)
  IF v_position.status != 'open' THEN
    RAISE EXCEPTION 'Position % already closed', p_position_id;
  END IF;

  -- Verify exit_time is after entry_time
  IF p_exit_time <= v_position.entry_time THEN
    RAISE EXCEPTION 'Exit time must be after entry time';
  END IF;

  -- Calculate PnL
  DECLARE
    v_pnl DECIMAL;
    v_pnl_pct DECIMAL;
  BEGIN
    IF v_position.direction = 'long' THEN
      v_pnl := (p_exit_price - v_position.entry_price) * v_position.quantity;
      v_pnl_pct := ((p_exit_price - v_position.entry_price) / v_position.entry_price) * 100;
    ELSE
      v_pnl := (v_position.entry_price - p_exit_price) * v_position.quantity;
      v_pnl_pct := ((v_position.entry_price - p_exit_price) / v_position.entry_price) * 100;
    END IF;

    -- Create trade record (atomically within same transaction)
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
  END;

  RETURN v_trade_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Permissions
GRANT EXECUTE ON FUNCTION close_paper_position TO service_role;
```

---

## Data Validation Checklist for Implementation

Before deploying paper trading executor, verify:

- [ ] **Transaction Safety:** All position create/update/close operations wrapped in BEGIN/COMMIT
- [ ] **Race Condition Prevention:** Position status checked with FOR UPDATE lock before close
- [ ] **Immutability:** RLS policies prevent UPDATE/DELETE on trades and execution logs
- [ ] **Referential Integrity:** Foreign keys use ON DELETE RESTRICT (never CASCADE for audit tables)
- [ ] **Constraint Compliance:** All NOT NULL, CHECK, UNIQUE constraints in place
- [ ] **PnL Accuracy:** Generated columns or triggers verify calculations match
- [ ] **RLS Coverage:** Every user-data table has RLS policies (no default-allow)
- [ ] **Indices Present:** Query paths have covering indices (user_id, strategy_id, time)
- [ ] **Null Handling:** Required columns have NOT NULL; optional columns documented
- [ ] **Audit Trail:** Every action logged to strategy_execution_log with immutable constraints

---

## Testing Strategy for Data Integrity

### Unit Tests

```python
# test_paper_trading_integrity.py
def test_position_race_condition():
    """Verify two concurrent closures only succeed once"""
    pos_id = create_test_position()

    # Simulate concurrent requests
    future1 = executor.close_position_async(pos_id, 105, "TP_HIT")
    future2 = executor.close_position_async(pos_id, 104, "SL_HIT")

    result1, result2 = asyncio.gather(future1, future2)

    # Only ONE should succeed (other should get "already closed" error)
    assert (result1.ok and result2.error) or (result2.ok and result1.error)

    # Exactly ONE trade created
    trades = db.query("SELECT COUNT(*) FROM paper_trading_trades WHERE position_id = ?", pos_id)
    assert trades == 1

def test_pnl_calculation_accuracy():
    """Verify PnL stored matches calculated"""
    trade = create_test_trade(
        entry_price=100,
        exit_price=105,
        quantity=10,
        direction='long'
    )

    expected_pnl = (105 - 100) * 10  # $50
    expected_pnl_pct = ((105 - 100) / 100) * 100  # 5%

    assert trade.pnl == expected_pnl
    assert trade.pnl_pct == expected_pnl_pct

def test_immutability_enforcement():
    """Verify trades cannot be updated/deleted"""
    trade = create_test_trade()

    with pytest.raises(Exception):  # RLS should reject
        db.execute("UPDATE paper_trading_trades SET pnl = 999999 WHERE id = ?", trade.id)

    with pytest.raises(Exception):  # RLS should reject
        db.execute("DELETE FROM paper_trading_trades WHERE id = ?", trade.id)
```

### Integration Tests

1. **End-to-end paper trade execution**
   - Entry condition triggered → position created
   - SL hits → trade closed at SL price
   - Verify execution_log has entry AND exit records
   - Verify metrics updated correctly

2. **Cascading delete safety**
   - Delete user → check all positions/trades/logs orphaned properly
   - Delete strategy → check ON DELETE RESTRICT prevents deletion if trades exist

3. **RLS enforcement**
   - User A creates position → User B cannot see it
   - Query bypassing RLS (SQL injection) → Still blocked

---

## Summary of Recommendations

| Issue | Severity | Fix | Effort |
|-------|----------|-----|--------|
| Position race condition (1.1) | CRITICAL | Add FOR UPDATE lock + position_id uniqueness | 2-3h |
| Immutability enforcement (2.1, 3.1) | CRITICAL | RLS policies + function permissions | 1-2h |
| Missing constraints (1.3, 2.2, 2.3) | HIGH | CHECK constraints on prices, quantities, times | 2-3h |
| Missing RLS policies (6.1) | CRITICAL | RLS on all user-owned tables | 2-3h |
| Missing indices (1.6, 2.5, 3.3) | MEDIUM | Create covering indices | 1h |
| Enum types (1.5, 2.4, 3.2) | MEDIUM | CREATE TYPE + migrate text → enum | 2-3h |
| Referential integrity (2.6) | MEDIUM | Foreign key to position_id + ON DELETE RESTRICT | 1-2h |
| Calculated metrics (4.1) | HIGH | Switch to materialized view or trigger validation | 3-4h |
| Cascading deletes (5.1) | HIGH | ON DELETE RESTRICT instead of CASCADE | 1h |

**Total Effort:** 15-23 hours (2-3 week sprint with testing)

**Critical Path:** Issue 1.1 (race condition) blocks safe execution. Must fix before deployment.

---

## Approval Checkpoints

- [ ] Data Integrity Guardian reviews migration script
- [ ] Product confirms acceptable timeline for fixes
- [ ] QA prepared with integration test scenarios
- [ ] Docs updated with data model and invariants

**Status:** Ready for implementation. Do not deploy without addressing critical issues.
