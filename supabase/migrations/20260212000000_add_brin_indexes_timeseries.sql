-- PostgreSQL Best Practices: BRIN indexes for time-series tables
-- Migration: 20260212000000_add_brin_indexes_timeseries.sql
-- Reference: .cursor/rules/supabase-postgres-best-practices.mdc
--
-- BRIN indexes are 10-100x smaller than B-tree for large time-series tables.
-- Use CONCURRENTLY in production if tables are very large (run outside migration).
-- Standard CREATE INDEX is used here (Supabase migrations run in transaction).

CREATE INDEX IF NOT EXISTS idx_ohlc_v2_ts_brin
ON ohlc_bars_v2 USING brin (ts);

CREATE INDEX IF NOT EXISTS idx_ohlc_h4_ts_brin
ON ohlc_bars_h4_alpaca USING brin (ts);

CREATE INDEX IF NOT EXISTS idx_indicator_values_ts_brin
ON indicator_values USING brin (ts);

CREATE INDEX IF NOT EXISTS idx_options_price_history_snapshot_brin
ON options_price_history USING brin (snapshot_at);

-- ml_forecasts_intraday: created_at for time-ordered queries
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_intraday_created_brin
ON ml_forecasts_intraday USING brin (created_at);

COMMENT ON INDEX idx_ohlc_v2_ts_brin IS 'BRIN for time-series range scans on ohlc_bars_v2';
COMMENT ON INDEX idx_ohlc_h4_ts_brin IS 'BRIN for time-series range scans on ohlc_bars_h4_alpaca';
COMMENT ON INDEX idx_indicator_values_ts_brin IS 'BRIN for time-series range scans on indicator_values';
COMMENT ON INDEX idx_options_price_history_snapshot_brin IS 'BRIN for time-series range scans on options_price_history';
COMMENT ON INDEX idx_ml_forecasts_intraday_created_brin IS 'BRIN for time-ordered queries on ml_forecasts_intraday';
