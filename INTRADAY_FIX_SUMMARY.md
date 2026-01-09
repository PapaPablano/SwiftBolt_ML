# Intraday Data Issue Diagnosis & Fix

**Date**: 2026-01-09
**Status**: Issues Identified - Ready to Fix

## Issues Found in Console Logs

### 1. ❌ Old Polygon Data Still in Database
Your console shows:
```json
"provider":"polygon"  // For NVDA h1 historical data
```

**Problem**: The database still contains old Polygon data from before we switched to Alpaca. The chart is displaying this outdated data.

**Impact**:
- AAPL h1: Only 9 bars (very sparse, from 2024)
- NVDA h1: 67 bars from Polygon + 6 intraday (dates from 2024)
- Data is 2 years old when it should be current

### 2. ❌ Backfill Not Yet Run
The system detects gaps correctly:
```
"gaps_detected" status with "gaps_found":2 for AAPL
```

**Problem**: The backfill worker hasn't processed these symbols yet, or the jobs weren't created.

### 3. ✅ What IS Working
- Daily (d1) data: 498 bars from yfinance ✓
- News API: Loading correctly ✓
- Options chain: Loading correctly ✓
- Gap detection: System knows data is incomplete ✓
- Provider routing: Alpaca primary, fallbacks configured ✓

## Root Cause

The **backfill orchestration** hasn't been triggered for AAPL and NVDA on the h1 timeframe. The old Polygon data exists from previous testing, but new Alpaca data hasn't been populated yet.

## The Fix (Simple 3-Step Process)

I've created automated scripts to fix this:

###  Step 1: Run Diagnostics

```bash
cd backend
./scripts/fix-intraday-data.sh
```

This will:
1. Show current provider distribution
2. Display backfill job status
3. Check Alpaca coverage
4. Identify old Polygon data

### Step 2: Trigger Backfill (Interactive)

The script will ask if you want to trigger backfill. Answer **"y"**.

This will:
1. Create backfill jobs for AAPL and NVDA (h1 timeframe, last 2 years)
2. Call the `run-backfill-worker` edge function
3. Start processing chunks with Alpaca API

### Step 3: Monitor Progress

Re-run the diagnostic script to see progress:
```bash
./scripts/fix-intraday-data.sh
```

Watch for:
- `alpaca_bars` count increasing
- `completed_chunks` progressing
- Provider changing from "polygon" to "alpaca"

## Manual Alternative (If Scripts Don't Work)

### Option A: SQL Commands

```bash
cd backend

# 1. Diagnose
npx supabase db execute --file scripts/diagnose-intraday-data.sql --linked

# 2. Create jobs
npx supabase db execute --file scripts/trigger-alpaca-backfill.sql --linked

# 3. Trigger worker
curl -X POST \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  https://YOUR_PROJECT.supabase.co/functions/v1/run-backfill-worker
```

### Option B: Database Direct

Connect to your Supabase database and run:

```sql
-- Create backfill jobs for AAPL and NVDA
INSERT INTO backfill_jobs (symbol_id, timeframe, start_date, end_date, status, priority)
SELECT
  id,
  'h1',
  (CURRENT_DATE - INTERVAL '730 days')::DATE,
  CURRENT_DATE,
  'pending',
  10
FROM symbols
WHERE ticker IN ('AAPL', 'NVDA')
ON CONFLICT (symbol_id, timeframe, start_date, end_date)
DO UPDATE SET status = 'pending', priority = 10;
```

Then call the worker edge function or wait for the cron job to pick it up.

## Expected Timeline

- **Immediate**: Jobs created, worker starts processing
- **5-10 minutes**: First chunks complete, data appears in database
- **30-60 minutes**: Full 2-year history populated for both symbols (730 days × hourly bars)

## How to Verify It's Fixed

1. **In Console Logs**: Look for `"provider":"alpaca"` instead of `"provider":"polygon"`
2. **Bar Count**: Should see hundreds of bars instead of 9 or 73
3. **Dates**: Should see current dates (2026-01-XX) instead of 2024 dates
4. **Chart**: Will display much more data with proper continuity

## Non-Issues (Ignore These)

Your console also shows many WebContent errors. These are **harmless macOS sandbox warnings**:

- ✅ `Connection to 'pboard' server` - Normal sandbox restriction
- ✅ `CRASHSTRING: XPC_ERROR_CONNECTION_INVALID` - Misleading name, not a crash
- ✅ `RunningBoard assertions` - Normal WKWebView entitlement warnings
- ✅ `Network error: Code=-999 cancelled` - GOOD! Your app is properly cancelling redundant requests

These don't affect functionality and are expected in sandboxed macOS apps.

## Files Created

1. **[diagnose-intraday-data.sql](backend/scripts/diagnose-intraday-data.sql)** - Database diagnostic queries
2. **[trigger-alpaca-backfill.sql](backend/scripts/trigger-alpaca-backfill.sql)** - Create backfill jobs
3. **[fix-intraday-data.sh](backend/scripts/fix-intraday-data.sh)** - Automated fix script (recommended)

## Code Changes Summary

Already completed:
- ✅ Removed Massive/Polygon API requirement from provider factory
- ✅ Updated router to use Alpaca as primary with proper fallbacks
- ✅ Updated backfill adapter to write Alpaca provider name
- ✅ Database migrations in place for Alpaca support
- ✅ Provider type definitions include Alpaca

## Next Actions

1. Run `./backend/scripts/fix-intraday-data.sh`
2. Answer "y" when prompted to trigger backfill
3. Wait 5-10 minutes
4. Refresh your app and check the h1 chart
5. You should see current, complete data from Alpaca!

---

**Questions?** The scripts include helpful output messages to guide you through each step.
