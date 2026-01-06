# SPEC-8 Deployment Status

**Date:** January 6, 2026  
**Status:** ⚠️ Partially Deployed - Schema Cache Issue

---

## ✅ Completed Steps

### 1. Database Migrations
- **Status:** ✅ Deployed and synced
- **Migrations Applied:**
  - `20260106000000_unified_orchestrator.sql` - Core tables (job_definitions, job_runs, coverage_status)
  - `20260106000001_orchestrator_cron.sql` - pg_cron + Realtime + RLS policies

**Verification:**
```bash
supabase migration list
# Shows both migrations as applied (Local + Remote)
```

### 2. Edge Functions Deployed
- **Status:** ✅ All functions deployed
- **Functions:**
  - `orchestrator` - Deployed (112.3kB)
  - `fetch-bars` - Deployed (142.4kB)
  - `ensure-coverage` - Deployed (108.2kB)

**Verification:**
```bash
supabase functions list
# All three functions should be listed
```

### 3. Client Code Updates
- **Status:** ✅ Complete
- **Files Modified:**
  - `Config.swift` - Fixed URL, enabled feature flag
  - `APIClient.swift` - Updated ensureCoverage signature
  - `EnsureCoverageResponse.swift` - Updated model structure
  - `ChartViewModel.swift` - Updated ensureCoverageAsync method

---

## ⚠️ Current Issue: Schema Cache

### Problem
Edge Functions cannot see the new tables:
```json
{"error":"Could not find the table 'public.job_definitions' in the schema cache"}
```

### Root Cause
Supabase Edge Functions cache the database schema. New tables from migrations aren't immediately visible to functions.

### Solution Options

#### Option 1: Wait for Cache Refresh (Recommended)
- **Time:** 5-10 minutes
- **Action:** Wait for Supabase to refresh schema cache automatically
- **Verification:** Retry ensure-coverage endpoint after 10 minutes

#### Option 2: Manual Schema Refresh via Dashboard
1. Go to Supabase Dashboard → Database → Schema
2. Click "Refresh Schema" or restart the project
3. Wait 2-3 minutes
4. Test endpoints again

#### Option 3: Grant Explicit Permissions (If needed)
```sql
-- Run in SQL Editor
grant usage on schema public to anon, authenticated, service_role;
grant all on all tables in schema public to anon, authenticated, service_role;
grant all on all sequences in schema public to anon, authenticated, service_role;
grant all on all functions in schema public to anon, authenticated, service_role;

-- Refresh schema cache
notify pgrst, 'reload schema';
```

---

## 🔄 Pending Configuration

### pg_cron Settings
**Status:** ⚠️ Not configured (requires manual setup)

The pg_cron job was created by the migration, but needs configuration:

```sql
-- Run in Supabase SQL Editor
alter database postgres set app.supabase_url = 'https://cygflaemtmwiwaviclks.supabase.co';
alter database postgres set app.supabase_service_role_key = 'your_actual_service_role_key';

-- Verify cron job
select jobid, schedule, command, active
from cron.job 
where jobname = 'orchestrator-tick';
```

**Note:** Replace `your_actual_service_role_key` with the real service role key from Supabase Dashboard → Settings → API.

---

## 📋 Next Steps (In Order)

### 1. Wait for Schema Cache (5-10 minutes)
```bash
# Test ensure-coverage after waiting
curl -i -X POST \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"1h","window_days":5}' \
  https://cygflaemtmwiwaviclks.supabase.co/functions/v1/ensure-coverage

# Expected: 200 OK with job_def_id
```

### 2. Configure pg_cron (Via Supabase Dashboard)
1. Go to SQL Editor
2. Run the configuration script from `backend/supabase/configure_cron.sql`
3. Verify cron job is active

### 3. Test Orchestrator
```bash
# Manually trigger orchestrator
curl -i -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick

# Expected: 200 OK with job statistics
```

### 4. Verify Job Creation
```sql
-- Run in SQL Editor
select status, count(*) 
from job_runs 
where symbol='AAPL' and timeframe='1h'
group by status;

-- Expected: Some queued/running/success jobs
```

