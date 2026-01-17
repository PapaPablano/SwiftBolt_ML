-- Migration: Comprehensive Intraday Backfill System Improvements
-- Implements recommended architecture for durable 2-year intraday backfills
-- Date: 2026-01-09

-- ============================================================================
-- PART A: Enhanced Indexing and Constraints
-- ============================================================================

-- Add composite unique index on ohlc_bars_v2 to prevent duplicates
-- This already exists from the UNIQUE constraint, but we ensure it's optimized
CREATE INDEX IF NOT EXISTS idx_ohlc_v2_intraday_query 
ON ohlc_bars_v2(symbol_id, timeframe, provider, ts DESC) 
WHERE is_forecast = false;

-- Index for backfill_chunks worker queries with SKIP LOCKED optimization
CREATE INDEX IF NOT EXISTS idx_backfill_chunks_claim 
ON backfill_chunks(status, day ASC) 
WHERE status = 'pending';

-- Add symbol_id column to backfill_chunks if missing (for consistency)
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'backfill_chunks' AND column_name = 'symbol_id'
  ) THEN
    ALTER TABLE backfill_chunks ADD COLUMN symbol_id UUID;
  END IF;
END $$;

-- ============================================================================
-- PART B: Seed 2-Year Intraday Backfill Jobs
-- ============================================================================

