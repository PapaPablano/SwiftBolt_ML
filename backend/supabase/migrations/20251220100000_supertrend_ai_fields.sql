-- Migration: Add SuperTrend AI fields to ml_forecasts table
-- Date: 2024-12-20
-- Description: Adds columns for SuperTrend AI indicator data including
--              optimal factor, performance metrics, signals, and confidence scores

-- Add SuperTrend AI columns to ml_forecasts table
ALTER TABLE ml_forecasts 
ADD COLUMN IF NOT EXISTS supertrend_factor DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS supertrend_performance DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS supertrend_signal INTEGER,
ADD COLUMN IF NOT EXISTS trend_label VARCHAR(10),
ADD COLUMN IF NOT EXISTS trend_confidence INTEGER,
ADD COLUMN IF NOT EXISTS stop_level DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS target_price DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS trend_duration_bars INTEGER;

-- Add comments for documentation
COMMENT ON COLUMN ml_forecasts.supertrend_factor IS 
    'Optimal ATR multiplier from K-means clustering (1.0-5.0)';
COMMENT ON COLUMN ml_forecasts.supertrend_performance IS 
    'Performance index (0-1) measuring signal quality';
COMMENT ON COLUMN ml_forecasts.supertrend_signal IS 
    'Current signal: 1=BUY, -1=SELL, 0=HOLD';
COMMENT ON COLUMN ml_forecasts.trend_label IS 
    'Current trend direction: BULLISH or BEARISH';
COMMENT ON COLUMN ml_forecasts.trend_confidence IS 
    'Confidence score (0-10) for current signal';
COMMENT ON COLUMN ml_forecasts.stop_level IS 
    'Current SuperTrend trailing stop level';
COMMENT ON COLUMN ml_forecasts.target_price IS 
    'Calculated take-profit target based on risk:reward';
COMMENT ON COLUMN ml_forecasts.trend_duration_bars IS 
    'Number of bars since last trend change';

-- Create index for efficient querying of active signals
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_supertrend_signal 
ON ml_forecasts(symbol, supertrend_signal) 
WHERE supertrend_signal IS NOT NULL AND supertrend_signal != 0;

-- Create index for trend filtering
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_trend_label 
ON ml_forecasts(symbol, trend_label) 
WHERE trend_label IS NOT NULL;

-- Optional: Create a dedicated table for signal history with full metadata
-- This allows tracking historical signals without bloating ml_forecasts
CREATE TABLE IF NOT EXISTS supertrend_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    signal_date TIMESTAMPTZ NOT NULL,
    signal_type VARCHAR(4) NOT NULL CHECK (signal_type IN ('BUY', 'SELL')),
    entry_price DOUBLE PRECISION NOT NULL,
    stop_level DOUBLE PRECISION NOT NULL,
    target_price DOUBLE PRECISION,
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 10),
    atr_at_signal DOUBLE PRECISION,
    factor_used DOUBLE PRECISION,
    performance_index DOUBLE PRECISION,
    risk_amount DOUBLE PRECISION,
    reward_amount DOUBLE PRECISION,
    -- Outcome tracking (updated after signal closes)
    outcome VARCHAR(10) CHECK (outcome IN ('WIN', 'LOSS', 'OPEN', NULL)),
    exit_price DOUBLE PRECISION,
    exit_date TIMESTAMPTZ,
    pnl_percent DOUBLE PRECISION,
    pnl_amount DOUBLE PRECISION,
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_signal UNIQUE (symbol, signal_date, signal_type)
);

-- Create indexes for supertrend_signals table
CREATE INDEX IF NOT EXISTS idx_supertrend_signals_symbol 
ON supertrend_signals(symbol, signal_date DESC);

CREATE INDEX IF NOT EXISTS idx_supertrend_signals_outcome 
ON supertrend_signals(outcome) 
WHERE outcome IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_supertrend_signals_open 
ON supertrend_signals(symbol) 
WHERE outcome = 'OPEN' OR outcome IS NULL;

-- Enable RLS on supertrend_signals
ALTER TABLE supertrend_signals ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for supertrend_signals (read-only for authenticated users)
CREATE POLICY "Allow authenticated read access to supertrend_signals"
ON supertrend_signals
FOR SELECT
TO authenticated
USING (true);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_supertrend_signals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_supertrend_signals_updated_at 
ON supertrend_signals;

CREATE TRIGGER trigger_supertrend_signals_updated_at
BEFORE UPDATE ON supertrend_signals
FOR EACH ROW
EXECUTE FUNCTION update_supertrend_signals_updated_at();

-- Create a view for easy access to latest signals per symbol
CREATE OR REPLACE VIEW latest_supertrend_signals AS
SELECT DISTINCT ON (symbol)
    id,
    symbol,
    signal_date,
    signal_type,
    entry_price,
    stop_level,
    target_price,
    confidence,
    outcome,
    pnl_percent
FROM supertrend_signals
ORDER BY symbol, signal_date DESC;

-- Grant access to the view
GRANT SELECT ON latest_supertrend_signals TO authenticated;
GRANT SELECT ON latest_supertrend_signals TO anon;
