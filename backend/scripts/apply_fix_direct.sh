#!/bin/bash
# Apply the database fix directly using psql
# This bypasses the migration system

set -e

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable not set"
    exit 1
fi

echo "🔧 Applying database fix directly..."

psql "$DATABASE_URL" << 'EOF'
DROP FUNCTION IF EXISTS get_chart_data_v2_dynamic(UUID, VARCHAR, INT, BOOLEAN) CASCADE;

CREATE OR REPLACE FUNCTION get_chart_data_v2_dynamic(
  p_symbol_id UUID,
  p_timeframe VARCHAR(10),
  p_max_bars INT DEFAULT 1000,
  p_include_forecast BOOLEAN DEFAULT true
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
  RETURN QUERY
  WITH recent_data AS (
    SELECT
      o.ts AS bar_ts,
      o.open, o.high, o.low, o.close, o.volume,
      o.provider, o.is_intraday, o.is_forecast,
      o.data_status, o.confidence_score,
      o.upper_band, o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.is_forecast = false
      AND o.provider IN ('alpaca', 'polygon', 'tradier', 'yfinance')
    ORDER BY o.ts DESC
    LIMIT p_max_bars
  ),
  forecast_data AS (
    SELECT
      o.ts AS bar_ts,
      o.open, o.high, o.low, o.close, o.volume,
      o.provider, o.is_intraday, o.is_forecast,
      o.data_status, o.confidence_score,
      o.upper_band, o.lower_band
    FROM ohlc_bars_v2 o
    WHERE p_include_forecast = true
      AND o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND DATE(o.ts) > CURRENT_DATE
      AND o.is_forecast = true
      AND o.provider = 'ml_forecast'
    ORDER BY o.ts ASC
    LIMIT 20
  )
  SELECT
    to_char(combined.bar_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    combined.open, combined.high, combined.low, combined.close, combined.volume, combined.provider,
    combined.is_intraday, combined.is_forecast, combined.data_status,
    combined.confidence_score, combined.upper_band, combined.lower_band
  FROM (
    SELECT * FROM recent_data
    UNION ALL
    SELECT * FROM forecast_data
  ) combined
  ORDER BY combined.bar_ts ASC;
END;
$$ LANGUAGE plpgsql;

SELECT '✅ Fix applied successfully!' as status;
EOF

echo "✅ Database fix applied!"
echo "🔄 Now rebuild your app (Cmd+B) and test"
