-- ============================================================================
-- Trigger Alpaca Backfill for AAPL and NVDA
-- Purpose: Create backfill jobs to populate intraday data from Alpaca
-- Date: 2026-01-09
-- ============================================================================

\echo '\n========================================='
\echo 'TRIGGERING ALPACA BACKFILL'
\echo '=========================================\n'

-- Get symbol IDs
DO $$
DECLARE
  aapl_id UUID;
  nvda_id UUID;
BEGIN
  -- Get symbol IDs
  SELECT id INTO aapl_id FROM symbols WHERE ticker = 'AAPL';
  SELECT id INTO nvda_id FROM symbols WHERE ticker = 'NVDA';

  \echo 'Symbol IDs:'
  RAISE NOTICE 'AAPL ID: %', aapl_id;
  RAISE NOTICE 'NVDA ID: %', nvda_id;

  -- Delete any existing pending/in_progress jobs to start fresh
  DELETE FROM backfill_jobs
  WHERE symbol_id IN (aapl_id, nvda_id)
    AND timeframe = 'h1'
    AND status IN ('pending', 'in_progress', 'error');

  RAISE NOTICE 'Deleted old jobs';

  -- Create new backfill jobs for last 730 days (2 years)
  -- AAPL h1
  INSERT INTO backfill_jobs (
    symbol_id,
    timeframe,
    start_date,
    end_date,
    status,
    priority,
    created_at
  ) VALUES (
    aapl_id,
    'h1',
    (CURRENT_DATE - INTERVAL '730 days')::DATE,
    CURRENT_DATE,
    'pending',
    10,  -- High priority
    NOW()
  ) ON CONFLICT (symbol_id, timeframe, start_date, end_date)
    DO UPDATE SET status = 'pending', priority = 10, updated_at = NOW();

  RAISE NOTICE 'Created AAPL h1 backfill job';

  -- NVDA h1
  INSERT INTO backfill_jobs (
    symbol_id,
    timeframe,
    start_date,
    end_date,
    status,
    priority,
    created_at
  ) VALUES (
    nvda_id,
    'h1',
    (CURRENT_DATE - INTERVAL '730 days')::DATE,
    CURRENT_DATE,
    'pending',
    10,  -- High priority
    NOW()
  ) ON CONFLICT (symbol_id, timeframe, start_date, end_date)
    DO UPDATE SET status = 'pending', priority = 10, updated_at = NOW();

  RAISE NOTICE 'Created NVDA h1 backfill job';

END $$;

-- Verify jobs were created
\echo '\n========================================='
\echo 'BACKFILL JOBS CREATED'
\echo '=========================================\n'

SELECT
  s.ticker,
  j.timeframe,
  j.start_date,
  j.end_date,
  j.status,
  j.priority,
  j.total_chunks,
  j.completed_chunks,
  j.created_at
FROM backfill_jobs j
JOIN symbols s ON j.symbol_id = s.id
WHERE s.ticker IN ('AAPL', 'NVDA')
  AND j.timeframe = 'h1'
ORDER BY j.created_at DESC;

\echo '\n========================================='
\echo 'NEXT STEPS'
\echo '=========================================\n'
\echo '1. The backfill jobs have been created with "pending" status'
\echo '2. The orchestrator cron job will pick them up automatically'
\echo '3. Or you can trigger manually with:'
\echo '   curl -X POST https://YOUR_PROJECT.supabase.co/functions/v1/run-backfill-worker'
\echo '4. Monitor progress with:'
\echo '   psql -f diagnose-intraday-data.sql'
\echo ''
