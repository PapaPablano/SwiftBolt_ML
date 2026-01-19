-- Migration: Add forecast validation metrics table

CREATE TABLE IF NOT EXISTS forecast_validation_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE SET NULL,
    horizon TEXT,
    scope TEXT NOT NULL DEFAULT 'global',
    lookback_days INTEGER NOT NULL DEFAULT 90,
    quality_grade TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_validation_metrics_symbol
    ON forecast_validation_metrics(symbol_id);
CREATE INDEX IF NOT EXISTS idx_forecast_validation_metrics_horizon
    ON forecast_validation_metrics(horizon);
CREATE INDEX IF NOT EXISTS idx_forecast_validation_metrics_scope
    ON forecast_validation_metrics(scope);
CREATE INDEX IF NOT EXISTS idx_forecast_validation_metrics_time
    ON forecast_validation_metrics(computed_at DESC);
