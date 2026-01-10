# Alpaca Integration Fix Plan
**Date:** January 9, 2026
**Status:** 🔴 CRITICAL ISSUES IDENTIFIED

## Executive Summary

The Alpaca integration **code is correct** but **not operational** due to missing configuration. Your app is currently using degraded data sources (polygon/tradier) with severe gaps (only 9 bars for 2-year intraday period).

---

## Critical Issues

### 1. Missing Alpaca Credentials
**Impact:** HIGH - Alpaca never used, falling back to inferior providers
**Status:** 🔴 NOT CONFIGURED

### 2. Severe Intraday Data Gaps
**Impact:** CRITICAL - App shows incorrect chart data (9 bars over 2 years for h1)
**Status:** 🔴 BROKEN

### 3. Orchestrator Cron Not Authenticating
**Impact:** HIGH - Background data backfill completely broken
**Status:** 🔴 NOT WORKING

---

## Fix Steps (Execute in Order)

### Step 1: Set Alpaca Credentials ⏱️ 2 minutes

1. Go to Supabase Dashboard:
   - https://app.supabase.com/project/cygflaemtmwiwaviclks

2. Navigate to: **Project Settings → Edge Functions → Secrets**

3. Add environment variables:
   ```bash
   ALPACA_API_KEY=<your-alpaca-api-key>
   ALPACA_API_SECRET=<your-alpaca-api-secret>
   ```

4. Get your keys from: https://app.alpaca.markets/brokerage/dashboard/overview

5. Restart Edge Functions (automatic after saving secrets)

**Verification:**
```bash
# Call any Edge Function and check logs for:
# "[Provider Factory] Alpaca assets cache warmed"
```

---

### Step 2: Configure Cron Authentication ⏱️ 5 minutes

1. Get your Service Role Key from Supabase Dashboard:
   - **Project Settings → API → service_role secret**

2. Run this SQL in Supabase SQL Editor:
   ```sql
   -- Set Supabase URL
   alter database postgres set app.supabase_url = 'https://cygflaemtmwiwaviclks.supabase.co';

   -- Set service role key (REPLACE WITH ACTUAL KEY)
   alter database postgres set app.supabase_service_role_key = 'eyJhb...your_actual_key';
   ```

3. Verify cron job exists:
   ```sql
   select jobid, schedule, command, active
   from cron.job
   where jobname = 'orchestrator-tick';
   ```

   **Expected:** One row with `active = true`, schedule = `* * * * *`

**Verification:**
```sql
-- Check orchestrator ran recently
select * from job_runs
order by created_at desc
limit 5;

-- Should see rows with status 'queued', 'running', or 'success'
```

---

### Step 3: Trigger Immediate Backfill ⏱️ 10 minutes

After credentials and cron are configured:

1. Manually trigger orchestrator to process pending gaps:
   ```bash
   curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick" \
     -H "Authorization: Bearer <SERVICE_ROLE_KEY>" \
     -H "Content-Type: application/json"
   ```

2. Monitor job progress:
   ```sql
   select symbol, timeframe, status, rows_written, provider, created_at
   from job_runs
   where symbol = 'AAPL' and timeframe = 'h1'
   order by created_at desc
   limit 10;
   ```

3. Watch for Alpaca provider:
   ```sql
   select provider, count(*)
   from ohlc_bars_v2
   where symbol_id = (select id from symbols where ticker = 'AAPL')
     and timeframe = 'h1'
   group by provider;
   ```

**Expected:** Rows with `provider = 'alpaca'` appearing

---

### Step 4: Clear Bad Cache & Reload App ⏱️ 2 minutes

Your Swift app has cached the broken 9-bar dataset:

1. In your Swift app, delete cached files:
   ```swift
   // In ChartCache.swift, add a method:
   func clearAll() {
       try? FileManager.default.removeItem(at: cacheDirectory)
   }

   // Call from debug menu or app launch
   ChartCache.shared.clearAll()
   ```

2. Or manually delete:
   ```bash
   rm ~/Library/Containers/com.yourapp.SwiftBoltML/Data/Library/Caches/*.json
   ```

3. Restart app and load AAPL/h1 chart

**Expected Logs:**
```
[DEBUG] ChartViewModel.loadChart() - V2 SUCCESS!
[DEBUG] - Historical: XXX (provider: alpaca)  ← Should see 'alpaca' now
[DEBUG] - Intraday: YYY (provider: alpaca)    ← Should see 'alpaca' now
```

---

## Verification Checklist

After completing all steps:

- [ ] **Alpaca credentials appear in Supabase Edge Function logs**
  - Look for: `[Provider Factory] Alpaca assets cache warmed`

- [ ] **Orchestrator cron job is running**
  - SQL: `select count(*) from job_runs where created_at > now() - interval '10 minutes';`
  - Expected: > 0 rows

- [ ] **Alpaca data appearing in database**
  - SQL: `select count(*) from ohlc_bars_v2 where provider = 'alpaca';`
  - Expected: > 0 rows

- [ ] **Swift app logs show Alpaca provider**
  - Console: `provider: alpaca` (not polygon/tradier)

- [ ] **Intraday charts show hundreds of bars**
  - Expected: ~2000+ bars for 730-day window (h1 timeframe)
  - Currently showing: 9 bars ⚠️

---

## Root Cause Analysis

### Why Alpaca Never Worked:

1. **Credentials:** Environment variables `ALPACA_API_KEY` and `ALPACA_API_SECRET` were never set in Supabase Edge Functions
   - Factory.ts checks for these (line 44-46)
   - Logs warning if missing (line 55-57)
   - Falls back to legacy providers (polygon/tradier)

