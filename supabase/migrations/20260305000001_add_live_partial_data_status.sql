-- Migration: Add 'live_partial' to ohlc_bars_v2 data_status CHECK constraint
-- Also create index on (symbol_id, timeframe, ts DESC) for m1 queries

-- Drop the existing CHECK constraint and recreate with 'live_partial'
ALTER TABLE ohlc_bars_v2
  DROP CONSTRAINT IF EXISTS ohlc_bars_v2_data_status_check;

ALTER TABLE ohlc_bars_v2
  ADD CONSTRAINT ohlc_bars_v2_data_status_check
  CHECK (data_status IN ('live', 'stale', 'refreshing', 'live_partial'));

-- Index for fast m1 bar lookups during partial candle synthesis
-- Partial index: only m1 rows with is_intraday=true
CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_m1_synthesis
  ON ohlc_bars_v2 (symbol_id, ts DESC)
  WHERE timeframe = 'm1' AND is_intraday = true;

COMMENT ON INDEX idx_ohlc_bars_v2_m1_synthesis IS
  'Supports partial candle synthesis: fast retrieval of today''s m1 bars per symbol';
