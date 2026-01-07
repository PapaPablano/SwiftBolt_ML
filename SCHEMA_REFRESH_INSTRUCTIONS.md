# URGENT: Schema Cache Refresh Required

## Problem
Edge Functions can't see the new SPEC-8 tables due to PostgREST schema cache.

## Solution: Manual Schema Refresh via Supabase Dashboard

### Step 1: Go to SQL Editor
1. Open https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql/new
2. Paste and run this SQL:

```sql
-- Grant permissions to all roles
grant usage on schema public to anon, authenticated, service_role;
grant all on all tables in schema public to anon, authenticated, service_role;
grant all on all sequences in schema public to anon, authenticated, service_role;
grant all on all functions in schema public to anon, authenticated, service_role;

-- Force PostgREST schema reload
notify pgrst, 'reload schema';

-- Verify tables exist
select table_name from information_schema.tables 
where table_schema = 'public' 
  and table_name in ('job_definitions', 'job_runs', 'coverage_status')
order by table_name;
```

### Step 2: Wait 1-2 Minutes
PostgREST needs time to process the reload signal.

### Step 3: Test ensure-coverage
```bash
curl -i -X POST \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"1h","window_days":5}' \
  https://cygflaemtmwiwaviclks.supabase.co/functions/v1/ensure-coverage
```

Expected: `200 OK` with JSON response containing `job_def_id`

---

## Alternative: Restart PostgREST

If the above doesn't work:

1. Go to https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/general
2. Click "Restart project" (this will cause ~30 seconds downtime)
3. Wait for project to restart
4. Test ensure-coverage endpoint again

---

## Why This Happens

PostgREST (Supabase's API layer) caches the database schema for performance. When new tables are created via migrations, PostgREST doesn't automatically see them until:
1. The cache expires (can take 10+ minutes)
2. A manual reload is triggered (`notify pgrst, 'reload schema'`)
3. The project is restarted

This is a known Supabase behavior and is expected after deploying new migrations.
