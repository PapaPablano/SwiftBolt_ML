# Configure pg_cron for SPEC-8 Orchestrator

## Problem
The `alter database` command requires superuser privileges which aren't available in Supabase SQL Editor.

## Solution: Use Supabase CLI or Dashboard

### Option 1: Configure via Supabase Dashboard (Recommended)

The pg_cron job is already created but needs the configuration values. Since we can't set database-level parameters, we'll modify the cron job to use hardcoded values temporarily.

**Step 1:** Run this in Supabase SQL Editor to update the cron job:

```sql
-- Delete the existing cron job
select cron.unschedule('orchestrator-tick');

-- Recreate with hardcoded values (temporary solution)
select cron.schedule(
  'orchestrator-tick',
  '* * * * *',
  $$
  select net.http_post(
    url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick',
    headers := jsonb_build_object(
      'Authorization', 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YOUR_SERVICE_ROLE_KEY_HERE',
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb
  ) as request_id;
  $$
);

-- Verify the job was created
select jobid, schedule, command, active
from cron.job 
where jobname = 'orchestrator-tick';
```

**Step 2:** Get your service role key:
1. Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/api
2. Copy the `service_role` key (NOT the anon key)
3. Replace `YOUR_SERVICE_ROLE_KEY_HERE` in the SQL above

**Step 3:** Run the SQL to activate the cron job

---

### Option 2: Manual Trigger (For Testing)

If you want to test without configuring the cron job, you can manually trigger the orchestrator:

```bash
# Set your service role key
export SERVICE_ROLE_KEY="your_service_role_key_here"

# Trigger orchestrator manually
curl -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick"
```

Run this every minute to simulate the cron job.

---

### Option 3: Use GitHub Actions (Fallback)

If pg_cron doesn't work, you can use the existing GitHub Actions workflow:

1. The workflow is already in `.github/workflows/orchestrator-cron.yml`
2. Add your service role key as a GitHub secret:
   - Go to: https://github.com/YOUR_USERNAME/SwiftBolt_ML/settings/secrets/actions
   - Add secret: `SUPABASE_SERVICE_ROLE_KEY`
3. The workflow will run every 5 minutes (GitHub Actions minimum)

**Note:** This is less ideal than pg_cron (5 min vs 1 min intervals) but works as a fallback.

---

## Verification

After configuring the cron job, verify it's running:

```sql
-- Check cron job status
select jobid, schedule, command, active, nodename
from cron.job 
where jobname = 'orchestrator-tick';

-- Check if jobs are being created
select count(*) as total_jobs, 
       count(*) filter (where status = 'queued') as queued,
       count(*) filter (where status = 'running') as running,
       count(*) filter (where status = 'success') as success,
       count(*) filter (where status = 'failed') as failed
from job_runs
where created_at > now() - interval '10 minutes';

-- Check latest job runs
select id, symbol, timeframe, status, slice_from, slice_to, created_at
from job_runs
order by created_at desc
limit 10;
```

---

## Expected Behavior

Once configured:
1. Cron job runs every minute
2. Orchestrator scans job_definitions
3. Creates job_runs for gaps
4. Dispatches fetch-bars workers
5. Data lands in ohlc_bars_v2
6. Coverage_status updates

---

## Troubleshooting

### Cron job not running?

```sql
-- Check cron.job_run_details for errors
select jobid, runid, status, return_message, start_time
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'orchestrator-tick')
order by start_time desc
limit 10;
```

### Jobs not being dispatched?

Check orchestrator logs:
```bash
# View orchestrator logs (requires Supabase CLI)
supabase functions logs orchestrator --tail
```

Or manually trigger:
```bash
curl -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick"
```

---

## Security Note

**Important:** The service role key has full database access. Keep it secure:
- Never commit it to git
- Use environment variables or secrets management
- Rotate it periodically via Supabase Dashboard

For production, consider using Supabase's built-in cron jobs feature (if available in your plan) or a secure secrets manager.
