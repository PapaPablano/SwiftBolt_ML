-- ============================================================================
-- MARKET INTELLIGENCE DEPLOYMENT SCRIPT
-- Run this in Supabase Dashboard → SQL Editor
-- ============================================================================

-- Migration 1: Market Intelligence Schema
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_market_calendar_date ON market_calendar(date);

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

CREATE INDEX IF NOT EXISTS idx_corporate_actions_symbol ON corporate_actions(symbol);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_date ON corporate_actions(ex_date);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_unadjusted ON corporate_actions(bars_adjusted) WHERE bars_adjusted = FALSE;

-- Function to check if market is open
CREATE OR REPLACE FUNCTION is_market_open(check_date DATE DEFAULT CURRENT_DATE)
RETURNS BOOLEAN AS $$
DECLARE
  trading_day market_calendar%ROWTYPE;
BEGIN
  SELECT * INTO trading_day FROM market_calendar WHERE date = check_date;
  
  IF NOT FOUND THEN
    RETURN FALSE;  -- No calendar data, assume closed
  END IF;
  
  IF NOT trading_day.is_open THEN
    RETURN FALSE;  -- Market closed (holiday/weekend)
  END IF;
  
  RETURN LOCALTIME BETWEEN trading_day.market_open AND trading_day.market_close;
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
  LEFT JOIN ohlc_bars_v2 b ON b.symbol_id = (
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

-- Add adjusted_for column to ohlc_bars_v2 if it doesn't exist
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'ohlc_bars_v2' AND column_name = 'adjusted_for'
  ) THEN
    ALTER TABLE ohlc_bars_v2 ADD COLUMN adjusted_for UUID REFERENCES corporate_actions(id);
    CREATE INDEX idx_ohlc_bars_v2_adjusted_for ON ohlc_bars_v2(adjusted_for);
  END IF;
END $$;


-- Migration 2: Market Intelligence Dashboard
-- ============================================================================

-- Market Intelligence Dashboard View
CREATE OR REPLACE VIEW market_intelligence_dashboard AS
SELECT 
  'Market Status' as metric,
  CASE WHEN is_market_open() THEN 'OPEN' ELSE 'CLOSED' END as value,
  next_trading_day()::TEXT as next_event,
  'real-time' as category
UNION ALL
SELECT 
  'Pending Split Adjustments',
  COUNT(*)::TEXT,
  MIN(ex_date)::TEXT,
  'corporate_actions'
FROM corporate_actions
WHERE bars_adjusted = FALSE
  AND action_type IN ('stock_split', 'reverse_split')
UNION ALL
SELECT
  'Calendar Cache Status',
  COUNT(*)::TEXT || ' days',
  MAX(date)::TEXT,
  'calendar'
FROM market_calendar
WHERE date >= CURRENT_DATE
UNION ALL
SELECT
  'Total Corporate Actions',
  COUNT(*)::TEXT,
  MAX(ex_date)::TEXT,
  'corporate_actions'
FROM corporate_actions
UNION ALL
SELECT
  'Unadjusted Bars',
  COUNT(*)::TEXT,
  NULL,
  'data_quality'
FROM ohlc_bars_v2
WHERE adjusted_for IS NULL
  AND symbol_id IN (
    SELECT symbol_id 
    FROM corporate_actions 
    WHERE bars_adjusted = FALSE
      AND action_type IN ('stock_split', 'reverse_split')
  );

-- Corporate Actions Summary View
CREATE OR REPLACE VIEW corporate_actions_summary AS
SELECT 
  ca.symbol,
  ca.action_type,
  ca.ex_date,
  ca.ratio,
  ca.bars_adjusted,
  ca.adjusted_at,
  COUNT(b.id) as total_bars,
  COUNT(CASE WHEN b.adjusted_for IS NULL THEN 1 END) as unadjusted_bars,
  COUNT(CASE WHEN b.adjusted_for = ca.id THEN 1 END) as adjusted_bars
FROM corporate_actions ca
LEFT JOIN symbols s ON s.ticker = ca.symbol
LEFT JOIN ohlc_bars_v2 b ON b.symbol_id = s.id AND b.ts < ca.ex_date
WHERE ca.action_type IN ('stock_split', 'reverse_split')
GROUP BY ca.id, ca.symbol, ca.action_type, ca.ex_date, ca.ratio, ca.bars_adjusted, ca.adjusted_at
ORDER BY ca.ex_date DESC;

-- Market Calendar Coverage View
CREATE OR REPLACE VIEW market_calendar_coverage AS
SELECT 
  DATE_TRUNC('month', date) as month,
  COUNT(*) as trading_days,
  COUNT(*) FILTER (WHERE is_open = TRUE) as open_days,
  COUNT(*) FILTER (WHERE is_open = FALSE) as closed_days,
  MIN(date) as first_day,
  MAX(date) as last_day
