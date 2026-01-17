-- Add missing indicator columns to indicator_values table
-- These columns are referenced in the ML code but were missing from the schema

-- Add rsi_14 column (RSI with 14-period calculation)
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS rsi_14 double precision;

-- Add index for better query performance on rsi_14
CREATE INDEX IF NOT EXISTS idx_indicator_values_rsi_14 ON indicator_values (rsi_14) WHERE rsi_14 IS NOT NULL;

-- Also add any other indicator columns that might be referenced
-- (Checking for common technical indicators that might be used)

-- Stochastic oscillators
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS stoch_k double precision;
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS stoch_d double precision;

-- Williams %R
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS williams_r double precision;

-- CCI (Commodity Channel Index)
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS cci double precision;

-- MFI (Money Flow Index)
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS mfi double precision;

-- OBV (On-Balance Volume)
ALTER TABLE indicator_values ADD COLUMN IF NOT EXISTS obv double precision;

-- Additional indexes for performance
CREATE INDEX IF NOT EXISTS idx_indicator_values_stoch_k ON indicator_values (stoch_k) WHERE stoch_k IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_indicator_values_stoch_d ON indicator_values (stoch_d) WHERE stoch_d IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_indicator_values_williams_r ON indicator_values (williams_r) WHERE williams_r IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_indicator_values_cci ON indicator_values (cci) WHERE cci IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_indicator_values_mfi ON indicator_values (mfi) WHERE mfi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_indicator_values_obv ON indicator_values (obv) WHERE obv IS NOT NULL;

-- Update RLS policies if needed (the existing policies should cover these new columns)
-- No additional RLS policies needed as they use SELECT ALL
