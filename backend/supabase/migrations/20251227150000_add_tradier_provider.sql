-- Migration: Add Tradier as a data provider
-- Tradier provides options data, quotes, and historical OHLCV

-- Add 'tradier' to data_provider enum
ALTER TYPE data_provider ADD VALUE IF NOT EXISTS 'tradier';

-- Comment
COMMENT ON TYPE data_provider IS 'Data provider sources: finnhub, massive, tradier';
