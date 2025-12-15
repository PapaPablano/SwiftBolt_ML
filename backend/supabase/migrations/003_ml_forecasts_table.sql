-- Migration: Create ml_forecasts table for storing ML predictions
-- Phase 4: ML Pipeline & Forecast Storage

-- Create ml_forecasts table
CREATE TABLE IF NOT EXISTS ml_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    horizon TEXT NOT NULL, -- '1D', '1W', '1M', etc.
    overall_label TEXT NOT NULL CHECK (overall_label IN ('Bullish', 'Neutral', 'Bearish')),
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    points JSONB NOT NULL, -- Array of forecast points: [{ts, value, lower, upper}, ...]
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one forecast per symbol per horizon
    UNIQUE(symbol_id, horizon)
);

-- Indexes
CREATE INDEX idx_ml_forecasts_symbol_id ON ml_forecasts(symbol_id);
CREATE INDEX idx_ml_forecasts_horizon ON ml_forecasts(horizon);
CREATE INDEX idx_ml_forecasts_run_at ON ml_forecasts(run_at DESC);
CREATE INDEX idx_ml_forecasts_symbol_horizon ON ml_forecasts(symbol_id, horizon);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_ml_forecasts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_ml_forecasts_updated_at
    BEFORE UPDATE ON ml_forecasts
    FOR EACH ROW
    EXECUTE FUNCTION update_ml_forecasts_updated_at();

-- Comments
COMMENT ON TABLE ml_forecasts IS 'ML-generated price forecasts for symbols';
COMMENT ON COLUMN ml_forecasts.symbol_id IS 'Reference to symbols table';
COMMENT ON COLUMN ml_forecasts.horizon IS 'Forecast time horizon (1D, 1W, 1M)';
COMMENT ON COLUMN ml_forecasts.overall_label IS 'Overall directional prediction (Bullish/Neutral/Bearish)';
COMMENT ON COLUMN ml_forecasts.confidence IS 'Model confidence score (0-1)';
COMMENT ON COLUMN ml_forecasts.points IS 'Array of forecast points with timestamps and values';
COMMENT ON COLUMN ml_forecasts.run_at IS 'When the forecast was generated';
