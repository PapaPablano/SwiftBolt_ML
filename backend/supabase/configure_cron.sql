-- Configure pg_cron settings for SPEC-8 orchestrator
-- Run this once after deploying migrations

-- Set Supabase URL
alter database postgres set app.supabase_url = 'https://cygflaemtmwiwaviclks.supabase.co';

-- Set service role key (replace with actual key)
-- alter database postgres set app.supabase_service_role_key = 'your_actual_service_role_key';

-- Verify cron job exists
select jobid, schedule, command, nodename, nodeport, database, username, active
from cron.job 
where jobname = 'orchestrator-tick';

-- Check if job_definitions table has data
select count(*) as job_definitions_count from job_definitions where enabled = true;

-- Check if job_runs table is ready
select count(*) as job_runs_count from job_runs;

-- Check if coverage_status table is ready
select count(*) as coverage_status_count from coverage_status;

-- Verify Realtime is enabled
select schemaname, tablename 
from pg_publication_tables 
where pubname = 'supabase_realtime' 
and tablename = 'job_runs';

-- Check RLS policies
select schemaname, tablename, policyname, permissive, roles, cmd, qual
from pg_policies
where tablename = 'job_runs';
