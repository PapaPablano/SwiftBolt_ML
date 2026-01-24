-- Verify Entry/Exit Ranking Migration
-- Run this after applying the migration to confirm everything is set up correctly

-- Check if all columns exist
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'options_ranks'
AND column_name IN (
    'ranking_mode', 'entry_rank', 'exit_rank',
    'entry_value_score', 'catalyst_score',
    'profit_protection_score', 'deterioration_score', 'time_urgency_score',
    'iv_percentile', 'iv_discount_score'
)
ORDER BY ordinal_position;

-- Check if indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'options_ranks'
AND indexname LIKE '%entry%' OR indexname LIKE '%exit%' OR indexname LIKE '%mode%'
ORDER BY indexname;

-- Check constraints
SELECT
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    pg_get_constraintdef(con.oid) AS constraint_definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
WHERE rel.relname = 'options_ranks'
AND con.conname LIKE '%ranking_mode%';

-- Sample data check (if any rankings exist)
SELECT 
    ranking_mode,
    COUNT(*) as count,
    COUNT(entry_rank) as entry_ranks,
    COUNT(exit_rank) as exit_ranks,
    COUNT(composite_rank) as monitor_ranks,
    AVG(entry_rank) as avg_entry,
    AVG(exit_rank) as avg_exit,
    AVG(composite_rank) as avg_monitor
FROM options_ranks
GROUP BY ranking_mode
ORDER BY ranking_mode;

-- Check for any NULL ranks by mode (should have ranks for their mode)
SELECT 
    ranking_mode,
    COUNT(*) FILTER (WHERE entry_rank IS NULL AND ranking_mode = 'entry') as missing_entry_ranks,
    COUNT(*) FILTER (WHERE exit_rank IS NULL AND ranking_mode = 'exit') as missing_exit_ranks,
    COUNT(*) FILTER (WHERE composite_rank IS NULL AND ranking_mode = 'monitor') as missing_monitor_ranks
FROM options_ranks
GROUP BY ranking_mode;

-- Verify column comments
SELECT 
    col_description(c.oid, cols.ordinal_position) as column_comment,
    cols.column_name
FROM information_schema.columns cols
JOIN pg_class c ON c.relname = cols.table_name
WHERE cols.table_name = 'options_ranks'
AND cols.column_name IN ('ranking_mode', 'entry_rank', 'exit_rank')
ORDER BY cols.ordinal_position;