FROM market_calendar
GROUP BY DATE_TRUNC('month', date)
ORDER BY month DESC;

-- Function to get market intelligence health report
CREATE OR REPLACE FUNCTION get_market_intelligence_health()
RETURNS TABLE (
  component TEXT,
  status TEXT,
  details JSONB
) AS $$
BEGIN
  -- Calendar coverage check
  RETURN QUERY
  SELECT 
    'Calendar Coverage'::TEXT,
    CASE 
      WHEN days_ahead >= 30 THEN 'HEALTHY'
      WHEN days_ahead >= 7 THEN 'WARNING'
      ELSE 'CRITICAL'
    END,
    jsonb_build_object(
      'days_ahead', days_ahead,
      'last_cached_date', last_date
    )
  FROM (
    SELECT 
      MAX(date) - CURRENT_DATE as days_ahead,
      MAX(date) as last_date
    FROM market_calendar
  ) cal;
  
  -- Pending adjustments check
  RETURN QUERY
  SELECT 
    'Pending Adjustments'::TEXT,
    CASE 
      WHEN pending_count = 0 THEN 'HEALTHY'
      WHEN pending_count <= 5 THEN 'WARNING'
      ELSE 'CRITICAL'
    END,
    jsonb_build_object(
      'pending_splits', pending_count,
      'oldest_pending', oldest_date,
      'affected_bars', total_bars
    )
  FROM (
    SELECT 
      COUNT(*) as pending_count,
      MIN(ex_date) as oldest_date,
      SUM(bars_affected) as total_bars
    FROM get_pending_adjustments()
  ) pending;
  
  -- Data quality check
  RETURN QUERY
  SELECT 
    'Data Quality'::TEXT,
    CASE 
      WHEN unadjusted_pct < 1 THEN 'HEALTHY'
      WHEN unadjusted_pct < 5 THEN 'WARNING'
      ELSE 'CRITICAL'
    END,
    jsonb_build_object(
      'total_bars', total_bars,
      'unadjusted_bars', unadjusted_bars,
      'unadjusted_percentage', ROUND(unadjusted_pct, 2)
    )
  FROM (
    SELECT 
      COUNT(*) as total_bars,
      COUNT(*) FILTER (WHERE adjusted_for IS NULL) as unadjusted_bars,
      (COUNT(*) FILTER (WHERE adjusted_for IS NULL)::NUMERIC / NULLIF(COUNT(*), 0) * 100) as unadjusted_pct
    FROM ohlc_bars_v2
    WHERE symbol_id IN (
      SELECT DISTINCT symbol_id 
      FROM corporate_actions 
      WHERE action_type IN ('stock_split', 'reverse_split')
    )
  ) quality;
  
END;
$$ LANGUAGE plpgsql;

-- Function to get recent corporate actions activity
CREATE OR REPLACE FUNCTION get_recent_corporate_actions(days_back INT DEFAULT 30)
RETURNS TABLE (
  date DATE,
  action_count BIGINT,
  splits_count BIGINT,
  dividends_count BIGINT,
  adjusted_count BIGINT
) AS $$
  SELECT 
    ex_date::DATE as date,
    COUNT(*) as action_count,
    COUNT(*) FILTER (WHERE action_type IN ('stock_split', 'reverse_split')) as splits_count,
    COUNT(*) FILTER (WHERE action_type = 'dividend') as dividends_count,
    COUNT(*) FILTER (WHERE bars_adjusted = TRUE) as adjusted_count
  FROM corporate_actions
  WHERE ex_date >= CURRENT_DATE - days_back
  GROUP BY ex_date::DATE
  ORDER BY date DESC;
$$ LANGUAGE sql STABLE;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ex_date_desc ON corporate_actions(ex_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_calendar_date_desc ON market_calendar(date DESC);

-- Grant permissions
GRANT SELECT ON market_intelligence_dashboard TO anon, authenticated;
GRANT SELECT ON corporate_actions_summary TO anon, authenticated;
GRANT SELECT ON market_calendar_coverage TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_market_intelligence_health() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION get_recent_corporate_actions(INT) TO anon, authenticated;

-- ============================================================================
-- DEPLOYMENT COMPLETE
-- ============================================================================

-- Verify deployment
SELECT 'Deployment successful! Run these queries to verify:' as message;
SELECT '1. SELECT * FROM market_intelligence_dashboard;' as step_1;
SELECT '2. SELECT * FROM get_market_intelligence_health();' as step_2;
SELECT '3. SELECT COUNT(*) FROM market_calendar;' as step_3;
