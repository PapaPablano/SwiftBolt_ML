ALTER TABLE options_ranks
ADD COLUMN IF NOT EXISTS ranking_mode TEXT DEFAULT 'entry';

ALTER TABLE options_ranks
ADD COLUMN IF NOT EXISTS relative_value_score DOUBLE PRECISION;

ALTER TABLE options_ranks
ADD COLUMN IF NOT EXISTS entry_difficulty_score DOUBLE PRECISION;

ALTER TABLE options_ranks
ADD COLUMN IF NOT EXISTS ranking_stability_score DOUBLE PRECISION;

UPDATE options_ranks
SET ranking_mode = 'entry'
WHERE ranking_mode IS NULL;

DROP INDEX IF EXISTS idx_options_ranks_unique;

CREATE UNIQUE INDEX IF NOT EXISTS idx_options_ranks_unique
ON options_ranks(underlying_symbol_id, ranking_mode, expiry, strike, side);

CREATE INDEX IF NOT EXISTS idx_options_ranks_mode
ON options_ranks(ranking_mode);

CREATE INDEX IF NOT EXISTS idx_options_ranks_symbol_mode_run_at
ON options_ranks(underlying_symbol_id, ranking_mode, run_at DESC);
