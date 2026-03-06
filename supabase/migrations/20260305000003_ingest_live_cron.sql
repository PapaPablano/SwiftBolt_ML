-- Migration: Schedule ingest-live Edge Function via pg_cron
-- Fires every minute Mon-Fri 13:30-20:59 UTC (covers 9:30-4:00 PM ET in both
-- EDT and EST — is_market_open() inside the function handles the exact gate).

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Remove any prior version of this job
SELECT cron.unschedule('ingest-live')
WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'ingest-live'
);

-- Schedule: every minute during extended market window Mon-Fri
-- The function itself gates on is_market_open() so early/late invocations
-- simply return {skipped: true, reason: "market_closed"} cheaply.
SELECT cron.schedule(
  'ingest-live',
  '* 13-20 * * 1-5',
  $$
    SELECT net.http_post(
      url := current_setting('app.supabase_url') || '/functions/v1/ingest-live',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'x-sb-gateway-key', current_setting('app.sb_gateway_key')
      ),
      body := '{}'::jsonb
    );
  $$
);

COMMENT ON EXTENSION pg_cron IS 'pg_cron: drives ingest-live + nightly m1 cleanup';