CREATE OR REPLACE FUNCTION seed_intraday_backfill_2yr(
  p_ticker TEXT,
  p_timeframe TEXT DEFAULT 'h1'
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_symbol_id UUID;
  v_job_id UUID;
  v_from_ts TIMESTAMPTZ;
  v_to_ts TIMESTAMPTZ;
  v_current_day DATE;
  v_chunk_count INT := 0;
BEGIN
  -- Get symbol_id
  SELECT id INTO v_symbol_id FROM symbols WHERE ticker = p_ticker;
  IF v_symbol_id IS NULL THEN
    RAISE EXCEPTION 'Symbol % not found', p_ticker;
  END IF;

  -- Set date range: 2 years back to yesterday (exclude today for historical)
  v_to_ts := (CURRENT_DATE - INTERVAL '1 day')::TIMESTAMPTZ;
  v_from_ts := (CURRENT_DATE - INTERVAL '2 years')::TIMESTAMPTZ;

  -- Create or update backfill job
  INSERT INTO backfill_jobs (symbol, symbol_id, timeframe, from_ts, to_ts, status)
  VALUES (p_ticker, v_symbol_id, p_timeframe, v_from_ts, v_to_ts, 'pending')
  ON CONFLICT (symbol, timeframe, from_ts, to_ts) 
  DO UPDATE SET 
    status = CASE 
      WHEN backfill_jobs.status = 'error' THEN 'pending'
      ELSE backfill_jobs.status 
    END,
    updated_at = NOW()
  RETURNING id INTO v_job_id;

  -- Fan out into daily chunks (only market days)
  v_current_day := v_from_ts::DATE;
  WHILE v_current_day <= v_to_ts::DATE LOOP
    -- Only create chunks for weekdays (Monday=1 to Friday=5)
    IF EXTRACT(DOW FROM v_current_day) BETWEEN 1 AND 5 THEN
      INSERT INTO backfill_chunks (job_id, symbol, symbol_id, timeframe, day, status)
      VALUES (v_job_id, p_ticker, v_symbol_id, p_timeframe, v_current_day, 'pending')
      ON CONFLICT (job_id, day) DO NOTHING;
      v_chunk_count := v_chunk_count + 1;
    END IF;
    v_current_day := v_current_day + INTERVAL '1 day';
  END LOOP;

  RAISE NOTICE 'Created job % with % chunks for % (%)', v_job_id, v_chunk_count, p_ticker, p_timeframe;
  RETURN v_job_id;
END;
$$;

COMMENT ON FUNCTION seed_intraday_backfill_2yr IS 
'Seeds a 2-year historical intraday backfill job with daily chunks for market days only';

-- ============================================================================
-- PART B2: Chunk Claiming Function for Worker
-- ============================================================================

CREATE OR REPLACE FUNCTION claim_backfill_chunk(p_limit INT DEFAULT 1)
RETURNS TABLE (
  id UUID,
  job_id UUID,
  symbol TEXT,
  symbol_id UUID,
  timeframe TEXT,
  day DATE,
  status TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE backfill_chunks
  SET 
    status = 'in_progress',
    updated_at = NOW()
  WHERE backfill_chunks.id IN (
    SELECT backfill_chunks.id
    FROM backfill_chunks
    WHERE backfill_chunks.status = 'pending'
    ORDER BY backfill_chunks.day ASC
    LIMIT p_limit
    FOR UPDATE SKIP LOCKED
  )
  RETURNING 
    backfill_chunks.id,
    backfill_chunks.job_id,
    backfill_chunks.symbol,
    backfill_chunks.symbol_id,
    backfill_chunks.timeframe,
    backfill_chunks.day,
    backfill_chunks.status;
END;
$$;

COMMENT ON FUNCTION claim_backfill_chunk IS
'Claims pending backfill chunks for processing using SKIP LOCKED for parallel workers';

-- ============================================================================
-- PART C: Update get_chart_data_v2 to Handle All Data Statuses
-- ============================================================================

DROP FUNCTION IF EXISTS get_chart_data_v2 CASCADE;

CREATE FUNCTION get_chart_data_v2(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_start_date TIMESTAMP WITH TIME ZONE,
  p_end_date TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
  ts TEXT,
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  provider VARCHAR(20),
  is_intraday BOOLEAN,
  is_forecast BOOLEAN,
  data_status VARCHAR(20),
  confidence_score DECIMAL(3, 2),
  upper_band DECIMAL(10, 4),
  lower_band DECIMAL(10, 4)
) AS $$
BEGIN
  -- For intraday timeframes (m15/h1/h4), query ohlc_bars_v2 where Polygon stores historical data
  IF p_timeframe IN ('m15', 'h1', 'h4') THEN
    RETURN QUERY
    WITH combined_data AS (
      -- Historical intraday from Polygon (ohlc_bars_v2)
      -- Include ALL data_status values (verified, live, provisional)
      SELECT 
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        o.volume,
        o.provider,
        (DATE(o.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE)::BOOLEAN as is_intraday,
        o.is_forecast,
        o.data_status,
        o.confidence_score,
        o.upper_band,
        o.lower_band
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id 
        AND o.timeframe = p_timeframe
        AND o.ts >= p_start_date 
        AND o.ts <= p_end_date
        AND o.provider = 'polygon'
        AND o.is_forecast = false
      
      UNION ALL
      
      -- Today's real-time data from Tradier (intraday_bars) - only for m15
      SELECT 
        ib.ts,
        ib.open::DECIMAL(10,4),
        ib.high::DECIMAL(10,4),
        ib.low::DECIMAL(10,4),
        ib.close::DECIMAL(10,4),
        ib.volume::BIGINT,
        'tradier'::VARCHAR(20) as provider,
        true::BOOLEAN as is_intraday,
        false::BOOLEAN as is_forecast,
        'live'::VARCHAR(20) as data_status,
        NULL::DECIMAL(3,2) as confidence_score,
        NULL::DECIMAL(10,4) as upper_band,
        NULL::DECIMAL(10,4) as lower_band
      FROM intraday_bars ib
      WHERE ib.symbol_id = p_symbol_id 
        AND ib.timeframe = '15m'
        AND ib.ts >= p_start_date 
        AND ib.ts <= p_end_date
        AND DATE(ib.ts AT TIME ZONE 'America/New_York') = CURRENT_DATE
        AND p_timeframe = 'm15'
    )
    SELECT 
      to_char(cd.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      cd.open,
      cd.high,
      cd.low,
      cd.close,
      cd.volume,
      cd.provider,
      cd.is_intraday,
      cd.is_forecast,
      cd.data_status,
      cd.confidence_score,
      cd.upper_band,
      cd.lower_band
    FROM combined_data cd
    ORDER BY cd.ts ASC;
  
  -- For daily/weekly timeframes (d1/w1), use existing logic
  ELSE
    RETURN QUERY
    WITH deduplicated AS (
      SELECT o.*, ROW_NUMBER() OVER (
        PARTITION BY DATE(o.ts), o.is_forecast, o.is_intraday
        ORDER BY CASE WHEN o.provider = 'yfinance' THEN 1 WHEN o.provider = 'polygon' THEN 2 ELSE 3 END,
        o.ts DESC, o.fetched_at DESC NULLS LAST
      ) as rn
      FROM ohlc_bars_v2 o
      WHERE o.symbol_id = p_symbol_id AND o.timeframe = p_timeframe
        AND o.ts >= p_start_date AND o.ts <= p_end_date
        AND ((DATE(o.ts) < CURRENT_DATE AND o.is_forecast = false AND o.provider IN ('yfinance', 'polygon'))
          OR (DATE(o.ts) = CURRENT_DATE AND o.is_intraday = true AND o.provider = 'tradier')
          OR (DATE(o.ts) > CURRENT_DATE AND o.is_forecast = true AND o.provider = 'ml_forecast'))
    )
    SELECT to_char(d.ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')::TEXT,
      d.open, d.high, d.low, d.close, d.volume, d.provider,
      d.is_intraday, d.is_forecast, d.data_status, d.confidence_score, d.upper_band, d.lower_band
    FROM deduplicated d WHERE d.rn = 1 ORDER BY d.ts ASC;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_chart_data_v2 IS
'Returns chart data with proper data source routing and ALL data_status values.
For intraday timeframes (m15/h1/h4):
  - Historical data: Queries ohlc_bars_v2 WHERE provider=polygon (all statuses: verified, live, provisional)
  - Today data: Queries intraday_bars (Tradier real-time)
For daily/weekly timeframes (d1/w1):
  - Uses deduplication logic with provider priority
Properly classifies is_intraday based on DATE(ts) = CURRENT_DATE.';

-- ============================================================================
-- PART D: Seed Initial Jobs for Priority Symbols
-- ============================================================================

-- Seed 2-year backfill jobs for common symbols
DO $$
DECLARE
  v_symbols TEXT[] := ARRAY['AAPL', 'NVDA', 'TSLA', 'SPY', 'QQQ'];
  v_symbol TEXT;
BEGIN
  FOREACH v_symbol IN ARRAY v_symbols
  LOOP
    BEGIN
      PERFORM seed_intraday_backfill_2yr(v_symbol, 'h1');
      RAISE NOTICE 'Seeded 2yr backfill for %', v_symbol;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Skipped % (may not exist in symbols table): %', v_symbol, SQLERRM;
    END;
  END LOOP;
END $$;
