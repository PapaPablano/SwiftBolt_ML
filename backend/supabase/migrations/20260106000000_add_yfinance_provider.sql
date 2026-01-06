-- Add 'yfinance' as an allowed provider for ohlc_bars_v2
-- This allows us to use Yahoo Finance as a data source

-- Drop the existing constraint
ALTER TABLE ohlc_bars_v2 DROP CONSTRAINT IF EXISTS ohlc_bars_v2_provider_check;

-- Add new constraint with yfinance included
ALTER TABLE ohlc_bars_v2 ADD CONSTRAINT ohlc_bars_v2_provider_check 
CHECK (provider IN ('polygon', 'tradier', 'ml_forecast', 'yfinance'));

-- Add comment
COMMENT ON CONSTRAINT ohlc_bars_v2_provider_check ON ohlc_bars_v2 IS 
'Allowed data providers: polygon (historical), tradier (intraday), ml_forecast (predictions), yfinance (historical)';
