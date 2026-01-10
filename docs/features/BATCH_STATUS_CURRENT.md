# Batch Backfill System - Current Status

**Date:** January 9, 2026, 7:02 PM CST  
**Status:** ⚠️ PARTIALLY WORKING - Needs Fix

---

## ✅ What's Working

1. **Queue Cleaned**: All single-symbol jobs cancelled (3,046 jobs removed)
2. **US-Only Batch Jobs Created**: 
   - US_BATCH_1: 50 symbols (AAPL, MSFT, NVDA, etc.)
   - US_BATCH_2: 11 symbols (TMUS, TSLA, UNH, etc.)
3. **Jobs Queued**: 303 batch job slices ready
4. **Orchestrator Running**: Claiming batch jobs successfully
5. **Alpaca Credentials**: Configured and working

---

## ⚠️ Current Issue

**Problem:** Orchestrator is routing batch jobs to `fetch-bars` (single-symbol) instead of `fetch-bars-batch`

**Error Message:**
```
Invalid symbol: US_BATCH_1
```

**Root Cause:** The orchestrator's batch detection logic (line 332 in `orchestrator/index.ts`) correctly identifies batch jobs, but something is causing it to route to the single-symbol function instead of the batch function.

**Evidence:**
- 16 batch jobs failed with "Invalid symbol: US_BATCH_1/US_BATCH_2"
- Logs show only `fetch-bars` calls, no `fetch-bars-batch` calls
- The error indicates it's passing the job definition name instead of the symbols array

---

## 🔍 Diagnosis

The orchestrator code at line 332:
```typescript
const isBatchJob = jobDef?.symbols_array && Array.isArray(jobDef.symbols_array) && jobDef.symbols_array.length > 1;
```

This should correctly detect batch jobs (our US_BATCH jobs have 50 and 11 symbols respectively), but the routing is failing.

**Possible causes:**
1. The `isBatchJob` condition is evaluating to `false` despite correct data
2. The orchestrator is falling through to the single-symbol path
3. There's an error in the batch routing code that's being caught and retried as single-symbol

---

## 📊 Current Job Status

```
US_BATCH_1 (50 symbols):
- Failed: 7 jobs
- Queued: 153 jobs
- Running: 0 jobs

US_BATCH_2 (11 symbols):
- Failed: 9 jobs
- Queued: 150 jobs
- Running: 1 job (42 seconds, likely will fail)
```

---

## 🛠️ Recommended Fix

**Option 1: Debug Orchestrator Logging**
Add console.log statements to the orchestrator to see why batch detection is failing:

```typescript
console.log('[Orchestrator] Job def:', {
  id: job.job_def_id,
  symbols_array: jobDef?.symbols_array,
  is_array: Array.isArray(jobDef?.symbols_array),
  length: jobDef?.symbols_array?.length,
  isBatchJob: isBatchJob
});
```

**Option 2: Simplify Batch Detection**
Change line 332 to be more explicit:

```typescript
const isBatchJob = jobDef?.symbols_array !== null && 
                   jobDef?.symbols_array !== undefined &&
                   Array.isArray(jobDef.symbols_array) && 
                   jobDef.symbols_array.length > 1;
```

**Option 3: Check for Errors in Batch Path**
Wrap the batch dispatch in try-catch to see if it's silently failing:

```typescript
if (isBatchJob) {
  try {
    console.log(`[Orchestrator] BATCH JOB DETECTED: ${jobDef.symbols_array.length} symbols`);
    // ... existing batch code
  } catch (error) {
    console.error(`[Orchestrator] Batch dispatch failed, falling back to single:`, error);
    // Falls through to single-symbol path
  }
}
```

---

## 📝 Monitoring Commands

### Check Job Status
```sql
SELECT 
  jd.symbol,
  jsonb_array_length(jd.symbols_array) as symbols_count,
  jr.status,
  COUNT(*) as count,
  SUM(jr.rows_written) as total_bars
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbol LIKE 'US_BATCH_%'
GROUP BY jd.symbol, jsonb_array_length(jd.symbols_array), jr.status
ORDER BY jr.status;
```

### Check Recent Errors
```sql
SELECT 
  jd.symbol,
  jr.error_message,
  jr.finished_at
FROM job_runs jr
JOIN job_definitions jd ON jr.job_def_id = jd.id
WHERE jd.symbol LIKE 'US_BATCH_%'
  AND jr.status = 'failed'
ORDER BY jr.finished_at DESC
LIMIT 5;
```

### Test Batch Detection
```sql
SELECT 
  id,
  symbol,
  symbols_array,
  CASE 
    WHEN symbols_array IS NOT NULL 
      AND jsonb_typeof(symbols_array) = 'array' 
      AND jsonb_array_length(symbols_array) > 1 
    THEN 'BATCH'
    ELSE 'SINGLE'
  END as detected_type
FROM job_definitions
WHERE symbol LIKE 'US_BATCH_%';
```

---

## 🎯 Next Steps

1. **Add debug logging** to orchestrator to see batch detection results
2. **Redeploy orchestrator** with logging
3. **Trigger manual tick** and check logs
4. **Verify fetch-bars-batch** is being called
5. **Monitor for successful completions**

---

## 📦 Files Created

- `fix_batch_queue.sql` - Queue cleanup
- `monitor_batch_progress.sql` - Progress monitoring  
- `create_us_batch_jobs.sql` - US-only batch jobs
- `BATCH_REPAIR_COMPLETE.md` - Initial success summary
- `BATCH_STATUS_CURRENT.md` - This file (current status)

---

**System is 90% complete. Just need to fix the orchestrator routing logic to use `fetch-bars-batch` for batch jobs.**
