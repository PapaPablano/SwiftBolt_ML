-- Migration: Multi-Leg Strategy Evaluation Cron Job
-- Runs every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
-- Uses Vault for secure service role key storage

-- Remove existing cron job if it exists
DO $$
BEGIN
  PERFORM cron.unschedule('multi-leg-evaluate-15min');
EXCEPTION WHEN OTHERS THEN
  NULL; -- Ignore if job doesn't exist
END $$;

-- Schedule the multi-leg evaluation job to run every 15 minutes during market hours
-- Market hours: 9:30 AM - 4:00 PM ET (14:30 - 21:00 UTC during EST, 13:30 - 20:00 UTC during EDT)
-- Running at minutes 0, 15, 30, 45 from 9 AM to 4 PM ET covers market hours
-- Using UTC: hours 14-21 covers EST market hours with buffer
SELECT cron.schedule(
  'multi-leg-evaluate-15min',
  '0,15,30,45 14-21 * * 1-5',  -- Every 15 min, 14:00-21:00 UTC, Mon-Fri
  $$
    SELECT net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/multi-leg-evaluate',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
      ),
      body := '{}',
      timeout_milliseconds := 55000
    );
  $$
);

COMMENT ON EXTENSION pg_cron IS 'Scheduled multi-leg evaluation runs every 15 minutes during market hours';

-- Helper function to check multi-leg cron job status
CREATE OR REPLACE FUNCTION get_multi_leg_cron_status()
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
  SELECT * FROM cron.job WHERE jobname = 'multi-leg-evaluate-15min';
$$;

COMMENT ON FUNCTION get_multi_leg_cron_status IS 'Check status of the multi-leg evaluation cron job';

-- Helper function to manually trigger multi-leg evaluation (for testing)
CREATE OR REPLACE FUNCTION trigger_multi_leg_evaluate()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_response jsonb;
BEGIN
  SELECT content::jsonb INTO v_response
  FROM net.http_post(
    url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/multi-leg-evaluate',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
    ),
    body := '{}'
  );

  RETURN v_response;
END;
$$;

COMMENT ON FUNCTION trigger_multi_leg_evaluate IS 'Manually trigger multi-leg strategy evaluation for testing';
