-- Multi-Timeframe Support & User Symbol Tracking
-- Part 1: User symbol tracking table
-- Part 2: Auto-trigger for job creation
-- Part 3: Helper functions for monitoring

-- ============================================================================
-- PART 1: User Symbol Tracking Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_symbol_tracking (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol_id uuid REFERENCES symbols(id) ON DELETE CASCADE,
  source text NOT NULL CHECK (source IN ('watchlist', 'recent_search', 'chart_view')),
  priority int DEFAULT 100,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(user_id, symbol_id, source)
);

CREATE INDEX IF NOT EXISTS idx_user_symbol_tracking_user ON user_symbol_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_user_symbol_tracking_symbol ON user_symbol_tracking(symbol_id);
CREATE INDEX IF NOT EXISTS idx_user_symbol_tracking_source ON user_symbol_tracking(source);

COMMENT ON TABLE user_symbol_tracking IS 'Tracks user interest in symbols from watchlist, searches, and chart views';
COMMENT ON COLUMN user_symbol_tracking.source IS 'Origin of symbol tracking: watchlist (300), chart_view (200), recent_search (100)';
COMMENT ON COLUMN user_symbol_tracking.priority IS 'Processing priority: higher = processed first';

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_user_symbol_tracking_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_user_symbol_tracking_timestamp ON user_symbol_tracking;
CREATE TRIGGER trigger_update_user_symbol_tracking_timestamp
BEFORE UPDATE ON user_symbol_tracking
FOR EACH ROW
EXECUTE FUNCTION update_user_symbol_tracking_timestamp();

-- ============================================================================
-- PART 2: Auto-Create Jobs for Tracked Symbols
-- ============================================================================

CREATE OR REPLACE FUNCTION auto_create_jobs_for_tracked_symbols()
RETURNS TRIGGER AS $$
DECLARE
  v_ticker text;
  v_timeframe text;
  v_job_priority int;
BEGIN
  -- Get symbol ticker
  SELECT ticker INTO v_ticker
  FROM symbols
  WHERE id = NEW.symbol_id;

  -- Set priority based on source
  v_job_priority := CASE NEW.source
    WHEN 'watchlist' THEN 300
    WHEN 'chart_view' THEN 200
    WHEN 'recent_search' THEN 100
    ELSE 100
  END;

  -- Create job definitions for all timeframes (m15, h1, h4)
  FOREACH v_timeframe IN ARRAY ARRAY['m15', 'h1', 'h4']
  LOOP
    INSERT INTO job_definitions (
      symbol, 
      timeframe, 
      job_type, 
      enabled, 
      priority, 
      window_days
    )
    VALUES (
      v_ticker,
      v_timeframe,
      'fetch_intraday',
      true,
      v_job_priority,
      CASE v_timeframe
        WHEN 'm15' THEN 30  -- 30 days for 15-min
        WHEN 'h1' THEN 90   -- 90 days for 1-hour
        WHEN 'h4' THEN 365  -- 1 year for 4-hour
        ELSE 7
      END
    )
    ON CONFLICT (symbol, timeframe, job_type)
    DO UPDATE SET
      enabled = true,
      priority = GREATEST(job_definitions.priority, EXCLUDED.priority),
      window_days = GREATEST(job_definitions.window_days, EXCLUDED.window_days),
      updated_at = now();
  END LOOP;

  RAISE NOTICE 'Auto-created jobs for symbol % (source: %, priority: %)', v_ticker, NEW.source, v_job_priority;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_auto_create_jobs ON user_symbol_tracking;
CREATE TRIGGER trigger_auto_create_jobs
AFTER INSERT OR UPDATE ON user_symbol_tracking
FOR EACH ROW
EXECUTE FUNCTION auto_create_jobs_for_tracked_symbols();

-- ============================================================================
-- PART 3: Helper Functions for Monitoring
-- ============================================================================

