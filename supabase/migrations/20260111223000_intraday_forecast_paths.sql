CREATE TABLE IF NOT EXISTS ml_forecast_paths_intraday (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    horizon VARCHAR(10) NOT NULL,

    steps INTEGER NOT NULL,
    interval_sec INTEGER NOT NULL,

    overall_label VARCHAR(20),
    confidence NUMERIC(5,4),
    model_type VARCHAR(50),

    points JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT unique_intraday_forecast_path UNIQUE (symbol_id, timeframe, horizon, created_at)
);

CREATE INDEX IF NOT EXISTS idx_intraday_forecast_paths_symbol_tf_exp
ON ml_forecast_paths_intraday(symbol_id, timeframe, expires_at);

CREATE INDEX IF NOT EXISTS idx_intraday_forecast_paths_exp
ON ml_forecast_paths_intraday(expires_at);
