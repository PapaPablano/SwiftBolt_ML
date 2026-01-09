# 📊 Data Health Check Guide

Based on your screenshot showing AAPL chart with 1H timeframe, here's how to verify everything is working correctly.

---

## 🔍 What You're Seeing

Your chart shows:
- **Symbol**: AAPL
- **Timeframe**: 1H (hourly)
- **Date**: Around Jan 30, 2024
- **Watchlist**: AAPL, NVDA, CRWD, AMD, PLTR, AMZN, MU (7 symbols)

---

## ⚠️ Potential Issue: Old Data

If you're seeing data from **Jan 2024** (over a year ago), this could mean:

1. **Backfill hasn't started yet** (chunks still pending)
2. **Chart is showing cached data** from previous Yahoo fetches
3. **Backfill is in progress** but not complete for recent dates yet

---

## ✅ How to Check Data Health

### Option 1: Quick Terminal Test

```bash
# Set your anon key
export SUPABASE_ANON_KEY="your-anon-key-from-dashboard"

# Run the health check
./test-data-health.sh
```

This will show you:
- ✅ Edge functions working
- ✅ Database connection
- 📊 Chunk processing status
- 🔄 Current backfill progress

### Option 2: SQL Editor Checks

Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql

**Run these queries in order:**

#### A. Check Backfill Status
```sql
SELECT
  symbol,
  progress || '%' as pct,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id AND status = 'done') as done,
  (SELECT COUNT(*) FROM backfill_chunks WHERE job_id = j.id) as total
FROM backfill_jobs j
WHERE symbol IN ('AAPL', 'NVDA', 'CRWD', 'AMD', 'PLTR', 'AMZN', 'MU')
ORDER BY symbol;
```

**Expected Output:**
```
symbol | pct  | done | total
-------|------|------|------
AAPL   | 0%   | 0    | 523    ← If 0%, backfill hasn't started
NVDA   | 5%   | 26   | 523    ← If >0%, backfill is working!
```

#### B. Check Actual Bar Data
```sql
SELECT
  s.ticker,
  COUNT(*) as bars,
  MIN(b.ts)::date as earliest,
  MAX(b.ts)::date as latest
FROM ohlc_bars_v2 b
JOIN symbols s ON s.id = b.symbol_id
WHERE s.ticker IN ('AAPL', 'NVDA', 'CRWD', 'AMD', 'PLTR', 'AMZN', 'MU')
  AND b.provider = 'polygon'
  AND b.timeframe = 'h1'
GROUP BY s.ticker
ORDER BY s.ticker;
```

**What to Look For:**
- If **no rows returned** → Backfill hasn't inserted any data yet
- If **bars < 100** → Backfill just started
- If **bars > 1000** → Good progress!
- If **latest date is recent** (within 7 days) → Excellent!

#### C. Check AAPL Specifically (Since You're Viewing It)
```sql
-- Use the check-aapl-data.sql file
-- This gives you complete AAPL diagnostics
```

---

## 🚀 If Backfill Hasn't Started

### Check 1: Is GitHub Actions Enabled?

Go to: https://github.com/YOUR_USERNAME/SwiftBolt_ML/actions

- **If disabled**: Click "I understand my workflows, go ahead and enable them"
- **If enabled**: Check the "Backfill Worker Cron" workflow runs

### Check 2: Is SUPABASE_ANON_KEY Secret Set?

Go to: https://github.com/YOUR_USERNAME/SwiftBolt_ML/settings/secrets/actions

- Should have secret named: `SUPABASE_ANON_KEY`
- If missing, add it (see README_BACKFILL.md)

### Check 3: Manually Trigger Backfill

