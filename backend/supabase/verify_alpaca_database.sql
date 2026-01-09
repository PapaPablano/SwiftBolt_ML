-- Alpaca Database Verification Script
-- Purpose: Verify Supabase database properly supports Alpaca optimization
-- Run this after deploying migration 20260109160000_complete_alpaca_database_support.sql

-- Check provider constraint includes alpaca
SELECT 
  conname as constraint_name,
  pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint 
WHERE conrelid = 'ohlc_bars_v2'::regclass 
  AND conname = 'ohlc_bars_v2_provider_check';

-- Check provider distribution (last 7 days)
SELECT * FROM get_provider_usage_stats(7);

-- Check if Alpaca data exists
SELECT 
  COUNT(*) as alpaca_bar_count,
  COUNT(DISTINCT symbol_id) as alpaca_symbol_count,
  MIN(DATE(ts)) as earliest_date,
  MAX(DATE(ts)) as latest_date
FROM ohlc_bars_v2
WHERE provider = 'alpaca';

-- Check Alpaca health metrics
SELECT * FROM v_alpaca_health;
