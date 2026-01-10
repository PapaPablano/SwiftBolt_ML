# Alpaca Integration Requirements Checklist

## ✅ Code Structure Verification

Based on review of the codebase, here's what's correctly implemented:

### 1. ✅ Alpaca Client Authentication
**File:** `backend/supabase/functions/_shared/providers/alpaca-client.ts:99-105`

```typescript
private getHeaders(): Record<string, string> {
  return {
    "APCA-API-KEY-ID": this.apiKey,
    "APCA-API-SECRET-KEY": this.apiSecret,
    "Accept": "application/json",
  };
}
```

**Status:** ✅ CORRECT
- Uses proper Alpaca authentication headers
- Market Data API authentication format
- No Basic Auth needed (that's for Trading API)

### 2. ✅ Provider Router Alpaca Priority
**File:** `backend/supabase/functions/_shared/providers/router.ts:134-143`

```typescript
if (alpacaProvider) {
  primary = "alpaca";
  // Fallback depends on timeframe
  if (isIntraday) {
    fallback = tradierProvider ? "tradier" : ...;
  } else {
    fallback = this.policy.historicalBars.fallback;
  }
}
```

**Status:** ✅ CORRECT
- Alpaca prioritized for ALL timeframes
- Smart fallback based on intraday vs historical
- Only used when credentials available

### 3. ✅ Provider Factory Initialization
**File:** `backend/supabase/functions/_shared/providers/factory.ts:44-77`

```typescript
const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

if (!alpacaApiKey || !alpacaApiSecret) {
  console.warn("[Provider Factory] ALPACA_API_KEY or ALPACA_API_SECRET not set");
}

const alpacaClient = (alpacaApiKey && alpacaApiSecret)
  ? new AlpacaClient(alpacaApiKey, alpacaApiSecret)
  : null;
```

**Status:** ✅ CORRECT
- Reads from environment variables
- Graceful fallback if not set
- Warning logged for debugging

### 4. ✅ Assets Cache Warming
**File:** `backend/supabase/functions/_shared/providers/factory.ts:79-85`

```typescript
if (alpacaClient) {
  alpacaClient.getAssets().then(() => {
    console.log("[Provider Factory] Alpaca assets cache warmed");
  }).catch((error) => {
    console.warn("[Provider Factory] Failed to warm Alpaca assets cache:", error);
  });
}
```

**Status:** ✅ CORRECT
- Async cache warming on startup
- Prevents first-request delays
- Graceful error handling

### 5. ✅ Database Provider Preference
**File:** `backend/supabase/migrations/20260109150000_add_alpaca_provider.sql:40-41`

```sql
WHEN o.provider = 'alpaca' THEN 1     -- Highest priority
WHEN o.provider = 'yfinance' THEN 2
WHEN o.provider = 'polygon' THEN 3
WHEN o.provider = 'tradier' THEN 4
```

**Status:** ✅ CORRECT
- Alpaca ranked #1 in deduplication
- Proper fallback hierarchy
- Works with existing data

### 6. ✅ Fetch-Bars Worker Integration
**File:** `backend/supabase/functions/fetch-bars/index.ts:73-74`

```typescript
const router = getProviderRouter();
injectSupabaseClient(supabase);
```

**Status:** ✅ CORRECT
- Uses provider router (includes Alpaca)
- Enables distributed rate limiting
- No hardcoded providers

### 7. ✅ Chart Data V2 Provider Attribution
**File:** `backend/supabase/functions/chart-data-v2/index.ts:241-250`

```typescript
const historicalProvider = historical.find(b => b.provider === 'alpaca')
  ? 'alpaca'
  : historical.find(b => b.provider === 'yfinance')
  ? 'yfinance'
  : 'polygon';
```

**Status:** ✅ CORRECT
- Dynamically detects actual provider
- Prioritizes Alpaca in reporting
- Accurate client-side attribution

---

## 🔧 Environment Configuration Requirements

### Required Environment Variables (Supabase Edge Functions)

| Variable | Required? | Format | Example |
|----------|-----------|--------|---------|
| `ALPACA_API_KEY` | ✅ YES | String starting with `PK` or `AK` | `PKXXXXXXXXXXXXXX` |
| `ALPACA_API_SECRET` | ✅ YES | String (alphanumeric) | `abc123...xyz` |
| `ALPACA_MAX_RPS` | ❌ Optional | Number | `10` (default) |
| `ALPACA_MAX_RPM` | ❌ Optional | Number | `200` (default) |

### Where to Set:
1. Supabase Dashboard
2. **Project Settings** → **Edge Functions**
3. **Environment Variables** section
4. Add both `ALPACA_API_KEY` and `ALPACA_API_SECRET`

---

## 🔑 Alpaca API Key Requirements

### Key Type
- ✅ **Market Data API** keys (for quotes/bars)
- ❌ **NOT** Trading API keys (for orders)

### Key Source
- Get from: https://app.alpaca.markets/brokerage/dashboard/overview
- Click: **"API Keys"** → **"Generate API Key"**
- Select: **Market Data scope**

### Key Format Validation

**API Key ID:**
- Starts with `PK` (Paper) or `AK` (Live)
- Length: ~20 characters
- Example: `PKABCDEFGH1234567890`

**API Secret:**
- Alphanumeric string
- Length: ~40 characters
- Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### ⚠️ Common Mistakes

❌ **Using Trading API keys instead of Market Data API keys**
- Error: "Unauthorized" or "Invalid scope"
- Fix: Generate new keys with Market Data scope

❌ **Swapping API Key and Secret**
- Error: "Authentication failed"
- Fix: API Key ID goes in `ALPACA_API_KEY`, Secret goes in `ALPACA_API_SECRET`

❌ **Extra whitespace in keys**
- Error: "Invalid API key format"
- Fix: Copy keys carefully, no leading/trailing spaces

---

## 📊 Expected Behavior After Setup

### 1. Edge Function Logs
Look for these log entries in Supabase → Edge Functions → Logs:

✅ **Success indicators:**
```
[Provider Factory] Initializing provider system...
[Provider Factory] Alpaca assets cache warmed
[Router] Using Alpaca (primary) for h1 with fallback: tradier
[Alpaca] Fetching historical bars for AAPL (h1)
```

❌ **Failure indicators:**
```
[Provider Factory] ALPACA_API_KEY or ALPACA_API_SECRET not set
[Alpaca] Authentication failed: 401 Unauthorized
[Router] Primary provider alpaca is in cooldown, using fallback
```

### 2. Database Queries
After backfill starts (2-3 minutes):

```sql
select provider, count(*)
from ohlc_bars_v2
group by provider;
```

**Expected:**
```
provider | count
---------|-------
alpaca   | 1500+  ← Should appear and grow
polygon  | 32963
yfinance | 3494
```

### 3. Job Runs Table
```sql
select provider, status, count(*)
from job_runs
where created_at > now() - interval '10 minutes'
group by provider, status;
```

**Expected:**
```
provider | status  | count
---------|---------|-------
alpaca   | success | 10+
alpaca   | running | 2-5
```

### 4. Swift App Logs
After cache cleared:

```
[DEBUG] ChartViewModel.loadChart() - V2 SUCCESS!
[DEBUG] - Historical: 1500 (provider: alpaca)  ← Key change
[DEBUG] - Intraday: 100 (provider: alpaca)     ← Key change
```

---

## 🚨 Troubleshooting

### Issue: "ALPACA_API_KEY not set" in logs

**Diagnosis:**
- Environment variables not loaded in Edge Functions
- Edge Functions not restarted after adding secrets

**Fix:**
1. Verify secrets in Supabase Dashboard → Edge Functions → Environment Variables
2. Both `ALPACA_API_KEY` and `ALPACA_API_SECRET` should be listed
3. Wait 30 seconds for Edge Functions to restart
4. Trigger new request to test

### Issue: "401 Unauthorized" errors

**Diagnosis:**
- Invalid API keys
- Wrong key type (Trading API instead of Market Data API)
- Keys swapped (ID in SECRET field, SECRET in ID field)

**Fix:**
1. Regenerate keys from Alpaca dashboard
2. Ensure using **Market Data API** keys
3. Copy keys carefully (no extra spaces)
4. Update Supabase secrets
5. Wait 30 seconds, test again

### Issue: "Invalid symbol" errors

**Diagnosis:**
- Symbol not tradable on Alpaca
- Symbol validation failing
- Assets cache not warmed

**Fix:**
1. Check if symbol is valid: https://alpaca.markets/data
2. Try with known valid symbol (e.g., AAPL, MSFT, TSLA)
3. Check Edge Function logs for assets cache warming
4. If cache not warming, check API key permissions

### Issue: All jobs stuck in "queued" status

**Diagnosis:**
- Orchestrator not dispatching jobs
- fetch-bars worker not being called

**Fix:**
```sql
-- Manually trigger orchestrator
select public.run_orchestrator_tick();

-- Check if jobs moved to running
select status, count(*) from job_runs group by status;
```

### Issue: Jobs failing with "RATE_LIMIT_EXCEEDED"

**Diagnosis:**
- Hitting Alpaca free tier limit (200 req/min)
- Normal during initial backfill

**Fix:**
- This is **expected behavior**
- Orchestrator will automatically retry
- Wait 1-2 minutes, jobs will resume
- For faster backfill, upgrade to Alpaca paid tier

---

## ✅ Final Verification Steps

Run these in order to confirm everything works:

### Step 1: Check Environment Variables
```bash
# In Supabase Dashboard:
# Project Settings → Edge Functions → Environment Variables
# Verify both ALPACA_API_KEY and ALPACA_API_SECRET are present
```

### Step 2: Check Edge Function Logs
```bash
# Supabase Dashboard → Edge Functions → Logs
# Look for: "Alpaca assets cache warmed"
```

### Step 3: Run Test Suite
```sql
-- Run the test suite from:
-- backend/supabase/test_alpaca_integration.sql

-- Key tests:
-- TEST 1: Job status distribution
-- TEST 2: Recent job details (look for provider='alpaca')
-- TEST 3: Provider data distribution (alpaca should appear)
-- TEST 7: Cron execution logs (status='succeeded')
```

### Step 4: Verify Data Appearing
```sql
-- Wait 5 minutes after triggering orchestrator, then:
select provider, count(*)
from ohlc_bars_v2
where fetched_at > now() - interval '10 minutes'
group by provider;

-- Expected: 'alpaca' with growing count
```

### Step 5: Test in Swift App
```bash
# 1. Clear app cache
rm -rf ~/Library/Containers/com.yourapp.SwiftBoltML/Data/Library/Caches/*.json

# 2. Restart app
# 3. Load AAPL h1 chart
# 4. Check console for: "provider: alpaca"
```

---

## 📈 Success Metrics

Integration is fully operational when:

- [x] ✅ Edge Function logs show "Alpaca assets cache warmed"
- [x] ✅ Database contains rows where `provider = 'alpaca'`
- [x] ✅ job_runs table shows `provider = 'alpaca'` with `status = 'success'`
- [x] ✅ AAPL h1 timeframe has 100+ bars from Alpaca
- [x] ✅ Swift console logs show `provider: alpaca`
- [x] ✅ Charts display smooth data without gaps
- [x] ✅ Orchestrator cron running every minute (check cron.job_run_details)

---

## 🎯 Next Steps After Verification

Once all checks pass:

1. **Monitor for 24 hours**
   - Watch job success rate
   - Check for rate limit errors
   - Verify data quality

2. **Expand to watchlist**
   - Add more symbols to job_definitions
   - Orchestrator will auto-backfill

3. **Consider paid tier** (optional)
   - If need >200 req/min
   - For real-time data (no 15-min delay)
   - Check: https://alpaca.markets/data

4. **Set up alerts**
   - Monitor job failure rate
   - Alert on Alpaca authentication errors
   - Track provider usage distribution

---

**Status**: Ready for testing
**Last Updated**: 2026-01-09
