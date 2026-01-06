-- SPEC-8: Cron schedule for backfill worker
-- Calls run-backfill-worker Edge Function every minute

-- Enable pg_cron extension if not already enabled
create extension if not exists pg_cron;

-- Store service role key in a secure setting (set via Supabase dashboard or CLI)
-- This should be set as: ALTER DATABASE postgres SET app.settings.service_role_key = 'your-service-role-key';
-- For now, we'll reference it from the setting

-- Schedule the backfill worker to run every minute
select cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    select net.http_post(
      url := current_setting('app.settings.supabase_url', true) || '/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true)
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);

-- View scheduled jobs
comment on extension pg_cron is 'Scheduled backfill worker runs every minute to process pending chunks';

-- Helper to check cron job status
create or replace function get_backfill_cron_status()
returns table(
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
language sql as $$
  select * from cron.job where jobname = 'backfill-worker-every-minute';
$$;

comment on function get_backfill_cron_status is 'Check status of the backfill worker cron job';