2. **Orchestrator:** Cron job created but cannot authenticate
   - Migration created cron job (20260107000000_spec8_unified_orchestrator.sql)
   - But `app.supabase_service_role_key` not set in database
   - Cron calls fail with authentication error
   - Gaps never filled

3. **Data Gaps:** Existing database has minimal intraday data
   - Only 9 bars for AAPL h1 timeframe
   - Spans 2024-01-25 to 2026-01-08 (2 years, 9 bars!)
   - Clearly from initial testing, not production backfill
   - Swift app caches this bad data

### Why Console Shows Wrong Providers:

Looking at your logs:
```
[DEBUG] - Historical: 498 (provider: polygon)
[DEBUG] - Intraday: 9 (provider: tradier)
```

The chart-data-v2 Edge Function correctly queries the database and reports the **actual** provider stored in each bar record. Since Alpaca was never fetching data, only polygon/tradier/yfinance data exists.

The provider labels are **accurate** - they're showing what's actually in your database, which is NOT from Alpaca (because credentials were never configured).

---

## Expected Improvements After Fix

### Data Quality
- **Before:** 9 hourly bars over 2 years (useless)
- **After:** 2000+ hourly bars with clean coverage
- **Provider:** Institutional-grade Alpaca data (7+ years history)

### Chart Accuracy
- **Before:** Huge gaps, incorrect prices, old data
- **After:** Complete historical + intraday coverage
- **Split-adjusted:** Automatic from Alpaca

### Provider Attribution
- **Before:** Logs show `polygon`, `tradier`, `yfinance`
- **After:** Logs show `alpaca` as primary for all timeframes

### Reliability
- **Before:** Gaps detected but never filled (orchestrator broken)
- **After:** Automatic backfill via cron every 1 minute
- **Monitoring:** Real-time job_runs table tracks progress

---

## Monitoring Post-Fix

### 1. Provider Usage (Daily Check)
```sql
select provider, count(*) as bar_count
from ohlc_bars_v2
where fetched_at > now() - interval '1 day'
group by provider
order by bar_count desc;
```

**Expected:** `alpaca` should be #1

### 2. Orchestrator Health (Daily Check)
```sql
select
  status,
  count(*) as count,
  avg(rows_written) as avg_bars,
  max(finished_at) as last_run
from job_runs
where created_at > now() - interval '1 day'
group by status;
```

**Expected:**
- `success`: majority of jobs
- `failed`: < 5%
- `last_run`: within last 10 minutes

### 3. Coverage Status (Weekly Check)
```sql
select symbol, timeframe, from_ts, to_ts, last_success_at
from coverage_status
where symbol = 'AAPL'
order by timeframe;
```

**Expected:** All timeframes have recent `last_success_at` timestamps

### 4. Rate Limit Errors (Monitor)
```sql
select count(*) as rate_limit_errors
from job_runs
where error_code = 'RATE_LIMIT_EXCEEDED'
  and created_at > now() - interval '1 hour';
```

**Expected:** 0 (Alpaca free tier: 200 req/min should be sufficient)

---

## Troubleshooting

### Issue: Still seeing polygon/tradier after Step 1
**Cause:** Old data still in database
**Fix:** Complete Steps 2-3 to backfill with Alpaca data

### Issue: Orchestrator not creating job_runs
**Cause:** Cron authentication failed
**Fix:** Verify Step 2 SQL was executed correctly
```sql
select current_setting('app.supabase_service_role_key', true);
-- Should return your actual key, not NULL
```

### Issue: Job runs stuck in "queued"
**Cause:** Orchestrator dispatch failing
**Fix:** Manually trigger:
```bash
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick" \
  -H "Authorization: Bearer <SERVICE_ROLE_KEY>"
```

### Issue: Swift app still shows 9 bars
**Cause:** App using cached data
**Fix:** Complete Step 4 to clear cache

### Issue: Alpaca authentication errors in logs
**Cause:** Invalid API keys
**Fix:** Verify keys from https://app.alpaca.markets
- Must use "Market Data API" keys (not Trading API)
- Must be from your Alpaca Markets account

---

## Timeline Estimate

| Step | Time | Critical? |
|------|------|-----------|
| Set Alpaca credentials | 2 min | ✅ YES |
| Configure cron auth | 5 min | ✅ YES |
| Trigger backfill | 10 min | ✅ YES |
| Clear app cache | 2 min | ⚠️ RECOMMENDED |
| **Total** | **19 min** | |

**Backfill Duration:**
- AAPL h1 (2-year backfill): ~10-30 minutes
- All watchlist symbols: ~1-2 hours
- Rate limited by: Alpaca free tier (200 req/min)

---

## Success Criteria

✅ **Integration is working when:**

1. Edge Function logs show: `[Provider Factory] Alpaca assets cache warmed`
2. Database query shows Alpaca bars: `select count(*) from ohlc_bars_v2 where provider = 'alpaca'; -- > 1000`
3. Swift console logs show: `provider: alpaca` (not polygon)
4. Charts display hundreds/thousands of bars (not 9)
5. Job runs table shows recent successes: `select max(finished_at) from job_runs; -- within last 10 min`

---

## Questions?

If issues persist after following this plan:

1. Export Edge Function logs (last 100 lines)
2. Export SQL query result: `select * from job_runs order by created_at desc limit 10;`
3. Export Swift console logs showing provider attribution
4. Share all three for further debugging

---

**Priority:** 🔴 CRITICAL - Execute immediately to restore app functionality
**Estimated Fix Time:** 20 minutes + backfill time
**Risk:** LOW - All changes are configuration, no code changes required
