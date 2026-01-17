-- Migration: Copy existing data from ohlc_bars to ohlc_bars_v2
-- This migration populates ohlc_bars_v2 with historical data from the old table

-- Step 1: Copy all existing data, marking it as historical Polygon data
-- We assume all existing data is historical (not intraday or forecast)
DO $$
DECLARE
  v_validate_has_deprecated_guard BOOLEAN;
  v_has_any_v2_rows BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname = 'validate_ohlc_v2_write'
      AND pg_get_functiondef(p.oid) ILIKE '%DEPRECATED%'
  ) INTO v_validate_has_deprecated_guard;

  SELECT EXISTS (SELECT 1 FROM ohlc_bars_v2 LIMIT 1) INTO v_has_any_v2_rows;

  IF v_validate_has_deprecated_guard OR v_has_any_v2_rows THEN
    RETURN;
  END IF;

  INSERT INTO ohlc_bars_v2 (
    symbol_id,
    timeframe,
    ts,
    open,
    high,
    low,
    close,
    volume,
    provider,
    is_intraday,
    is_forecast,
    data_status,
    fetched_at,
    created_at
  )
  SELECT 
    symbol_id,
    timeframe,
    ts,
    open,
    high,
    low,
    close,
    volume,
    CASE 
      WHEN provider::text = 'massive' THEN 'polygon'
      WHEN provider::text = 'finnhub' THEN 'polygon'
      ELSE 'polygon'
    END as provider,
    false as is_intraday,
    false as is_forecast,
    'verified' as data_status,
    created_at as fetched_at,
    created_at
  FROM ohlc_bars
  WHERE DATE(ts) < CURRENT_DATE
  ON CONFLICT (symbol_id, timeframe, ts, provider, is_forecast) DO NOTHING;
END $$;

-- Step 2: Create index on old table for reference queries during transition
CREATE INDEX IF NOT EXISTS idx_ohlc_bars_migration 
  ON ohlc_bars(symbol_id, timeframe, ts DESC);

-- Step 3: Add comment documenting the migration
COMMENT ON TABLE ohlc_bars IS 'DEPRECATED: Migrated to ohlc_bars_v2. Keep for reference during transition period.';

-- Step 4: Create view for backward compatibility (optional)
CREATE OR REPLACE VIEW ohlc_bars_unified AS
SELECT 
  id,
  symbol_id,
  timeframe,
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider,
  is_intraday,
  is_forecast,
  data_status,
  fetched_at,
  created_at,
  updated_at
FROM ohlc_bars_v2
UNION ALL
SELECT 
  id,
  symbol_id,
  timeframe::text as timeframe,  -- Cast ENUM to text
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider::text as provider,  -- Cast ENUM to text
  false as is_intraday,
  false as is_forecast,
  'verified' as data_status,
  created_at as fetched_at,  -- Old table doesn't have fetched_at
  created_at,
  created_at as updated_at  -- Old table doesn't have updated_at
FROM ohlc_bars
WHERE NOT EXISTS (
  SELECT 1 FROM ohlc_bars_v2 v2
  WHERE v2.symbol_id = ohlc_bars.symbol_id
    AND v2.timeframe = ohlc_bars.timeframe::text
    AND v2.ts = ohlc_bars.ts
);

COMMENT ON VIEW ohlc_bars_unified IS 'Unified view combining ohlc_bars_v2 and legacy ohlc_bars for backward compatibility';
