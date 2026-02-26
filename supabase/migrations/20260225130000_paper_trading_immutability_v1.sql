-- Paper Trading Immutability & Append-Only Enforcement
-- Prevents modification or deletion of trades (audit trail integrity)
-- Date: 2026-02-25

-- ============================================================================
-- 1. TRIGGER: Prevent updates to closed trades
-- ============================================================================
-- Ensures paper_trading_trades is append-only
-- Once a trade is created, it cannot be modified

CREATE OR REPLACE FUNCTION prevent_trade_updates()
RETURNS TRIGGER AS $$
BEGIN
  -- Reject any UPDATE attempt on paper_trading_trades
  -- (This should already be blocked by RLS, but trigger provides extra safety)
  RAISE EXCEPTION 'Cannot modify trades - audit trail must be immutable';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Attach trigger to paper_trading_trades table
DROP TRIGGER IF EXISTS prevent_trade_updates_trigger ON paper_trading_trades;
CREATE TRIGGER prevent_trade_updates_trigger
  BEFORE UPDATE ON paper_trading_trades
  FOR EACH ROW
  EXECUTE FUNCTION prevent_trade_updates();

-- ============================================================================
-- 2. TRIGGER: Prevent deletes of closed trades
-- ============================================================================
-- Extra protection: prevent deletion of audit trail

CREATE OR REPLACE FUNCTION prevent_trade_deletes()
RETURNS TRIGGER AS $$
BEGIN
  -- Reject any DELETE attempt on paper_trading_trades
  RAISE EXCEPTION 'Cannot delete trades - audit trail must be immutable';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS prevent_trade_deletes_trigger ON paper_trading_trades;
CREATE TRIGGER prevent_trade_deletes_trigger
  BEFORE DELETE ON paper_trading_trades
  FOR EACH ROW
  EXECUTE FUNCTION prevent_trade_deletes();

-- ============================================================================
-- 3. TRIGGER: Automatic updated_at for positions
-- ============================================================================
-- Keep updated_at in sync with actual position changes

CREATE OR REPLACE FUNCTION update_position_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS update_position_timestamp_trigger ON paper_trading_positions;
CREATE TRIGGER update_position_timestamp_trigger
  BEFORE UPDATE ON paper_trading_positions
  FOR EACH ROW
  EXECUTE FUNCTION update_position_timestamp();

-- ============================================================================
-- 4. TRIGGER: Prevent orphaned positions
-- ============================================================================
-- If a position's entry_price or quantity is NULL, reject the INSERT/UPDATE
-- (Should be caught by NOT NULL, but trigger provides explicit error message)

CREATE OR REPLACE FUNCTION validate_position_completeness()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.entry_price IS NULL THEN
    RAISE EXCEPTION 'Position entry_price cannot be null - partial failure detected';
  END IF;

  IF NEW.quantity IS NULL THEN
    RAISE EXCEPTION 'Position quantity cannot be null - partial failure detected';
  END IF;

  IF NEW.stop_loss_price IS NULL THEN
    RAISE EXCEPTION 'Position stop_loss_price cannot be null';
  END IF;

  IF NEW.take_profit_price IS NULL THEN
    RAISE EXCEPTION 'Position take_profit_price cannot be null';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS validate_position_completeness_trigger ON paper_trading_positions;
CREATE TRIGGER validate_position_completeness_trigger
  BEFORE INSERT OR UPDATE ON paper_trading_positions
  FOR EACH ROW
  EXECUTE FUNCTION validate_position_completeness();

-- ============================================================================
-- 5. ENHANCED SAFE POSITION CLOSURE WITH LOGGING
-- ============================================================================
-- Logs all closure attempts for audit trail

CREATE TABLE IF NOT EXISTS position_closure_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  position_id UUID NOT NULL,
  user_id UUID NOT NULL,
  strategy_id UUID NOT NULL,
  attempted_at TIMESTAMPTZ DEFAULT NOW(),
  status TEXT NOT NULL CHECK (status IN ('success', 'race_condition', 'error')),
  error_message TEXT,
  entry_price DECIMAL(12,4),
  exit_price DECIMAL(12,4),
  pnl DECIMAL(12,2)
);

-- Index for debugging
CREATE INDEX IF NOT EXISTS idx_closure_log_position
  ON position_closure_log(position_id);

-- Enable RLS
ALTER TABLE position_closure_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own closure logs"
  ON position_closure_log FOR SELECT
  USING (auth.uid() = user_id);

-- ============================================================================
-- 6. RACE CONDITION DETECTION TEST FUNCTION
-- ============================================================================
-- This function simulates concurrent close attempts to verify race condition prevention

CREATE OR REPLACE FUNCTION test_concurrent_close(
  p_position_id UUID,
  p_user_id UUID,
  p_strategy_id UUID
) RETURNS TABLE (
  attempt_number INT,
  status TEXT,
  error_message TEXT
) AS $$
DECLARE
  v_exit_price DECIMAL;
  v_result JSONB;
  v_success BOOLEAN;
BEGIN
  -- Simulate first close attempt
  v_exit_price := 105.0;
  v_result := close_paper_position(p_position_id, v_exit_price, 'EXIT_SIGNAL');
  v_success := v_result ->> 'success' = 'true';

  IF v_success THEN
    RETURN QUERY SELECT 1, 'success', NULL::TEXT;
  ELSE
    RETURN QUERY SELECT 1, 'error', v_result ->> 'error'::TEXT;
  END IF;

  -- Simulate second close attempt (should fail with race condition)
  v_exit_price := 106.0;
  v_result := close_paper_position(p_position_id, v_exit_price, 'TP_HIT');
  v_success := v_result ->> 'success' = 'true';

  IF v_success THEN
    RETURN QUERY SELECT 2, 'success', NULL::TEXT;
  ELSE
    RETURN QUERY SELECT 2, v_result ->> 'error'::TEXT, v_result ->> 'error'::TEXT;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 7. DATA CONSISTENCY VALIDATION
-- ============================================================================
-- Helper view to detect orphaned positions or trades

CREATE OR REPLACE VIEW consistency_check_orphaned_positions AS
SELECT
  pp.id as position_id,
  pp.user_id,
  pp.strategy_id,
  pp.symbol_id,
  pp.status,
  COUNT(ppt.id) as trade_count,
  CASE
    WHEN pp.status = 'closed' AND COUNT(ppt.id) = 0 THEN 'ORPHANED: Closed position with no trade'
    WHEN pp.status = 'open' AND COUNT(ppt.id) > 0 THEN 'ORPHANED: Open position with closed trade'
    ELSE 'OK'
  END as consistency_status
FROM paper_trading_positions pp
LEFT JOIN paper_trading_trades ppt ON pp.id = ppt.id
GROUP BY pp.id, pp.user_id, pp.strategy_id, pp.symbol_id, pp.status;

-- ============================================================================
-- 8. VERIFICATION QUERIES
-- ============================================================================
-- Run after migration to verify immutability enforcement:
--
-- SELECT * FROM information_schema.triggers
-- WHERE trigger_name LIKE 'prevent_%' OR trigger_name LIKE 'validate_%';
--
-- SELECT * FROM pg_indexes
-- WHERE tablename IN ('paper_trading_positions', 'paper_trading_trades');
--
-- SELECT proname FROM pg_proc
-- WHERE proname IN ('prevent_trade_updates', 'prevent_trade_deletes',
--                   'validate_position_completeness', 'test_concurrent_close');