### 5. Check Data Landing
```sql
-- Run in SQL Editor
select count(*) 
from ohlc_bars_v2 
where symbol='AAPL' and timeframe='1h'
  and ts > now() - interval '7 days';

-- Expected: Rows > 0 after jobs complete
```

### 6. Test Client Integration
- Open SwiftBoltML app
- Select AAPL symbol
- Switch to 1h timeframe
- Check console logs for:
  - `✅ Coverage complete` or `🔄 Gaps detected`
  - `ensureCoverage: AAPL/1h windowDays=5`

---

## 🐛 Troubleshooting

### If Schema Cache Issue Persists After 10 Minutes

**Check PostgREST Status:**
```sql
-- Verify PostgREST can see tables
select table_name 
from information_schema.tables 
where table_schema = 'public' 
  and table_name in ('job_definitions', 'job_runs', 'coverage_status');
```

**Force Schema Reload:**
```sql
-- Send reload signal to PostgREST
notify pgrst, 'reload schema';
```

**Check Function Logs:**
```bash
# View ensure-coverage logs
supabase functions logs ensure-coverage --tail

# View orchestrator logs
supabase functions logs orchestrator --tail
```

### If Orchestrator Not Creating Jobs

**Check Job Definitions:**
```sql
select * from job_definitions where enabled = true;
-- Should have rows for AAPL, NVDA, TSLA
```

**Check Coverage Gaps:**
```sql
select * from get_coverage_gaps('AAPL', '1h', 5);
-- Should return gaps if no data exists
```

**Manually Trigger Orchestrator:**
```bash
curl -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick
```

---

## 📊 Deployment Checklist

- [x] Database migrations deployed
- [x] Edge functions deployed (orchestrator, fetch-bars, ensure-coverage)
- [x] Client code updated
- [ ] Schema cache refreshed (wait 10 minutes)
- [ ] pg_cron configured with service role key
- [ ] ensure-coverage endpoint tested successfully
- [ ] Orchestrator creates job_runs
- [ ] Data lands in ohlc_bars_v2
- [ ] Client receives coverage status
- [ ] Realtime subscription implemented (TODO)
- [ ] Progress ribbon UI implemented (TODO)

---

## 🎯 Success Criteria

Once schema cache refreshes, verify:

1. **ensure-coverage returns 200:**
   ```json
   {
     "job_def_id": "uuid",
     "symbol": "AAPL",
     "timeframe": "1h",
     "status": "gaps_detected",
     "coverage_status": {
       "from_ts": null,
       "to_ts": null,
       "last_success_at": null,
       "gaps_found": 1
     }
   }
   ```

2. **Orchestrator creates jobs:**
   ```sql
   select count(*) from job_runs where status = 'queued';
   -- Should be > 0
   ```

3. **Bars appear in database:**
   ```sql
   select count(*) from ohlc_bars_v2 where symbol='AAPL' and timeframe='1h';
   -- Should increase after jobs complete
   ```

4. **Client logs show coverage check:**
   ```
   [DEBUG] ensureCoverage: AAPL/1h windowDays=5
   [DEBUG] 🔄 Gaps detected for AAPL 1h, orchestrator will hydrate
   ```

---

## 📝 Notes

- **Schema Cache:** This is a known Supabase behavior. New tables take 5-10 minutes to appear in Edge Functions.
- **pg_cron:** Requires manual configuration of service role key for security.
- **Realtime:** Backend is ready, client subscription needs implementation.
- **Progress Ribbon:** Backend is ready, UI component needs implementation.

---

## 🔗 Related Documents

- `SPEC8_DEPLOYMENT_GUIDE.md` - Full deployment instructions
- `SPEC8_BLOCKER_FIXES.md` - All 6 blocker fixes
- `SPEC8_IMPLEMENTATION_SUMMARY.md` - Architecture overview
- `configure_cron.sql` - pg_cron configuration script

---

## ⏰ Timeline

- **5:45 PM** - Migrations deployed and synced
- **5:46 PM** - Edge functions deployed
- **5:47 PM** - Schema cache issue discovered
- **5:55 PM** (Expected) - Schema cache should be refreshed
- **6:00 PM** (Target) - Full deployment verified

**Current Status:** Waiting for schema cache refresh. Retry ensure-coverage endpoint at 5:55 PM.
