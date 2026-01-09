-- Step 2: Configure Cron Authentication (VAULT METHOD - RECOMMENDED)
-- This uses Supabase Vault for secure credential storage instead of database settings
-- Run this in Supabase SQL Editor

-- ============================================================================
-- PART 1: Create helper function that reads from Vault
-- ============================================================================

create or replace function public.run_orchestrator_tick()
returns void
language plpgsql
security definer
as $$
declare
  svc_secret jsonb;
  svc_key text;
  base_url text := 'https://cygflaemtmwiwaviclks.supabase.co';
  req_id bigint;
begin
  -- Read service role key from Vault
  -- Supabase automatically stores this as 'service_role' secret
  select decrypted_secret into svc_key
  from vault.decrypted_secrets
  where name = 'service_role';

  -- If secret not found, raise error
  if svc_key is null then
    raise exception 'Service role key not found in Vault. Please add it via: select vault.create_secret(''service_role'', ''your-key-here'');';
  end if;

  -- Fire-and-forget HTTP call to Edge Function "orchestrator"
  select net.http_post(
    url := base_url || '/functions/v1/orchestrator?action=tick',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || svc_key,
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 30000  -- 30 second timeout
  ) into req_id;

  -- Note: We don't wait for completion (fire-and-forget)
  -- The orchestrator runs async in the background
  raise notice 'Orchestrator tick triggered with request_id: %', req_id;
end;
$$;

-- Lock down execution (only postgres and supabase_admin can call this)
revoke all on function public.run_orchestrator_tick() from public;
grant execute on function public.run_orchestrator_tick() to postgres, supabase_admin;

comment on function public.run_orchestrator_tick() is
'Triggers the orchestrator Edge Function tick. Reads credentials from Vault for security.';

-- ============================================================================
-- PART 2: Store service role key in Vault (if not already there)
-- ============================================================================

-- First, check if the secret already exists
select name, description, created_at
from vault.secrets
where name = 'service_role';

-- If the query above returns NO ROWS, then add your service role key:
-- UNCOMMENT and replace 'your-actual-service-role-key' with your real key
-- Get your key from: Supabase Dashboard → Project Settings → API → service_role

select vault.create_secret(
   'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YajeNHOQ63uBDDZhJ2YYHK7L-BKmnZAviDqrlk2TQxU',  -- The actual key value
   'service_role',                   -- Secret name
   'Service role key for orchestrator cron job'  -- Description (optional)
 );

-- ⚠️ SECURITY NOTE: After running the above ONCE, immediately comment it out
-- to prevent accidentally re-running with the key visible in SQL history

-- Verify the secret was created
select name, description, created_at
from vault.secrets
where name = 'service_role';

-- Expected result: One row with name='service_role'

-- ============================================================================
-- PART 3: Schedule the cron job
-- ============================================================================

-- First, unschedule any existing orchestrator-tick job to avoid duplicates
select cron.unschedule('orchestrator-tick');

-- Schedule the job to run every minute
select cron.schedule(
  job_name => 'orchestrator-tick',
  schedule => '* * * * *',  -- Every minute
  command  => $$select public.run_orchestrator_tick();$$
);

-- ============================================================================
-- PART 4: Verify everything is configured correctly
-- ============================================================================

-- 1. Check cron job exists and is active
select jobid, schedule, command, active, jobname
from cron.job
where jobname = 'orchestrator-tick';

-- Expected result:
-- jobid | schedule   | command                               | active | jobname
-- ------|------------|---------------------------------------|--------|------------------
-- X     | * * * * *  | select public.run_orchestrator_tick() | true   | orchestrator-tick

-- 2. Check service_role secret exists in Vault
select name, description, created_at
from vault.secrets
where name = 'service_role';

-- Expected result: One row showing the secret exists

-- 3. Test the function manually (optional but recommended)
-- This will trigger one orchestrator tick immediately
-- select public.run_orchestrator_tick();

-- Check the logs for "Orchestrator tick triggered with request_id: XXX"

-- 4. Check recent cron job executions (wait 1-2 minutes after scheduling)
select
  jobid,
  runid,
  job_pid,
  database,
  username,
  command,
  status,
  return_message,
  start_time,
  end_time
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'orchestrator-tick')
order by start_time desc
limit 5;

-- Expected result: Rows showing recent executions with status='succeeded'

-- ============================================================================
-- TROUBLESHOOTING
-- ============================================================================

-- If cron job fails, check the return_message from job_run_details above

-- Common issues:

-- Issue 1: "Service role key not found in Vault"
-- Fix: Run the vault.create_secret() command in PART 2

-- Issue 2: "permission denied for schema vault"
-- Fix: Ensure you're running as postgres or supabase_admin user

-- Issue 3: "relation vault.secrets does not exist"
-- Fix: Vault extension may not be enabled. Check with:
-- select * from pg_extension where extname = 'supabase_vault';
-- Enable if needed (contact Supabase support)

-- Issue 4: HTTP request times out
-- Fix: Check Edge Function logs in Supabase Dashboard
-- The orchestrator function may be having issues

-- ============================================================================
-- CLEANUP (Optional)
-- ============================================================================

-- If you want to remove the old database settings method (from previous approach):
-- alter database postgres reset app.supabase_url;
-- alter database postgres reset app.supabase_service_role_key;

-- ============================================================================
-- NOTES
-- ============================================================================

-- ✅ This approach is MORE SECURE than storing keys in database settings
-- ✅ Vault secrets are encrypted at rest
-- ✅ Only functions with SECURITY DEFINER can access Vault secrets
-- ✅ The service_role key is never exposed in logs or pg_stat views
-- ✅ Following Supabase best practices for credential management
