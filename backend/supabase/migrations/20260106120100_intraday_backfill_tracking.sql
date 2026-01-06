-- Migration: Track which symbols have had intraday data backfilled
-- Prevents duplicate backfill requests

CREATE TABLE IF NOT EXISTS intraday_backfill_status (
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  last_backfill_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  backfill_days INTEGER NOT NULL DEFAULT 10,
  bar_count INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  
  PRIMARY KEY (symbol_id)
);

-- Index for quick status checks
CREATE INDEX idx_intraday_backfill_status ON intraday_backfill_status(symbol_id, status);

-- Function to check if symbol needs backfill
CREATE OR REPLACE FUNCTION needs_intraday_backfill(p_symbol_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  v_status RECORD;
  v_bar_count INTEGER;
BEGIN
  -- Check if backfill record exists
  SELECT * INTO v_status
  FROM intraday_backfill_status
  WHERE symbol_id = p_symbol_id;
  
  -- If no record exists, needs backfill
  IF NOT FOUND THEN
    RETURN TRUE;
  END IF;
  
  -- If last backfill was more than 1 day ago, needs refresh
  IF v_status.last_backfill_at < NOW() - INTERVAL '1 day' THEN
    RETURN TRUE;
  END IF;
  
  -- If status is failed, needs retry
  IF v_status.status = 'failed' THEN
    RETURN TRUE;
  END IF;
  
  -- Check if we actually have intraday bars
  SELECT COUNT(*) INTO v_bar_count
  FROM intraday_bars
  WHERE symbol_id = p_symbol_id;
  
  -- If no bars exist, needs backfill
  IF v_bar_count = 0 THEN
    RETURN TRUE;
  END IF;
  
  -- Otherwise, no backfill needed
  RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to mark backfill as started
CREATE OR REPLACE FUNCTION mark_backfill_started(p_symbol_id UUID)
RETURNS VOID AS $$
BEGIN
  INSERT INTO intraday_backfill_status (symbol_id, status, last_backfill_at)
  VALUES (p_symbol_id, 'in_progress', NOW())
  ON CONFLICT (symbol_id) 
  DO UPDATE SET 
    status = 'in_progress',
    last_backfill_at = NOW(),
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to mark backfill as completed
CREATE OR REPLACE FUNCTION mark_backfill_completed(
  p_symbol_id UUID,
  p_bar_count INTEGER,
  p_backfill_days INTEGER
)
RETURNS VOID AS $$
BEGIN
  INSERT INTO intraday_backfill_status (symbol_id, status, bar_count, backfill_days, last_backfill_at)
  VALUES (p_symbol_id, 'completed', p_bar_count, p_backfill_days, NOW())
  ON CONFLICT (symbol_id) 
  DO UPDATE SET 
    status = 'completed',
    bar_count = p_bar_count,
    backfill_days = p_backfill_days,
    last_backfill_at = NOW(),
    error_message = NULL,
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to mark backfill as failed
CREATE OR REPLACE FUNCTION mark_backfill_failed(
  p_symbol_id UUID,
  p_error_message TEXT
)
RETURNS VOID AS $$
BEGIN
  INSERT INTO intraday_backfill_status (symbol_id, status, error_message, last_backfill_at)
  VALUES (p_symbol_id, 'failed', p_error_message, NOW())
  ON CONFLICT (symbol_id) 
  DO UPDATE SET 
    status = 'failed',
    error_message = p_error_message,
    last_backfill_at = NOW(),
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON intraday_backfill_status TO authenticated;
GRANT SELECT, INSERT, UPDATE ON intraday_backfill_status TO service_role;

COMMENT ON TABLE intraday_backfill_status IS 'Tracks which symbols have had intraday data backfilled to prevent duplicate requests';
COMMENT ON FUNCTION needs_intraday_backfill IS 'Returns true if symbol needs intraday backfill (no data, stale data, or failed previous attempt)';
