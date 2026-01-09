# Phase 2 Batch Processing - Production Deployment Guide

## 🎯 Overview

Phase 2 delivers **50x API efficiency** by batching 50 symbols per Alpaca API request instead of 1 symbol per request. This reduces API calls from 5000+ to ~100 while staying under the 200 req/min rate limit.

**Status**: ✅ Ready for production deployment

---

## 🏗️ Architecture Changes

### Database Schema
- **Added**: `batch_version` column to `job_definitions`
- **Updated**: Unique constraint now includes `batch_version`
  - Phase 1 jobs: `batch_version = 1` (single-symbol)
  - Phase 2 jobs: `batch_version = 2` (batch processing)
- **Benefit**: Phase 1 and Phase 2 jobs can coexist safely

### Edge Functions Updated
1. **`batch-backfill-orchestrator`**
   - Creates batch jobs with `symbols_array` containing up to 50 symbols
   - Sets `batch_version = 2` for new jobs
   - Labels batch rows as `BATCH_1`, `BATCH_2`, etc.

2. **`orchestrator`** (dispatcher)
   - Detects batch jobs by checking `symbols_array` field
   - Routes batch jobs → `fetch-bars-batch` (Phase 2)
   - Routes single jobs → `fetch-bars` (Phase 1)
   - Seamless coexistence of both processing modes

3. **`fetch-bars-batch`** (already deployed)
   - Processes up to 50 symbols in a single Alpaca API call
   - Writes results to `intraday_bars` table
   - Updates `job_runs` status

---

## 📋 Deployment Steps

### Step 1: Deploy Updated Functions

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase

# Deploy orchestrator with batch routing logic
supabase functions deploy orchestrator

# Deploy batch-backfill-orchestrator with batch_version support
supabase functions deploy batch-backfill-orchestrator
```

### Step 2: Test with 5 Symbols

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/scripts

# Test Phase 2 with NVDA, TSLA, AMD, META, NFLX
./test-phase2-batch.sh
```

**Expected Results**:
- 2 batch jobs created (1 for h1, 1 for d1)
- Each job has `symbols_array` with 5 symbols
- `batch_version = 2`
- Jobs appear in `job_definitions` table

### Step 3: Verify Batch Processing

```bash
# Check job creation
psql $DATABASE_URL -c "
SELECT 
  symbol,
  timeframe,
  batch_version,
  jsonb_array_length(symbols_array) AS batch_size,
  symbols_array
FROM job_definitions
WHERE batch_version = 2
ORDER BY created_at DESC
LIMIT 5;
"

# Manually trigger orchestrator to process batch jobs
curl -X POST \
  'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick' \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"

# Monitor job execution
psql $DATABASE_URL -c "
SELECT 
  id,
  symbol,
  timeframe,
  status,
  rows_written,
  created_at,
  finished_at
FROM job_runs
WHERE created_at > now() - interval '30 minutes'
ORDER BY created_at DESC
LIMIT 10;
"
```

### Step 4: Migrate Full Universe (Once Proven)

```bash
# This creates Phase 2 batch jobs for ALL symbols in your universe
./migrate-to-phase2-batch.sh
```

**What This Does**:
1. Reads all unique symbols from existing `job_definitions` (batch_version=1)
2. Creates new batch jobs with `batch_version=2`
3. Batches symbols into groups of 50
4. Creates jobs for all timeframes: m15, h1, h4, d1
5. Leaves Phase 1 jobs enabled (for safety)

**Expected Results**:
- ~100 batch jobs created (vs 5000+ single-symbol jobs)
- 50x reduction in API calls
- Both Phase 1 and Phase 2 jobs coexist

---

## 📊 Monitoring & Validation

### Check Batch Job Status

```sql
-- Summary by batch version
SELECT 
  batch_version,
  COUNT(*) as job_count,
  COUNT(DISTINCT timeframe) as timeframes,
  SUM(CASE WHEN symbols_array IS NOT NULL 
      THEN jsonb_array_length(symbols_array) 
      ELSE 1 END) as total_symbols
FROM job_definitions
GROUP BY batch_version
ORDER BY batch_version;
```

### Monitor API Efficiency

```sql
-- Count API calls in last 24 hours
SELECT 
  DATE_TRUNC('hour', created_at) as hour,
  COUNT(*) as api_calls,
  SUM(rows_written) as total_bars
FROM job_runs
WHERE created_at > now() - interval '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

### Check Orchestrator Logs

```bash
# View orchestrator logs
supabase functions logs orchestrator --tail

# View batch worker logs
supabase functions logs fetch-bars-batch --tail
```

### Verify Data Quality

```sql
-- Check recent data writes
SELECT 
  symbol_id,
  timeframe,
  COUNT(*) as bar_count,
  MIN(ts) as earliest,
  MAX(ts) as latest,
  provider
