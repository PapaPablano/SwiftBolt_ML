-- Rollback: Remove Entry/Exit Ranking Columns
-- Created: 2026-01-23
-- Description: Reverts the entry/exit ranking migration if needed

BEGIN;

-- Drop indexes first
DROP INDEX IF EXISTS idx_options_ranks_symbol_mode_exit;
DROP INDEX IF EXISTS idx_options_ranks_symbol_mode_entry;
DROP INDEX IF EXISTS idx_options_ranks_ranking_mode;
DROP INDEX IF EXISTS idx_options_ranks_exit_rank;
DROP INDEX IF EXISTS idx_options_ranks_entry_rank;

-- Drop columns
ALTER TABLE options_ranks 
DROP COLUMN IF EXISTS time_urgency_score,
DROP COLUMN IF EXISTS deterioration_score,
DROP COLUMN IF EXISTS profit_protection_score,
DROP COLUMN IF EXISTS iv_discount_score,
DROP COLUMN IF EXISTS iv_percentile,
DROP COLUMN IF EXISTS catalyst_score,
DROP COLUMN IF EXISTS entry_value_score,
DROP COLUMN IF EXISTS exit_rank,
DROP COLUMN IF EXISTS entry_rank,
DROP COLUMN IF EXISTS ranking_mode;

-- Verify rollback
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
    
    IF col_count = 0 THEN
        RAISE NOTICE 'Rollback successful: All entry/exit ranking columns removed';
    ELSE
        RAISE WARNING 'Rollback incomplete: %s columns still exist', col_count;
    END IF;
END $$;

COMMIT;
