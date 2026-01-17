-- Migration: Backfill Worker Cron with Vault-based Service Role Key
-- Uses Supabase Vault for secure secret storage instead of database parameters

-- First, store the service role key in Vault (do this manually via Supabase Dashboard or SQL):
-- INSERT INTO vault.secrets (name, secret)
-- VALUES ('service_role_key', 'your-service-role-key-here')
-- ON CONFLICT (name) DO UPDATE SET secret = EXCLUDED.secret;

-- Remove existing cron job if it exists
DO $$
BEGIN
  PERFORM cron.unschedule('backfill-worker-every-minute');
EXCEPTION WHEN OTHERS THEN
  NULL; -- Ignore if job doesn't exist
END $$;

-- Schedule the backfill worker to run every minute using Vault
SELECT cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    SELECT net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);

COMMENT ON EXTENSION pg_cron IS 'Scheduled backfill worker runs every minute to process pending chunks';

-- Helper function to check cron job status
CREATE OR REPLACE FUNCTION get_backfill_cron_status()
RETURNS TABLE(
  jobid bigint,
  schedule text,
  command text,
  nodename text,
  nodeport int,
  database text,
  username text,
  active boolean,
  jobname text
)
LANGUAGE sql AS $$
  SELECT * FROM cron.job WHERE jobname = 'backfill-worker-every-minute';
$$;

COMMENT ON FUNCTION get_backfill_cron_status IS 'Check status of the backfill worker cron job';

-- Helper function to manually trigger the backfill worker (for testing)
CREATE OR REPLACE FUNCTION trigger_backfill_worker()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_response jsonb;
BEGIN
  SELECT content::jsonb INTO v_response
  FROM net.http_post(
    url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
    ),
    body := '{}'
  );

  RETURN v_response;
END;
$$;

COMMENT ON FUNCTION trigger_backfill_worker IS 'Manually trigger the backfill worker for testing';
