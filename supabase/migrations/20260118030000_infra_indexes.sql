-- Migration: Infra performance indexes for time-series + indicator cache

CREATE INDEX IF NOT EXISTS idx_ohlc_bars_v2_symbol_tf_ts
ON ohlc_bars_v2(symbol_id, timeframe, ts DESC)
WHERE is_forecast = false;

CREATE INDEX IF NOT EXISTS idx_indicator_values_symbol_tf_ts
ON indicator_values(symbol_id, timeframe, ts DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_evaluations_symbol_horizon_date
ON forecast_evaluations(symbol_id, horizon, evaluation_date DESC);
