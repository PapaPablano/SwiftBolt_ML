-- Migration: Add price adjustment tracking to ohlc_bars table
-- This tracks whether prices are adjusted for splits/dividends
-- Created: 2026-01-05

-- Add adjustment tracking column
ALTER TABLE ohlc_bars 
ADD COLUMN IF NOT EXISTS is_adjusted BOOLEAN DEFAULT false;

-- Add index for querying by adjustment status
CREATE INDEX IF NOT EXISTS idx_ohlc_bars_adjusted 
ON ohlc_bars(symbol_id, timeframe, is_adjusted);

-- Add comment explaining the column
COMMENT ON COLUMN ohlc_bars.is_adjusted IS 
'Indicates if prices are adjusted for splits/dividends. false = actual historical trading prices, true = retroactively adjusted prices';

-- Update existing data to mark as adjusted (old data from Polygon with adjusted=true)
UPDATE ohlc_bars 
SET is_adjusted = true 
WHERE provider = 'massive' 
AND is_adjusted IS NULL;

-- Add constraint to ensure provider is set when is_adjusted is set
ALTER TABLE ohlc_bars 
ADD CONSTRAINT check_provider_with_adjustment 
CHECK (
  (is_adjusted IS NULL) OR 
  (is_adjusted IS NOT NULL AND provider IS NOT NULL)
);
