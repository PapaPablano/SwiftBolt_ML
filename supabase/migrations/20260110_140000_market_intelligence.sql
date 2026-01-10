-- Market Intelligence Schema
-- Adds market calendar cache, corporate actions tracking, and helper functions

-- Market calendar cache
CREATE TABLE IF NOT EXISTS market_calendar (
  date DATE PRIMARY KEY,
  is_open BOOLEAN NOT NULL,
  session_open TIME,
  session_close TIME,
  market_open TIME,
  market_close TIME,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_market_calendar_date ON market_calendar(date);

-- Corporate actions registry
CREATE TABLE IF NOT EXISTS corporate_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('stock_split', 'reverse_split', 'dividend', 'merger', 'spin_off')),
  ex_date DATE NOT NULL,
  record_date DATE,
  payment_date DATE,
  
  -- Split-specific fields
  old_rate NUMERIC,
  new_rate NUMERIC,
  ratio NUMERIC GENERATED ALWAYS AS (new_rate / NULLIF(old_rate, 0)) STORED,
  
  -- Dividend-specific fields
  cash_amount NUMERIC,
  
  -- Adjustment tracking
  bars_adjusted BOOLEAN DEFAULT FALSE,
  adjusted_at TIMESTAMPTZ,
  
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(symbol, action_type, ex_date)
);

CREATE INDEX idx_corporate_actions_symbol ON corporate_actions(symbol);
CREATE INDEX idx_corporate_actions_date ON corporate_actions(ex_date);
CREATE INDEX idx_corporate_actions_unadjusted ON corporate_actions(bars_adjusted) WHERE bars_adjusted = FALSE;

-- Function to check if market is open
CREATE OR REPLACE FUNCTION is_market_open(check_date DATE DEFAULT CURRENT_DATE)
RETURNS BOOLEAN AS $$
DECLARE
  trading_day market_calendar%ROWTYPE;
  current_time TIME;
BEGIN
  SELECT * INTO trading_day FROM market_calendar WHERE date = check_date;
  
  IF NOT FOUND THEN
    RETURN FALSE;  -- No calendar data, assume closed
  END IF;
  
  IF NOT trading_day.is_open THEN
    RETURN FALSE;  -- Market closed (holiday/weekend)
  END IF;
  
  current_time := CURRENT_TIME;
  RETURN current_time BETWEEN trading_day.market_open AND trading_day.market_close;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get next trading day
CREATE OR REPLACE FUNCTION next_trading_day(from_date DATE DEFAULT CURRENT_DATE)
RETURNS DATE AS $$
  SELECT date 
  FROM market_calendar 
  WHERE date > from_date 
    AND is_open = TRUE 
  ORDER BY date ASC 
  LIMIT 1;
$$ LANGUAGE sql STABLE;

-- Function to get unadjusted corporate actions
CREATE OR REPLACE FUNCTION get_pending_adjustments()
RETURNS TABLE (
  symbol TEXT,
  action_type TEXT,
  ex_date DATE,
  ratio NUMERIC,
  bars_affected BIGINT
) AS $$
  SELECT 
    ca.symbol,
    ca.action_type,
    ca.ex_date,
    ca.ratio,
    COUNT(b.id) as bars_affected
  FROM corporate_actions ca
  LEFT JOIN ohlcbarsv2 b ON b.symbol_id = (
    SELECT id FROM symbols WHERE ticker = ca.symbol LIMIT 1
  ) AND b.ts < ca.ex_date
  WHERE ca.bars_adjusted = FALSE
    AND ca.action_type IN ('stock_split', 'reverse_split')
  GROUP BY ca.symbol, ca.action_type, ca.ex_date, ca.ratio;
$$ LANGUAGE sql STABLE;

-- Function to check for pending splits for a symbol
CREATE OR REPLACE FUNCTION has_pending_splits(check_symbol TEXT)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 
    FROM corporate_actions 
    WHERE symbol = check_symbol 
      AND bars_adjusted = FALSE
      AND action_type IN ('stock_split', 'reverse_split')
  );
$$ LANGUAGE sql STABLE;

-- Add adjusted_for column to ohlcbarsv2 if it doesn't exist
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'ohlcbarsv2' AND column_name = 'adjusted_for'
  ) THEN
    ALTER TABLE ohlcbarsv2 ADD COLUMN adjusted_for UUID REFERENCES corporate_actions(id);
    CREATE INDEX idx_ohlcbarsv2_adjusted_for ON ohlcbarsv2(adjusted_for);
  END IF;
END $$;
