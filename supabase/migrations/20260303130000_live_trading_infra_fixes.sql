-- Infrastructure fixes for live trading executor (PR #28 review findings)
-- Migration: 20260303130000_live_trading_infra_fixes
-- Covers: #115, #120, #121, #122, #153, #154, #158, #166, #167, #169, #170, #187

-- ============================================================================
-- 1. DEFINE increment_rate_limit RPC (#115, #153, #169, #170)
-- ============================================================================

CREATE OR REPLACE FUNCTION increment_rate_limit(
  p_user_id      UUID,
  p_window_start TIMESTAMPTZ,
  p_max_requests INT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp  -- #170: prevent search_path hijacking
AS $$
DECLARE v_count INT;
BEGIN
  -- #169: Defense in depth — reject cross-user calls
  IF auth.uid() IS DISTINCT FROM p_user_id THEN
    RAISE EXCEPTION 'unauthorized: caller % cannot increment rate limit for %',
      auth.uid(), p_user_id
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  -- #153: Two-statement form (upsert + SELECT) because
  -- RETURNING...INTO after INSERT ON CONFLICT DO UPDATE is invalid PL/pgSQL
  INSERT INTO live_order_rate_limits (user_id, window_start, request_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET request_count = live_order_rate_limits.request_count + 1;

  SELECT request_count INTO v_count
  FROM live_order_rate_limits
  WHERE user_id = p_user_id AND window_start = p_window_start;

  RETURN v_count <= p_max_requests;
END;
$$;

-- #169: Revoke public access; only service_role should call this RPC
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM anon;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) FROM authenticated;
GRANT EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) TO service_role;

-- ============================================================================
-- 2. ADD updated_at AUTO-UPDATE TRIGGER (#120, #158)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_live_positions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- #158: Drop-then-create for idempotency (matches paper trading migration convention)
DROP TRIGGER IF EXISTS live_positions_updated_at ON live_trading_positions;
CREATE TRIGGER live_positions_updated_at
  BEFORE UPDATE ON live_trading_positions
  FOR EACH ROW EXECUTE FUNCTION update_live_positions_updated_at();

-- ============================================================================
-- 3. FIX FK DELETE INCONSISTENCY (#121, #166)
-- ============================================================================
-- live_trading_positions.user_id uses CASCADE; should be RESTRICT.
-- Financial records must never be silently deleted.
-- GDPR deletion requires manual ordered purge:
--   1. DELETE FROM live_trading_trades WHERE user_id = $1;
--   2. DELETE FROM live_trading_positions WHERE user_id = $1;
--   3. DELETE FROM auth.users WHERE id = $1;

ALTER TABLE live_trading_positions
  DROP CONSTRAINT IF EXISTS live_trading_positions_user_id_fkey;

ALTER TABLE live_trading_positions
  ADD CONSTRAINT live_trading_positions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE RESTRICT;

-- ============================================================================
-- 4. ADD CHECK CONSTRAINTS TO live_trading_trades (#122, #154, #167)
-- ============================================================================

ALTER TABLE live_trading_trades
  ADD CONSTRAINT live_trades_positive_prices
    CHECK (entry_price > 0 AND exit_price > 0),
  ADD CONSTRAINT live_trades_positive_quantity
    CHECK (quantity > 0),
  ADD CONSTRAINT live_trades_close_reason_valid
    CHECK (close_reason IN (
      -- #154: Match UPPERCASE casing from live_trading_positions CHECK constraint
      'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
      'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
      'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
      'EMERGENCY_CLOSE',     -- Phase 5 recovery scan
      'CIRCUIT_BREAKER'      -- Phase 8.6
    )),
  -- #167: Sanity bounds on pnl
  ADD CONSTRAINT live_trades_pnl_sane
    CHECK (pnl BETWEEN -1000000 AND 1000000),
  ADD CONSTRAINT live_trades_pnl_pct_sane
    CHECK (pnl_pct IS NULL OR pnl_pct BETWEEN -1000 AND 1000);

-- ============================================================================
-- 5. UPDATE live_trading_positions STATUS AND CLOSE_REASON CHECKS (#187)
-- ============================================================================
-- Add 'closing_emergency' to status CHECK (for Phase 5 recovery)
-- Add 'EMERGENCY_CLOSE' and 'CIRCUIT_BREAKER' to close_reason CHECK

ALTER TABLE live_trading_positions
  DROP CONSTRAINT IF EXISTS live_trading_positions_status_check;

ALTER TABLE live_trading_positions
  ADD CONSTRAINT live_trading_positions_status_check
    CHECK (status IN (
      'pending_entry',
      'pending_bracket',
      'open',
      'pending_close',
      'closing_emergency',   -- Phase 5 recovery scan
      'closed',
      'cancelled'
    ));

ALTER TABLE live_trading_positions
  DROP CONSTRAINT IF EXISTS live_trading_positions_close_reason_check;

ALTER TABLE live_trading_positions
  ADD CONSTRAINT live_trading_positions_close_reason_check
    CHECK (close_reason IS NULL OR close_reason IN (
      'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
      'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
      'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
      'EMERGENCY_CLOSE',     -- Phase 5 recovery scan
      'CIRCUIT_BREAKER'      -- Phase 8.6
    ));

-- ============================================================================
-- 6. SET order_submitted_at NOT NULL DEFAULT (#180)
-- ============================================================================
-- Prevent future NULL insertions that would be excluded from recovery scan

ALTER TABLE live_trading_positions
  ALTER COLUMN order_submitted_at SET DEFAULT NOW();
