-- SPEC-8: Supabase pg_cron for orchestrator (replaces GitHub Actions)
-- Runs every minute to process job queue

-- Enable pg_cron extension
create extension if not exists pg_cron;

-- Create cron job to call orchestrator every minute
select cron.schedule(
  'orchestrator-tick',
  '* * * * *', -- Every minute
  $$
  select net.http_post(
    url := current_setting('app.supabase_url') || '/functions/v1/orchestrator?action=tick',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.supabase_service_role_key'),
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb
  ) as request_id;
  $$
);

-- Enable Realtime for job_runs (already in main migration, but ensure it's set)
-- This allows clients to subscribe to job progress updates
alter table job_runs replica identity full;

-- RLS policy for job_runs - allow authenticated users to read
alter table job_runs enable row level security;

create policy "Allow authenticated users to read job_runs"
  on job_runs
  for select
  using (true); -- Allow all reads (job_runs is not sensitive data)

-- Also allow anon reads for public dashboard
create policy "Allow anon users to read job_runs"
  on job_runs
  for select
  using (true);

-- Grant select to anon and authenticated
grant select on job_runs to anon, authenticated;

-- Verify cron job was created
select jobid, schedule, command 
from cron.job 
where jobname = 'orchestrator-tick';

comment on extension pg_cron is 'SPEC-8: Orchestrator runs every minute via pg_cron';
