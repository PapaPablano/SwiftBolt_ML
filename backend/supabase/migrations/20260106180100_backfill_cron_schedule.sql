-- SPEC-8: Cron schedule for backfill worker
-- Calls run-backfill-worker Edge Function every minute

-- Note: Service role key must be set via Supabase Dashboard with superuser privileges:
-- Go to SQL Editor and run:
-- ALTER DATABASE postgres SET app.settings.service_role_key = 'your-service-role-key';

-- Remove existing job if it exists
do $$
begin
  perform cron.unschedule('backfill-worker-every-minute');
exception when others then
  null; -- Ignore if job doesn't exist
end $$;

-- Schedule the backfill worker to run every minute
-- URL is hardcoded since it's not sensitive and doesn't change
select cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    select net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
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
