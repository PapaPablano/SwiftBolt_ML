-- Migration: Seed job definitions for 2-year intraday backfill
-- Purpose: Enable progressive backfill of historical m15/h1/h4 data from Polygon
-- Date: 2026-01-08

-- This migration creates job definitions for frequently-traded symbols
-- Orchestrator will create slices and progressively backfill 2 years of data

-- Function to seed a backfill job for a symbol
CREATE OR REPLACE FUNCTION seed_intraday_backfill_job(
  p_symbol TEXT,
  p_timeframe TEXT,
  p_window_days INT DEFAULT 730, -- 2 years
  p_priority INT DEFAULT 100
)
RETURNS UUID AS $$
DECLARE
  v_job_id UUID;
BEGIN
  INSERT INTO job_definitions (
    symbol,
    timeframe,
    job_type,
    window_days,
    priority,
    enabled
  )
  VALUES (
    p_symbol,
    p_timeframe,
    'fetch_intraday', -- Will route to Polygon for historical dates
    p_window_days,
    p_priority,
    true
  )
  ON CONFLICT (symbol, timeframe, job_type)
  DO UPDATE SET
    window_days = EXCLUDED.window_days,
    priority = EXCLUDED.priority,
    enabled = EXCLUDED.enabled,
    updated_at = now()
  RETURNING id INTO v_job_id;

  RETURN v_job_id;
END;
$$ LANGUAGE plpgsql;

-- Seed backfill jobs for top symbols (ONLY RUN ONCE per symbol)
-- Priority: Higher = more important (fetched first)
-- Start with just AAPL to test, add more symbols after validation

DO $$
DECLARE
  v_aapl_id UUID;
BEGIN
  -- AAPL: Highest priority for testing
  -- m15 timeframe: Raw 15-minute bars (will be resampled to h1/h4 by feature flags)
  SELECT seed_intraday_backfill_job('AAPL', 'm15', 730, 200) INTO v_aapl_id;

  RAISE NOTICE '✅ Created backfill job for AAPL (m15, 2 years): %', v_aapl_id;
  RAISE NOTICE '';
  RAISE NOTICE '📊 Backfill Configuration:';
  RAISE NOTICE '  - Symbol: AAPL';
  RAISE NOTICE '  - Timeframe: m15 (15-minute bars)';
  RAISE NOTICE '  - Window: 730 days (2 years)';
  RAISE NOTICE '  - Provider: Polygon (for dates before today)';
  RAISE NOTICE '  - Resampling: m15 → h1/h4 (via feature flags)';
  RAISE NOTICE '';
  RAISE NOTICE '⏱️  Estimated backfill:';
  RAISE NOTICE '  - ~196,560 m15 bars (252 trading days × 390 min/day)';
  RAISE NOTICE '  - ~40 Polygon API requests';
  RAISE NOTICE '  - ~8 minutes total (5 req/min limit)';
  RAISE NOTICE '';
  RAISE NOTICE '🔄 Next steps:';
  RAISE NOTICE '  1. Set environment variables in Supabase Dashboard:';
  RAISE NOTICE '     RESAMPLE_H1_FROM_M15=true';
  RAISE NOTICE '     RESAMPLE_H4_FROM_M15=true';
  RAISE NOTICE '  2. Apply this migration via SQL Editor';
  RAISE NOTICE '  3. Orchestrator will auto-create slices on next tick (runs every 15 min)';
  RAISE NOTICE '  4. Swift app will poll every 15s and show progress';
  RAISE NOTICE '  5. Chart updates in real-time as bars arrive';
  RAISE NOTICE '';

  -- Add more symbols here after testing AAPL:
  -- SELECT seed_intraday_backfill_job('TSLA', 'm15', 730, 190);
  -- SELECT seed_intraday_backfill_job('MSFT', 'm15', 730, 180);
  -- SELECT seed_intraday_backfill_job('GOOGL', 'm15', 730, 170);
  -- SELECT seed_intraday_backfill_job('NVDA', 'm15', 730, 160);
  -- SELECT seed_intraday_backfill_job('META', 'm15', 730, 150);
  -- SELECT seed_intraday_backfill_job('AMZN', 'm15', 730, 140);
  -- SELECT seed_intraday_backfill_job('SPY', 'm15', 730, 130);
  -- SELECT seed_intraday_backfill_job('QQQ', 'm15', 730, 120);
  -- SELECT seed_intraday_backfill_job('IWM', 'm15', 730, 110);
END $$;

COMMENT ON FUNCTION seed_intraday_backfill_job IS
'Seeds a job definition for historical intraday backfill.
Idempotent: Safe to run multiple times (updates existing jobs).
Use this to add new symbols for 2-year backfill.';
