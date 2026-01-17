DROP VIEW IF EXISTS ohlc_bars_unified;
DROP VIEW IF EXISTS provider_coverage_summary;

WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY symbol_id, timeframe, ts, provider, is_forecast
      ORDER BY fetched_at DESC NULLS LAST, updated_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM ohlc_bars_v2
)
DELETE FROM ohlc_bars_v2 o
USING ranked r
WHERE o.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_bars_v2_natural_key
  ON ohlc_bars_v2(symbol_id, timeframe, ts, provider, is_forecast);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'i'
      AND c.relname = 'idx_ohlc_bars_v2_m15_symbol_ts'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'i'
      AND c.relname = 'idx_ohlc_bars_v2_m15_lookup'
  ) THEN
    EXECUTE 'ALTER INDEX idx_ohlc_bars_v2_m15_symbol_ts RENAME TO idx_ohlc_bars_v2_m15_lookup';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_m15_lookup
  ON ohlc_bars_v2(symbol_id, ts DESC)
  WHERE timeframe = 'm15' AND is_forecast = false;

CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_timeframe_lookup
  ON ohlc_bars_v2(symbol_id, timeframe, ts DESC)
  WHERE is_forecast = false;

CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_forecast_lookup
  ON ohlc_bars_v2(symbol_id, timeframe, ts DESC)
  WHERE is_forecast = true AND provider = 'ml_forecast';

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
  timeframe::text as timeframe,
  ts,
  open,
  high,
  low,
  close,
  volume,
  provider::text as provider,
  false as is_intraday,
  false as is_forecast,
  'verified' as data_status,
  created_at as fetched_at,
  created_at,
  created_at as updated_at
FROM ohlc_bars
WHERE NOT EXISTS (
  SELECT 1 FROM ohlc_bars_v2 v2
  WHERE v2.symbol_id = ohlc_bars.symbol_id
    AND v2.timeframe = ohlc_bars.timeframe::text
    AND v2.ts = ohlc_bars.ts
);

COMMENT ON VIEW ohlc_bars_unified IS 'Unified view combining ohlc_bars_v2 and legacy ohlc_bars for backward compatibility';

CREATE OR REPLACE VIEW provider_coverage_summary AS
SELECT 
  s.ticker,
  o.timeframe,
  o.provider,
  COUNT(*) as bar_count,
  MIN(o.ts) as earliest_bar,
  MAX(o.ts) as latest_bar,
  MAX(o.fetched_at) as last_updated
FROM ohlc_bars_v2 o
JOIN symbols s ON s.id = o.symbol_id
WHERE o.is_forecast = false
GROUP BY s.ticker, o.timeframe, o.provider
ORDER BY s.ticker, o.timeframe, 
  CASE o.provider 
    WHEN 'alpaca' THEN 1 
    WHEN 'polygon' THEN 2 
    WHEN 'yfinance' THEN 3 
    ELSE 4 
  END;

COMMENT ON VIEW provider_coverage_summary IS
'Summary view showing data coverage by provider.
Use this to monitor Alpaca migration progress and identify gaps.';
