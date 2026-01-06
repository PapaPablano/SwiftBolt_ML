-- Migration: Seed ohlc_bars_v2 with historical data from legacy ohlc_bars table
-- This populates the new layered architecture with existing historical data

-- Insert historical data from ohlc_bars into ohlc_bars_v2
-- Only insert data for dates before today (historical data from Polygon)
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
  created_at
)
SELECT
  ob.symbol_id,
  ob.timeframe,
  ob.ts,
  ob.open,
  ob.high,
  ob.low,
  ob.close,
  ob.volume,
  'polygon' AS provider,
  false AS is_intraday,
  false AS is_forecast,
  'verified' AS data_status,
  now()
FROM ohlc_bars ob
WHERE DATE(ob.ts) < CURRENT_DATE
ON CONFLICT (symbol_id, timeframe, ts, provider, is_forecast) DO NOTHING;