-- Function to check multi-timeframe coverage for a symbol
CREATE OR REPLACE FUNCTION get_symbol_timeframe_coverage(p_symbol text)
RETURNS TABLE(
  timeframe text,
  bars_count bigint,
  earliest_bar timestamptz,
  latest_bar timestamptz,
  coverage_days numeric,
  last_fetch timestamptz,
  job_enabled boolean,
  job_priority int
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    tf.timeframe,
    COALESCE(bar_counts.cnt, 0) as bars_count,
    bar_counts.earliest,
    bar_counts.latest,
    EXTRACT(EPOCH FROM (bar_counts.latest - bar_counts.earliest)) / 86400.0 as coverage_days,
    cs.last_success_at as last_fetch,
    jd.enabled as job_enabled,
    jd.priority as job_priority
  FROM (VALUES ('m15'), ('h1'), ('h4')) AS tf(timeframe)
  LEFT JOIN (
    SELECT 
      o.timeframe,
      COUNT(*) as cnt,
      MIN(o.timestamp) as earliest,
      MAX(o.timestamp) as latest
    FROM ohlc_bars_v2 o
    JOIN symbols s ON o.symbol_id = s.id
    WHERE s.ticker = p_symbol
    GROUP BY o.timeframe
  ) bar_counts ON tf.timeframe = bar_counts.timeframe
  LEFT JOIN coverage_status cs ON cs.symbol = p_symbol AND cs.timeframe = tf.timeframe
  LEFT JOIN job_definitions jd ON jd.symbol = p_symbol AND jd.timeframe = tf.timeframe AND jd.job_type = 'fetch_intraday'
  ORDER BY 
    CASE tf.timeframe 
      WHEN 'h1' THEN 1 
      WHEN 'h4' THEN 2 
      WHEN 'm15' THEN 3 
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to get job processing stats by timeframe
CREATE OR REPLACE FUNCTION get_timeframe_job_stats(p_hours int DEFAULT 1)
RETURNS TABLE(
  timeframe text,
  total_jobs bigint,
  queued bigint,
  running bigint,
  success bigint,
  failed bigint,
  total_bars_written bigint,
  avg_duration_seconds numeric
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    jd.timeframe,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE jr.status = 'queued') as queued,
    COUNT(*) FILTER (WHERE jr.status = 'running') as running,
    COUNT(*) FILTER (WHERE jr.status = 'success') as success,
    COUNT(*) FILTER (WHERE jr.status = 'failed') as failed,
    COALESCE(SUM(jr.rows_written) FILTER (WHERE jr.status = 'success'), 0) as total_bars_written,
    AVG(EXTRACT(EPOCH FROM (jr.finished_at - jr.started_at))) FILTER (WHERE jr.status = 'success') as avg_duration_seconds
  FROM job_runs jr
  JOIN job_definitions jd ON jr.job_def_id = jd.id
  WHERE jr.created_at > now() - (p_hours || ' hours')::interval
  GROUP BY jd.timeframe
  ORDER BY 
    CASE jd.timeframe 
      WHEN 'h1' THEN 1 
      WHEN 'h4' THEN 2 
      WHEN 'm15' THEN 3 
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to get user's tracked symbols with coverage info
CREATE OR REPLACE FUNCTION get_user_tracked_symbols_status(p_user_id uuid)
RETURNS TABLE(
  symbol text,
  source text,
  priority int,
  tracked_at timestamptz,
  m15_bars bigint,
  h1_bars bigint,
  h4_bars bigint,
  jobs_pending bigint,
  jobs_running bigint
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    s.ticker as symbol,
    ust.source,
    ust.priority,
    ust.created_at as tracked_at,
    COALESCE(COUNT(*) FILTER (WHERE o.timeframe = 'm15'), 0) as m15_bars,
    COALESCE(COUNT(*) FILTER (WHERE o.timeframe = 'h1'), 0) as h1_bars,
    COALESCE(COUNT(*) FILTER (WHERE o.timeframe = 'h4'), 0) as h4_bars,
    COALESCE(COUNT(*) FILTER (WHERE jr.status = 'queued'), 0) as jobs_pending,
    COALESCE(COUNT(*) FILTER (WHERE jr.status = 'running'), 0) as jobs_running
  FROM user_symbol_tracking ust
  JOIN symbols s ON ust.symbol_id = s.id
  LEFT JOIN ohlc_bars_v2 o ON o.symbol_id = s.id AND o.timeframe IN ('m15', 'h1', 'h4')
  LEFT JOIN job_runs jr ON jr.symbol = s.ticker AND jr.status IN ('queued', 'running')
  WHERE ust.user_id = p_user_id
  GROUP BY s.ticker, ust.source, ust.priority, ust.created_at
  ORDER BY ust.priority DESC, ust.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PART 4: Enable RLS and Permissions
-- ============================================================================

ALTER TABLE user_symbol_tracking ENABLE ROW LEVEL SECURITY;

-- Users can only see their own tracked symbols
DROP POLICY IF EXISTS "Users can view own tracked symbols" ON user_symbol_tracking;
CREATE POLICY "Users can view own tracked symbols"
  ON user_symbol_tracking FOR SELECT
  USING (auth.uid() = user_id);

-- Users can insert their own tracked symbols
DROP POLICY IF EXISTS "Users can insert own tracked symbols" ON user_symbol_tracking;
CREATE POLICY "Users can insert own tracked symbols"
  ON user_symbol_tracking FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own tracked symbols
DROP POLICY IF EXISTS "Users can update own tracked symbols" ON user_symbol_tracking;
CREATE POLICY "Users can update own tracked symbols"
  ON user_symbol_tracking FOR UPDATE
  USING (auth.uid() = user_id);

-- Users can delete their own tracked symbols
DROP POLICY IF EXISTS "Users can delete own tracked symbols" ON user_symbol_tracking;
CREATE POLICY "Users can delete own tracked symbols"
  ON user_symbol_tracking FOR DELETE
  USING (auth.uid() = user_id);

-- Service role has full access
GRANT ALL ON user_symbol_tracking TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_symbol_tracking TO authenticated;

-- ============================================================================
-- PART 5: Seed Initial Multi-Timeframe Jobs for Key Symbols
-- ============================================================================

-- Create jobs for top 20 tech symbols across all timeframes
INSERT INTO job_definitions (symbol, timeframe, job_type, enabled, priority, window_days)
SELECT 
  s.ticker as symbol,
  tf.timeframe,
  'fetch_intraday' as job_type,
  true as enabled,
  CASE tf.timeframe 
    WHEN 'h1' THEN 200
    WHEN 'h4' THEN 150
    WHEN 'm15' THEN 100
  END as priority,
  CASE tf.timeframe
    WHEN 'm15' THEN 30
    WHEN 'h1' THEN 90
    WHEN 'h4' THEN 365
  END as window_days
FROM symbols s
CROSS JOIN (VALUES ('m15'), ('h1'), ('h4')) AS tf(timeframe)
WHERE s.ticker IN (
  'AAPL','MSFT','NVDA','GOOGL','TSLA','AMD','META','NFLX','ADBE','AMZN',
  'CRM','CSCO','INTC','ORCL','QCOM','TXN','AVGO','MU','AMAT','LRCX'
)
ON CONFLICT (symbol, timeframe, job_type) 
DO UPDATE SET 
  enabled = true, 
  priority = GREATEST(job_definitions.priority, EXCLUDED.priority),
  window_days = GREATEST(job_definitions.window_days, EXCLUDED.window_days),
  updated_at = now();

-- Log the seeding
DO $$
DECLARE
  v_count int;
BEGIN
  SELECT COUNT(*) INTO v_count
  FROM job_definitions
  WHERE timeframe IN ('m15', 'h1', 'h4')
    AND enabled = true;
  
  RAISE NOTICE 'Multi-timeframe jobs seeded: % active job definitions', v_count;
END $$;
