-- Add unique constraints to prevent duplicate bars
-- This is the root cause of chart rendering issues

-- For historical and intraday data: one bar per (symbol, timestamp, timeframe, provider)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_unique_historical 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider)
WHERE is_forecast = false;

-- For forecast data: allow multiple predictions per timestamp
-- (different models can predict the same future date)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlc_unique_forecast 
ON ohlc_bars_v2 (symbol_id, ts, timeframe, provider, confidence_score)
WHERE is_forecast = true;

-- Add comment explaining the constraints
COMMENT ON INDEX idx_ohlc_unique_historical IS 
'Prevents duplicate bars for historical/intraday data. 
Each symbol+timestamp+timeframe+provider combination must be unique.';

COMMENT ON INDEX idx_ohlc_unique_forecast IS 
'Allows multiple forecast predictions per timestamp (different confidence scores).';