Run in terminal:
```bash
export SUPABASE_ANON_KEY="your-key-here"

curl -X POST \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-backfill" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response:**
```json
{
  "success": true,
  "worker_response": {
    "processed": 4,
    "succeeded": 4,
    "failed": 0
  }
}
```

If `processed: 4` or more → **Working!** ✅
If `processed: 0` → Chunks are either all done or none pending

---

## 📈 Understanding Progress

### Backfill Timeline

- **Per symbol**: 523 chunks (one per trading day for 2 years)
- **Processing rate**: ~4-5 chunks per minute (GitHub Actions: every 5 min)
- **Per symbol time**: ~2-3 hours (with 5-min cron)
- **All 10 symbols**: ~20-30 hours total

### What Happens During Backfill

1. **Hour 0**: 0% complete, no Polygon data yet
   - Your chart may show old Yahoo data from cache
   - This is **normal** - data is still loading

2. **Hour 1**: 2-5% complete per symbol
   - First ~30 days of data inserted
   - Chart starts showing Polygon data for those dates

3. **Hour 5**: 15-25% complete
   - ~150 days of data available
   - Chart can show 5+ months of history

4. **Hour 10**: 50% complete
   - ~1 year of data available
   - Chart can show 12 months of history

5. **Hour 20+**: 100% complete ✅
   - Full 2 years available
   - Chart can show entire historical range

---

## 🔧 Common Issues & Fixes

### Issue 1: "Chart shows old data from 2024"

**Diagnosis**: Backfill hasn't reached recent dates yet

**Fix**: Check backfill progress:
```sql
SELECT symbol, progress FROM backfill_jobs WHERE symbol = 'AAPL';
```

If 0%: Backfill hasn't started (enable GitHub Actions)
If >0%: Be patient, data is loading chronologically

### Issue 2: "No data in database at all"

**Diagnosis**: Edge functions not running

**Fix**:
1. Check edge function logs
2. Manually trigger: `./test-data-health.sh`
3. Verify API keys are correct

### Issue 3: "GitHub Actions failing"

**Diagnosis**: Missing or wrong SUPABASE_ANON_KEY

**Fix**:
1. Go to repo secrets
2. Verify SUPABASE_ANON_KEY is set correctly
3. Get fresh key from Supabase dashboard if needed

### Issue 4: "Chunks stuck in 'pending' status"

**Diagnosis**: Worker not processing chunks

**Fix**:
1. Check edge function logs for errors
2. Verify Polygon API key (MASSIVE_API_KEY) is set
3. Check rate bucket table: `SELECT * FROM rate_buckets;`

---

## 📊 Health Check Files

I've created these tools for you:

1. **[check-data-health.sql](check-data-health.sql)**
   - Comprehensive SQL queries (10 different checks)
   - Run in Supabase SQL Editor
   - Checks: backfill status, bar data, gaps, provider distribution, duplicates

2. **[check-aapl-data.sql](check-aapl-data.sql)**
   - AAPL-specific diagnostics
   - Explains what data your chart is using
   - Identifies why you might see old data

3. **[test-data-health.sh](test-data-health.sh)**
   - Automated terminal test
   - Tests edge functions, database, processing
   - Run with: `./test-data-health.sh`

---

## ✅ Expected Healthy State

After backfill completes, you should see:

### SQL Query Results

```sql
-- Backfill status
symbol | progress | done | total
AAPL   | 100%     | 523  | 523  ✅

-- Bar data
ticker | bars  | earliest    | latest
AAPL   | 3,300 | 2024-01-09  | 2026-01-09  ✅
```

### Chart Behavior

- Shows **2 years** of 1H data
- Can scroll back to 2024-01-09
- Latest data is within **1 week** of today
- No gaps in weekday data
- Smooth scrolling through history

---

## 🎯 Quick Actions

**Right Now:**

1. **Check if backfill is running**:
   ```bash
   export SUPABASE_ANON_KEY="your-key"
   ./test-data-health.sh
   ```

2. **Check progress in SQL**:
   ```sql
   SELECT * FROM backfill_jobs;
   ```

3. **View logs**:
   - Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
   - Click "run-backfill-worker" → Logs

**If Nothing Is Processing:**

1. Enable GitHub Actions
2. Add SUPABASE_ANON_KEY secret
3. Manually trigger workflow once
4. Wait 5 minutes and check again

**If Backfill Is Working But Chart Shows Old Data:**

- This is **normal** during backfill
- Data is inserted chronologically (oldest first)
- Recent data appears after ~50% progress
- Be patient - it's processing!

---

## 📞 Need Help?

Run these and share the results:

```bash
# Test script output
./test-data-health.sh > health-report.txt

# SQL query results
# Copy results from check-data-health.sql
```

---

## 🎉 Success Indicators

You know it's working when:

- ✅ `test-data-health.sh` shows "processed > 0"
- ✅ SQL shows progress increasing over time
- ✅ Bar count increases when you re-run queries
- ✅ Edge function logs show successful chunk processing
- ✅ GitHub Actions show successful runs every 5 minutes

If you see these, **everything is working** - just needs time to complete!
