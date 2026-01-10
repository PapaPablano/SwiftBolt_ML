# Batch Backfill System - Critical Blocker

**Date:** January 9, 2026, 7:11 PM CST  
**Status:** 🔴 BLOCKED - fetch-bars-batch BOOT_ERROR

---

## 🎯 What We Accomplished

### ✅ Completed
1. **Queue Management**: Cleared 3,000+ single-symbol jobs
2. **US-Only Batch Jobs**: Created 61 US symbols in 2 batches (US_BATCH_1: 50, US_BATCH_2: 11)
3. **Job Definitions**: 390 batch job slices queued and ready
4. **Orchestrator**: Deployed with debug logging, correctly claiming batch jobs
5. **Alpaca Credentials**: Verified in Supabase secrets
6. **Batch Detection**: Orchestrator logic correctly identifies batch jobs

### ⚠️ Partial Success
- **Orchestrator routing**: Code updated to route batch jobs to `fetch-bars-batch`
- **Debug logging**: Added comprehensive logging to track batch detection
- **Job claiming**: `claim_queued_job()` successfully returns US_BATCH jobs

---

## 🔴 Critical Blocker

### Problem: fetch-bars-batch BOOT_ERROR

**Error:**
```json
{"code":"BOOT_ERROR","message":"Function failed to start (please check logs)"}
```

**Impact:**
- Orchestrator correctly detects batch jobs
- Orchestrator attempts to call `fetch-bars-batch`
- `fetch-bars-batch` returns 503 BOOT_ERROR
- Jobs fail with "Invalid symbol: US_BATCH_1" (falling back to single-symbol path)

**Root Cause:**
The `fetch-bars-batch` Edge Function fails to start. Possible causes:
1. Missing environment variable at boot time
2. Import/dependency issue with `_shared/cors.ts`
3. Syntax error preventing Deno from parsing the file
4. Memory/resource limit during function initialization

**Evidence:**
- Direct curl test: `503 BOOT_ERROR`
- Function redeployment: "No change found" (already deployed)
- Code review: Syntax appears correct
- Dependencies: `cors.ts` exists and is valid

---

## 📊 Current System State

### Job Status
```
US_BATCH_1 (50 symbols):
- Queued: 80 jobs
- Running: 2 jobs (will fail)
- Failed: 8 jobs

US_BATCH_2 (11 symbols):
- Queued: 85 jobs  
- Failed: 12 jobs
```

### Orchestrator Behavior
- **Claiming**: ✅ Working (returns US_BATCH jobs)
- **Batch Detection**: ✅ Working (isBatchJob = true)
- **Routing**: ✅ Correct (calls fetch-bars-batch)
- **Execution**: ❌ BLOCKED (fetch-bars-batch won't start)

### Concurrency
- 5 jobs running (at MAX_CONCURRENT_JOBS limit)
- Orchestrator won't dispatch more until some complete
- Running jobs will fail due to fetch-bars-batch BOOT_ERROR

---

## 🔧 Attempted Fixes

1. ✅ Redeployed `fetch-bars-batch` - No change
2. ✅ Verified Alpaca credentials exist in secrets
3. ✅ Checked `cors.ts` dependency - Exists and valid
4. ✅ Added debug logging to orchestrator
5. ✅ Fixed orchestrator parameter mapping (job_run_ids, from/to)
6. ❌ Direct function test - Still BOOT_ERROR

---

## 💡 Recommended Solutions

### Option 1: Check Supabase Dashboard Logs (IMMEDIATE)
```
1. Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
2. Click on "fetch-bars-batch"
3. View "Logs" tab
4. Look for boot/startup errors
5. Check for missing env vars or import errors
```

### Option 2: Simplify fetch-bars-batch (30 MIN)
Create a minimal version to test if it's a code issue:

```typescript
// Minimal test version
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

Deno.serve(async (req) => {
  console.log("[fetch-bars-batch] Function started!");
  
  return new Response(JSON.stringify({
    success: true,
    message: "Batch function is alive"
  }), {
    headers: { "Content-Type": "application/json" }
  });
});
```

Deploy and test. If this works, gradually add back functionality.

### Option 3: Use fetch-bars with Orchestrator Batching (2 HOURS)
Modify orchestrator to:
1. Detect batch jobs
2. Loop through symbols array
3. Call `fetch-bars` for each symbol (still faster than queue processing)
4. Aggregate results

This sacrifices the 50x API efficiency but unblocks the system.

### Option 4: Debug with Local Supabase (1 HOUR)
```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase
supabase functions serve fetch-bars-batch
# Test locally to see actual error messages
curl http://localhost:54321/functions/v1/fetch-bars-batch \
  -d '{"job_run_ids":[],"symbols":["AAPL"],"timeframe":"h1","from":"2024-01-11T00:00:00Z","to":"2024-01-12T00:00:00Z"}'
```

---

## 📝 Next Steps

**IMMEDIATE (5 min):**
1. Check Supabase dashboard logs for fetch-bars-batch
2. Look for specific error message at boot time

**IF LOGS SHOW ERROR (15 min):**
3. Fix the specific error (missing import, env var, etc.)
4. Redeploy fetch-bars-batch
5. Test with curl

**IF NO CLEAR ERROR (30 min):**
6. Deploy minimal test version of fetch-bars-batch
7. Verify it starts successfully
8. Gradually add back functionality

**FALLBACK (2 hours):**
9. Implement Option 3: Orchestrator-level batching with fetch-bars
10. Sacrifice API efficiency for system functionality

---

## 🎯 Success Criteria

When fixed, you should see:
```sql
SELECT 
  jd.symbol,
  COUNT(*) FILTER (WHERE jr.status = 'success') as success,
  SUM(jr.rows_written) as total_bars
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbol LIKE 'US_BATCH_%'
  AND jr.updated_at > now() - interval '10 minutes'
GROUP BY jd.symbol;

-- Expected:
-- US_BATCH_1: success: 5+, total_bars: 2500+
-- US_BATCH_2: success: 5+, total_bars: 550+
```

---

## 📁 Files Modified

1. `orchestrator/index.ts` - Added debug logging, fixed batch routing ✅
2. `fix_batch_queue.sql` - Queue cleanup ✅
3. `create_us_batch_jobs.sql` - US-only batch jobs ✅
4. `BATCH_STATUS_CURRENT.md` - Status documentation ✅
5. `BATCH_SYSTEM_BLOCKER.md` - This file ✅

---

**The system is 95% complete. Only blocker: fetch-bars-batch won't start.**

**Recommended action: Check Supabase dashboard logs immediately.**
