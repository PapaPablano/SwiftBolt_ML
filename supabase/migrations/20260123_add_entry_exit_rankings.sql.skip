-- Migration: Add Entry/Exit Ranking Columns
-- Created: 2026-01-23
-- Description: Adds columns for entry_rank, exit_rank, and mode-specific component scores

BEGIN;

-- Add ranking mode column (entry, exit, monitor)
ALTER TABLE options_ranks 
ADD COLUMN IF NOT EXISTS ranking_mode TEXT DEFAULT 'monitor' CHECK (ranking_mode IN ('entry', 'exit', 'monitor'));

-- Add mode-specific rank columns
ALTER TABLE options_ranks 
ADD COLUMN IF NOT EXISTS entry_rank NUMERIC,
ADD COLUMN IF NOT EXISTS exit_rank NUMERIC;

-- Add ENTRY mode component scores
ALTER TABLE options_ranks 
ADD COLUMN IF NOT EXISTS entry_value_score NUMERIC,
ADD COLUMN IF NOT EXISTS catalyst_score NUMERIC,
ADD COLUMN IF NOT EXISTS iv_percentile NUMERIC,
ADD COLUMN IF NOT EXISTS iv_discount_score NUMERIC;

-- Add EXIT mode component scores
ALTER TABLE options_ranks 
ADD COLUMN IF NOT EXISTS profit_protection_score NUMERIC,
ADD COLUMN IF NOT EXISTS deterioration_score NUMERIC,
ADD COLUMN IF NOT EXISTS time_urgency_score NUMERIC;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_options_ranks_entry_rank ON options_ranks(entry_rank DESC) WHERE entry_rank IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_options_ranks_exit_rank ON options_ranks(exit_rank DESC) WHERE exit_rank IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_options_ranks_ranking_mode ON options_ranks(ranking_mode);

-- Add composite index for common query patterns (symbol + mode + rank)
CREATE INDEX IF NOT EXISTS idx_options_ranks_symbol_mode_entry 
ON options_ranks(underlying_symbol_id, ranking_mode, entry_rank DESC) 
WHERE ranking_mode = 'entry' AND entry_rank IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_options_ranks_symbol_mode_exit 
ON options_ranks(underlying_symbol_id, ranking_mode, exit_rank DESC) 
WHERE ranking_mode = 'exit' AND exit_rank IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN options_ranks.ranking_mode IS 'Ranking optimization mode: entry (find buys), exit (detect sells), or monitor (balanced)';
COMMENT ON COLUMN options_ranks.entry_rank IS 'Entry-optimized rank 0-100: Value 40%, Catalyst 35%, Greeks 25%';
COMMENT ON COLUMN options_ranks.exit_rank IS 'Exit-optimized rank 0-100: Profit 50%, Deterioration 30%, Time 20%';
COMMENT ON COLUMN options_ranks.entry_value_score IS 'Entry value score: IV percentile 40%, IV discount 30%, Spread 30%';
COMMENT ON COLUMN options_ranks.catalyst_score IS 'Catalyst score: Price momentum 40%, Volume surge 35%, OI build 25%';
COMMENT ON COLUMN options_ranks.profit_protection_score IS 'Profit protection: P&L% 50%, IV expansion 30%, Target hit 20%';
COMMENT ON COLUMN options_ranks.deterioration_score IS 'Deterioration: Momentum decay 40%, Volume drop 30%, OI stall 30%';
COMMENT ON COLUMN options_ranks.time_urgency_score IS 'Time urgency: DTE urgency 60%, Theta burn 40%';

-- Verify the changes
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'options_ranks'
    AND column_name IN (
        'ranking_mode', 'entry_rank', 'exit_rank',
        'entry_value_score', 'catalyst_score',
        'profit_protection_score', 'deterioration_score', 'time_urgency_score'
    );
    
    IF col_count = 8 THEN
        RAISE NOTICE 'Migration successful: All 8 columns added to options_ranks';
    ELSE
        RAISE WARNING 'Migration incomplete: Expected 8 columns, found %', col_count;
    END IF;
END $$;

COMMIT;

-- Usage notes:
-- 1. MONITOR mode (default): Uses composite_rank, momentum_score, value_score, greeks_score
-- 2. ENTRY mode: Uses entry_rank, entry_value_score, catalyst_score, greeks_score
-- 3. EXIT mode: Uses exit_rank, profit_protection_score, deterioration_score, time_urgency_score
--
-- Example queries:
-- -- Get top entry opportunities
-- SELECT * FROM options_ranks 
-- WHERE underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
--   AND ranking_mode = 'entry'
--   AND expiry >= CURRENT_DATE
-- ORDER BY entry_rank DESC
-- LIMIT 20;
--
-- -- Get exit signals for owned positions
-- SELECT * FROM options_ranks 
-- WHERE underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
--   AND ranking_mode = 'exit'
--   AND exit_rank > 70
-- ORDER BY exit_rank DESC;
