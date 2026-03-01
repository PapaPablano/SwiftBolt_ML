-- Intraday live refresh: every 15 min, weekdays 13:00–20:45 UTC
-- Covers both EST (14:30-21:00) and EDT (13:30-20:00) market hours.
-- The Edge Function's is_market_open() RPC handles the precise gate.
-- Uses service_role_key from Vault (same pattern as backfill-worker cron).

SELECT cron.schedule(
  'intraday-live-refresh',
  '*/15 13-20 * * 1-5',
  $$
    SELECT net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/intraday-live-refresh',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
        'X-SB-Gateway-Key', (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key')
      ),
      body := '{}',
      timeout_milliseconds := 58000
    );
  $$
);