FROM intraday_bars
WHERE created_at > now() - interval '1 hour'
GROUP BY symbol_id, timeframe, provider
ORDER BY created_at DESC
LIMIT 20;
```

---

## 🔄 Gradual Migration Strategy

### Option A: Parallel Operation (Recommended)
1. Deploy Phase 2 functions ✅
2. Test with 5 symbols ✅
3. Create Phase 2 jobs for full universe
4. Monitor both Phase 1 and Phase 2 for 24-48 hours
5. Compare data quality and API usage
6. Disable Phase 1 jobs once confident:
   ```sql
   UPDATE job_definitions 
   SET enabled = false 
   WHERE batch_version = 1;
   ```
7. Clean up Phase 1 jobs after 1 week:
   ```sql
   DELETE FROM job_definitions 
   WHERE batch_version = 1 AND enabled = false;
   ```

### Option B: Immediate Cutover
1. Deploy Phase 2 functions
2. Test with 5 symbols
3. Disable Phase 1 jobs:
   ```sql
   UPDATE job_definitions SET enabled = false WHERE batch_version = 1;
   ```
4. Create Phase 2 jobs for full universe
5. Monitor closely for 24 hours

---

## 🎯 Success Metrics

### API Efficiency
- **Before**: 5000+ API calls per backfill cycle
- **After**: ~100 API calls per backfill cycle
- **Target**: 50x reduction confirmed

### Rate Limit Compliance
- **Limit**: 200 requests/minute (Alpaca)
- **Phase 1**: Risk of hitting limit with parallel workers
- **Phase 2**: Safely under limit with batch processing

### Data Quality
- Same data coverage as Phase 1
- No gaps in historical data
- Consistent bar counts across timeframes

### Performance
- Job completion time should be similar or faster
- Reduced database write contention
- Lower Supabase function invocation costs

---

## 🚨 Rollback Plan

If Phase 2 encounters issues:

```sql
-- Disable Phase 2 jobs
UPDATE job_definitions 
SET enabled = false 
WHERE batch_version = 2;

-- Re-enable Phase 1 jobs
UPDATE job_definitions 
SET enabled = true 
WHERE batch_version = 1;
```

Then investigate logs:
```bash
supabase functions logs orchestrator --tail
supabase functions logs fetch-bars-batch --tail
```

---

## 📝 Key Files Modified

### Database Migrations
- `backend/supabase/migrations/add_batch_version_to_job_definitions.sql`
  - Adds `batch_version` column
  - Updates unique constraint

### Edge Functions
- `backend/supabase/functions/batch-backfill-orchestrator/index.ts`
  - Sets `batch_version = 2`
  - Uses `BATCH_N` symbol naming

- `backend/supabase/functions/orchestrator/index.ts`
  - Detects batch jobs via `symbols_array`
  - Routes to `fetch-bars-batch` for Phase 2
  - Routes to `fetch-bars` for Phase 1

### Scripts
- `backend/scripts/test-phase2-batch.sh`
  - Test with 5 symbols
  
- `backend/scripts/migrate-to-phase2-batch.sh`
  - Migrate full universe to Phase 2

---

## 🔍 Troubleshooting

### Issue: Batch jobs not being processed
**Check**: Orchestrator is picking up jobs
```sql
SELECT * FROM job_runs 
WHERE created_at > now() - interval '1 hour' 
ORDER BY created_at DESC;
```

**Solution**: Manually trigger orchestrator
```bash
curl -X POST \
  'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick' \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

### Issue: Unique constraint violation
**Cause**: Trying to create duplicate batch jobs

**Solution**: Check existing jobs first
```sql
SELECT * FROM job_definitions 
WHERE symbol LIKE 'BATCH_%' 
  AND timeframe = 'h1' 
  AND batch_version = 2;
```

### Issue: No data written
**Check**: `fetch-bars-batch` logs for errors
```bash
supabase functions logs fetch-bars-batch --tail
```

**Common causes**:
- Alpaca API key not set
- Rate limit exceeded
- Invalid symbol in batch

---

## 📈 Next Steps After Deployment

1. **Monitor for 24 hours**
   - Check job completion rates
   - Verify data quality
   - Monitor API usage

2. **Compare Phase 1 vs Phase 2**
   - Data coverage
   - API efficiency
   - Error rates

3. **Optimize batch size** (if needed)
   - Current: 50 symbols/batch
   - Can adjust based on performance

4. **Disable Phase 1** (once confident)
   - Reduces database clutter
   - Simplifies monitoring

5. **Document learnings**
   - Update runbooks
   - Share with team

---

## ✅ Deployment Checklist

- [ ] Database migration applied (`batch_version` column added)
- [ ] Unique constraint updated to include `batch_version`
- [ ] `orchestrator` function deployed with batch routing
- [ ] `batch-backfill-orchestrator` function deployed with `batch_version=2`
- [ ] Test with 5 symbols successful
- [ ] Batch jobs appear in `job_definitions`
- [ ] Orchestrator routes batch jobs to `fetch-bars-batch`
- [ ] Data written to `intraday_bars` table
- [ ] API efficiency confirmed (50x reduction)
- [ ] Full universe migration completed
- [ ] Monitoring dashboards updated
- [ ] Team notified of deployment

---

## 🎉 Expected Impact

### Cost Savings
- **Supabase Function Invocations**: 50x reduction
- **Alpaca API Calls**: 50x reduction
- **Database Writes**: More efficient batching

### Performance
- **Faster backfills**: Fewer round trips
- **Better rate limit compliance**: Controlled request rate
- **Reduced contention**: Fewer concurrent jobs

### Maintainability
- **Simpler job definitions**: ~100 jobs vs 5000+
- **Easier monitoring**: Fewer jobs to track
- **Clearer logs**: Batch-level visibility

---

**Questions or issues?** Check logs first, then review this guide's troubleshooting section.
