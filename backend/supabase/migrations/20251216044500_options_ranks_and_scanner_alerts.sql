-- Migration: Enhance options_ranks and create scanner_alerts tables
-- Phase 6: Options Ranker & Scanner

-- Add missing columns to existing options_ranks table
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS contract_symbol TEXT;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS theta NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS vega NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS rho NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS bid NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS ask NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS mark NUMERIC;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS last_price NUMERIC;

-- Add new indexes for options_ranks
CREATE INDEX IF NOT EXISTS idx_options_ranks_run_at ON options_ranks(run_at DESC);
CREATE INDEX IF NOT EXISTS idx_options_ranks_underlying_score ON options_ranks(underlying_symbol_id, ml_score DESC);

-- Comments for options_ranks
COMMENT ON TABLE options_ranks IS 'ML-scored and ranked option contracts';
COMMENT ON COLUMN options_ranks.underlying_symbol_id IS 'Reference to underlying symbol';
COMMENT ON COLUMN options_ranks.ml_score IS 'ML-generated favorability score (0-1, higher is better)';
COMMENT ON COLUMN options_ranks.run_at IS 'When the ML scoring job ran';

-- Enhance scanner_alerts table for Phase 6
ALTER TABLE scanner_alerts ADD COLUMN IF NOT EXISTS condition_type TEXT;
ALTER TABLE scanner_alerts ADD COLUMN IF NOT EXISTS details JSONB;
ALTER TABLE scanner_alerts ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE;
ALTER TABLE scanner_alerts ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Rename dismissed to is_read if it exists (existing column uses "dismissed")
-- Note: We'll use the existing "dismissed" column as "is_read" semantically

-- Add new indexes for scanner_alerts
CREATE INDEX IF NOT EXISTS idx_scanner_alerts_condition_type ON scanner_alerts(condition_type);
CREATE INDEX IF NOT EXISTS idx_scanner_alerts_is_read ON scanner_alerts(is_read);

-- Comments for scanner_alerts
COMMENT ON TABLE scanner_alerts IS 'Scanner alerts triggered for watchlist symbols';
COMMENT ON COLUMN scanner_alerts.condition_label IS 'Human-readable condition that triggered the alert';
COMMENT ON COLUMN scanner_alerts.severity IS 'Alert importance level (info/warning/critical)';
