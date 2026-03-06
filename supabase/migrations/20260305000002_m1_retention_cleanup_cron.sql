-- Migration: pg_cron job to purge m1 bars older than 2 days
-- Runs nightly at midnight UTC to keep the m1 table lean

-- Ensure pg_cron is available (already enabled on this project)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Remove any prior version of this job
SELECT cron.unschedule('purge-m1-bars')
WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'purge-m1-bars'
);

-- Schedule nightly cleanup: delete m1 bars older than 2 days
SELECT cron.schedule(
  'purge-m1-bars',
  '0 0 * * *',  -- midnight UTC every day
  $$
    DELETE FROM ohlc_bars_v2
    WHERE timeframe = 'm1'
      AND is_intraday = true
      AND ts < NOW() - INTERVAL '2 days';
  $$
);

COMMENT ON EXTENSION pg_cron IS 'Enables scheduled SQL jobs for m1 bar retention and intraday ingestion';
