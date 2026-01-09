-- Step 2: Configure Cron Authentication
-- Run this in Supabase SQL Editor after setting Edge Function secrets

-- Set Supabase URL
alter database postgres set app.supabase_url = 'https://cygflaemtmwiwaviclks.supabase.co';

-- Set service role key (YOU MUST REPLACE THIS WITH YOUR ACTUAL KEY)
-- Get your key from: Supabase Dashboard → Project Settings → API → service_role secret
alter database postgres set app.supabase_service_role_key = 'YOUR_SERVICE_ROLE_KEY_HERE';

-- Verify cron job exists
select jobid, schedule, command, active, jobname
from cron.job
where jobname = 'orchestrator-tick';

-- Expected result: One row with:
--   jobname: orchestrator-tick
--   schedule: * * * * *
--   active: true

-- Verify settings are applied
select
  current_setting('app.supabase_url', true) as supabase_url,
  length(current_setting('app.supabase_service_role_key', true)) as key_length;

-- Expected result:
--   supabase_url: https://cygflaemtmwiwaviclks.supabase.co
--   key_length: should be > 100 (not NULL or 0)
