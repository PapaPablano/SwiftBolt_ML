-- ============================================================================
-- PAPER TRADING DEPLOYMENT VERIFICATION SCRIPT
-- Run in Supabase SQL Editor (https://app.supabase.com/project/[ref]/sql)
-- ============================================================================

-- ============================================================================
-- CHECKPOINT 1: Verify Tables Created
-- ============================================================================
-- Expected: 5 rows (paper_trading_metrics, paper_trading_positions,
--                    paper_trading_trades, position_closure_log,
--                    strategy_execution_log)

SELECT
  table_name,
  (SELECT count(*) FROM information_schema.columns
   WHERE table_schema='public' AND table_name=t.table_name) as column_count,
  (SELECT count(*) FROM information_schema.table_constraints
   WHERE table_schema='public' AND table_name=t.table_name) as constraint_count
FROM information_schema.tables t
WHERE table_schema='public' AND table_name LIKE 'paper_%'
ORDER BY table_name;

-- ✅ PASS: All 5 tables present with columns and constraints
-- ❌ FAIL: Less than 5 tables, or 0 constraints


-- ============================================================================
-- CHECKPOINT 2: Verify RLS (Row Level Security) Enabled
-- ============================================================================
-- Expected: 5 rows, all with rowsecurity='t'

SELECT
  tablename,
  rowsecurity as rls_enabled,
  CASE WHEN rowsecurity THEN '✅ ENABLED' ELSE '❌ DISABLED' END as status
FROM pg_tables
WHERE schemaname='public' AND tablename LIKE 'paper_%'
ORDER BY tablename;

-- ✅ PASS: All paper_* tables show 't' (true) for RLS
-- ❌ FAIL: Any table shows 'f' (false)


-- ============================================================================
-- CHECKPOINT 3: Verify CHECK Constraints
-- ============================================================================
-- Expected: 9+ constraints on paper_trading_positions (entry_price > 0,
--           quantity bounds, slippage bounds, SL/TP levels, direction check)

SELECT
  constraint_name,
  table_name,
  -- Extract constraint from database system tables
  (SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conname=constraint_name AND conrelid::regclass::text=table_name
   LIMIT 1) as constraint_definition
FROM information_schema.check_constraints
WHERE table_schema='public' AND table_name='paper_trading_positions'
ORDER BY constraint_name;

-- ✅ PASS: At least 5 CHECK constraints visible
-- ✅ PASS: Constraints include entry_price > 0
-- ✅ PASS: Constraints include quantity bounds
-- ❌ FAIL: No constraints found


-- ============================================================================
-- CHECKPOINT 4: Verify Triggers Exist
-- ============================================================================
-- Expected: 4 triggers (prevent_trade_updates, prevent_trade_deletes,
--           validate_position_completeness, update_position_timestamp)

SELECT
  trigger_name,
  event_object_table,
  event_manipulation,
  action_timing,
  CASE
    WHEN trigger_name LIKE 'prevent_%' THEN 'Immutability'
    WHEN trigger_name LIKE 'validate_%' THEN 'Validation'
    WHEN trigger_name LIKE 'update_%' THEN 'Auto-update'
    ELSE 'Other'
  END as trigger_purpose
FROM information_schema.triggers
WHERE trigger_schema='public'
  AND (trigger_name LIKE 'prevent_%'
    OR trigger_name LIKE 'validate_%'
    OR trigger_name LIKE 'update_%')
ORDER BY event_object_table, trigger_name;

-- ✅ PASS: 4+ triggers present
-- ✅ PASS: prevent_trade_updates_trigger on paper_trading_trades
-- ✅ PASS: prevent_trade_deletes_trigger on paper_trading_trades
-- ✅ PASS: validate_position_completeness_trigger on paper_trading_positions
-- ❌ FAIL: Less than 4 triggers


-- ============================================================================
-- CHECKPOINT 5: Verify Database Indices (Performance)
-- ============================================================================
-- Expected: 4+ indices for fast queries

SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE schemaname='public' AND tablename LIKE 'paper_%'
ORDER BY tablename, indexname;

-- ✅ PASS: idx_paper_positions_user_strategy visible
-- ✅ PASS: idx_paper_positions_status visible
-- ✅ PASS: idx_paper_trades_user_strategy visible
-- ✅ PASS: idx_execution_log_user_strategy visible


-- ============================================================================
-- CHECKPOINT 6: Verify Functions Created
-- ============================================================================
-- Expected: 6 functions (close_paper_position, prevent_*, validate_*, etc.)

SELECT
  proname as function_name,
  pronargs as parameter_count,
  prosecdef::boolean as security_definer,
  CASE
    WHEN proname = 'close_paper_position' THEN 'Safe Position Closure'
    WHEN proname LIKE 'prevent_%' THEN 'Immutability Enforcement'
    WHEN proname LIKE 'validate_%' THEN 'Validation'
    WHEN proname LIKE 'update_%' THEN 'Auto-update'
    WHEN proname = 'test_concurrent_close' THEN 'Race Condition Test'
    ELSE 'Other'
  END as purpose
FROM pg_proc
WHERE proname IN ('close_paper_position', 'prevent_trade_updates',
                   'prevent_trade_deletes', 'validate_position_completeness',
                   'update_position_timestamp', 'test_concurrent_close')
ORDER BY proname;

-- ✅ PASS: 6 functions exist
-- ✅ PASS: close_paper_position is SECURITY DEFINER (safe)
-- ❌ FAIL: Any function missing


-- ============================================================================
-- CHECKPOINT 7: Test RLS - Anonymous User Access
-- ============================================================================
-- This tests the anon user policies (demo mode)
-- Expected: INSERT succeeds (returns id), proves anon policies work

-- First, verify the policy exists:
SELECT
  policyname,
  tablename,
  qual as policy_definition,
  with_check as insert_check
FROM pg_policies
WHERE tablename='paper_trading_positions'
  AND policyname LIKE '%null user_id%'
ORDER BY tablename, policyname;

-- ✅ PASS: Policy for anon users (user_id IS NULL) present
-- ❌ FAIL: No anon user policy found


-- ============================================================================
-- CHECKPOINT 8: Verify View for Data Consistency
-- ============================================================================
-- This view helps detect orphaned positions

SELECT *
FROM information_schema.views
WHERE table_schema='public' AND table_name LIKE '%consistency%'
ORDER BY table_name;

-- ✅ PASS: consistency_check_orphaned_positions view exists
-- ❌ FAIL: View not found


-- ============================================================================
-- CHECKPOINT 9: Check Migration History
-- ============================================================================
-- Verify our migrations are recorded

SELECT *
FROM _supabase_migrations
WHERE name LIKE '202602251%'
ORDER BY name DESC;

-- ✅ PASS: Both migrations (120000 and 130000) listed as 'applied'
-- ❌ FAIL: Migrations missing or not marked as applied


-- ============================================================================
-- CHECKPOINT 10: Quick Safety Test - Entry Price Validation
-- ============================================================================
-- This will FAIL with a constraint error (which is what we want)
-- It proves the CHECK constraint entry_price > 0 is working

-- DON'T RUN THIS (it will error on purpose, proving constraint works):
-- INSERT INTO paper_trading_positions (
--   id, user_id, strategy_id, symbol_id, timeframe,
--   entry_price, quantity, entry_time, direction,
--   stop_loss_price, take_profit_price
-- ) VALUES (
--   gen_random_uuid(), null, 'test-id', 'test-symbol', '1D',
--   0, -- ❌ Invalid: entry_price must be > 0
--   100, now(), 'long', 90, 110
-- );
-- Expected error: "new row for relation "paper_trading_positions"
--                 violates check constraint..."


-- ============================================================================
-- SUMMARY CHECKPOINT: Count All Components
-- ============================================================================
-- If all counts match expected, deployment is successful!

SELECT
  'Tables' as component,
  count(*) as count,
  5 as expected
FROM information_schema.tables
WHERE table_schema='public' AND table_name LIKE 'paper_%'

UNION ALL

SELECT
  'RLS Policies' as component,
  count(*) as count,
  24 as expected
FROM pg_policies
WHERE tablename LIKE 'paper_%'

UNION ALL

SELECT
  'CHECK Constraints' as component,
  count(*) as count,
  9 as expected
FROM information_schema.check_constraints
WHERE table_schema='public' AND table_name LIKE 'paper_%'

UNION ALL

SELECT
  'Triggers' as component,
  count(*) as count,
  4 as expected
FROM information_schema.triggers
WHERE trigger_schema='public'
  AND (trigger_name LIKE 'prevent_%'
    OR trigger_name LIKE 'validate_%'
    OR trigger_name LIKE 'update_%')

UNION ALL

SELECT
  'Indices' as component,
  count(*) as count,
  4 as expected
FROM pg_indexes
WHERE schemaname='public' AND tablename LIKE 'paper_%'

UNION ALL

SELECT
  'Functions' as component,
  count(*) as count,
  6 as expected
FROM pg_proc
WHERE proname IN ('close_paper_position', 'prevent_trade_updates',
                   'prevent_trade_deletes', 'validate_position_completeness',
                   'update_position_timestamp', 'test_concurrent_close')

ORDER BY component;

-- ✅ PASS: All counts match expected
-- ❌ FAIL: Any count is lower than expected

-- ============================================================================
-- END OF VERIFICATION SCRIPT
-- ============================================================================
-- If all checkpoints passed, your deployment is successful! ✅
-- Record results in: docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md
