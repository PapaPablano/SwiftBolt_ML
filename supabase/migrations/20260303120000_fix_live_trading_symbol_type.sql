-- Fix live trading symbol_id type: UUID → TEXT (#117)
-- The executor passes raw symbol strings (e.g., "AAPL", "@ES") but the column is UUID.
-- UUID strings are valid TEXT, so this is a safe forward migration.
-- NOTE: This is a one-way door once non-UUID strings are written (#164).

-- Change symbol_id from UUID to TEXT
ALTER TABLE live_trading_positions
  ALTER COLUMN symbol_id TYPE TEXT;

-- Re-create affected indexes using correct existing names (#152)
-- Original names from 20260303110000_live_trading_tables.sql lines 86+91
DROP INDEX IF EXISTS idx_live_positions_active_unique;
DROP INDEX IF EXISTS idx_live_positions_user_strategy;

CREATE UNIQUE INDEX idx_live_positions_active_unique
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');

CREATE INDEX idx_live_positions_user_strategy
  ON live_trading_positions (user_id, strategy_id, symbol_id, status, created_at DESC);
