-- run-backfill-worker now requires X-SB-Gateway-Key (SB_GATEWAY_KEY).
-- Cron must send it; use same Vault secret as Bearer so SB_GATEWAY_KEY can be set to service role in Dashboard.

DO $$
BEGIN
  PERFORM cron.unschedule('backfill-worker-every-minute');
EXCEPTION WHEN OTHERS THEN
  NULL;
END $$;

SELECT cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    SELECT net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
        'X-SB-Gateway-Key', (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);

-- Update helper so manual trigger also sends X-SB-Gateway-Key
CREATE OR REPLACE FUNCTION trigger_backfill_worker()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_key text;
  v_response jsonb;
BEGIN
  SELECT decrypted_secret INTO v_key FROM vault.decrypted_secrets WHERE name = 'service_role_key';
  IF v_key IS NULL THEN
    RAISE EXCEPTION 'Vault secret service_role_key not found';
  END IF;

  SELECT content::jsonb INTO v_response
  FROM net.http_post(
    url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || v_key,
      'X-SB-Gateway-Key', v_key
    ),
    body := '{}'
  );

  RETURN v_response;
END;
$$;

COMMENT ON FUNCTION trigger_backfill_worker IS 'Manually trigger the backfill worker (sends X-SB-Gateway-Key). Set SB_GATEWAY_KEY for run-backfill-worker to service role key.';
