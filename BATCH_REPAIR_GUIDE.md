# Batch Backfill Repair Guide

## 🔧 Issues Identified

1. **fetch-bars-batch Boot Error**: Missing Alpaca credentials in Supabase Edge Functions
2. **Orchestrator Dispatching 0 Jobs**: Function signature is correct, but queue needs cleanup
3. **Batch Jobs Stuck**: Old queued jobs blocking the queue

## ✅ Repair Steps

### Step 1: Add Alpaca Credentials to Supabase

**Manual Step - Required First**

1. Go to Supabase Dashboard:
   ```
   https://app.supabase.com/project/cygflaemtmwiwaviclks/settings/functions
   ```

2. Click "Add Secret" and add these environment variables:
   ```
   ALPACA_API_KEY=<your-alpaca-api-key>
   ALPACA_API_SECRET=<your-alpaca-api-secret>
   ```

3. Get your keys from: https://app.alpaca.markets/brokerage/dashboard/overview

### Step 2: Redeploy fetch-bars-batch

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase
supabase functions deploy fetch-bars-batch --project-ref cygflaemtmwiwaviclks
```

**Expected Output:**
```
Deploying fetch-bars-batch (project ref: cygflaemtmwiwaviclks)
✓ Function deployed successfully
```

### Step 3: Test fetch-bars-batch

```bash
curl -X POST \
  'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/fetch-bars-batch' \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["AAPL"],
    "timeframe": "h1",
    "start": 1704067200,
    "end": 1704153600
  }'
```

**Expected Response:**
```json
{"success": true, "rowsWritten": 8}
```

**NOT:** `503 Service Unavailable`

### Step 4: Clear Queue and Prioritize Batch Jobs

Run the SQL script:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase
supabase db execute --project-ref cygflaemtmwiwaviclks -f fix_batch_queue.sql
```

**Expected Output:**
- Deleted old queued jobs
- Reset failed batch jobs to queued
- Shows batch job counts by status
- Shows next 10 jobs in queue

### Step 5: Trigger Orchestrator

```bash
# Set your service role key first
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# Trigger orchestrator
curl -X POST \
  'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick' \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

**Expected Response:**
```json
{"jobs_dispatched": 3}
```

### Step 6: Monitor Progress

Run this command to watch progress in real-time:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase

# Watch every 10 seconds
watch -n 10 "supabase db execute --project-ref cygflaemtmwiwaviclks -f monitor_batch_progress.sql"
```

**Or run manually:**

```bash
supabase db execute --project-ref cygflaemtmwiwaviclks -f monitor_batch_progress.sql
```

## 📊 Expected Timeline

- **+5 min**: First batch jobs succeed, 8,000+ bars written
- **+15 min**: 50+ batch jobs complete, 400,000+ bars written
- **+30 min**: 200+ batch jobs complete, 1.6M+ bars written
- **+60 min**: All 1,620 batch jobs complete, full h1 coverage

## 🚨 Troubleshooting

### If fetch-bars-batch still returns 503:

1. Check credentials are set:
   ```bash
   supabase functions list --project-ref cygflaemtmwiwaviclks
   ```

2. Check function logs:
   ```bash
   supabase functions logs fetch-bars-batch --project-ref cygflaemtmwiwaviclks
   ```

### If orchestrator dispatches 0 jobs:

1. Check if jobs are queued:
   ```sql
   SELECT COUNT(*) FROM job_runs WHERE status = 'queued';
   ```

2. Test claim_queued_job directly:
   ```sql
   SELECT * FROM claim_queued_job();
   ```

### If jobs fail with errors:

1. Check error messages:
   ```sql
   SELECT symbol, error_message, finished_at 
   FROM job_runs 
   WHERE status = 'failed' 
   ORDER BY finished_at DESC 
   LIMIT 10;
   ```

2. Check function logs:
   ```bash
   supabase functions logs fetch-bars-batch --project-ref cygflaemtmwiwaviclks
   ```

## 🎯 Success Criteria

✅ fetch-bars-batch returns 200 (not 503)
✅ orchestrator dispatches 3-5 jobs per tick
✅ Batch jobs transition: queued → running → success
✅ rows_written increases with each successful job
✅ No "boot error" messages in logs

## 📝 Files Created

- `fix_batch_queue.sql` - Clears queue and prioritizes batch jobs
- `monitor_batch_progress.sql` - Tracks batch job progress
- `BATCH_REPAIR_GUIDE.md` - This guide

## 🔗 Quick Links

- Supabase Dashboard: https://app.supabase.com/project/cygflaemtmwiwaviclks
- Edge Functions: https://app.supabase.com/project/cygflaemtmwiwaviclks/settings/functions
- Alpaca Dashboard: https://app.alpaca.markets/brokerage/dashboard/overview
