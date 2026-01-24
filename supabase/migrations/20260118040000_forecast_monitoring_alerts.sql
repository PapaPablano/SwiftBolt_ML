-- Migration: Forecast monitoring alerts for drift/accuracy

CREATE TABLE IF NOT EXISTS forecast_monitoring_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    horizon TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_forecast_monitoring_alerts_symbol
ON forecast_monitoring_alerts(symbol_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_monitoring_alerts_type
ON forecast_monitoring_alerts(alert_type, created_at DESC);
