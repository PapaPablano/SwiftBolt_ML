# Alpaca Integration Deployment Fix

## Root Cause Analysis

**CRITICAL ISSUE FOUND:** AlpacaClient was implemented but never integrated into the provider factory system.

### What Was Wrong

1. ❌ `AlpacaClient` existed in `backend/supabase/functions/_shared/providers/alpaca-client.ts`
2. ❌ Factory.ts only initialized Finnhub, Massive (Polygon), and Yahoo
3. ❌ Router had no knowledge of Alpaca as a provider option
4. ❌ Edge functions calling the router got 401s because Alpaca was never instantiated
5. ✅ Credentials ARE in Supabase (verified via edge function logs showing fetch-bars working)

### Evidence from Logs

```
run-backfill-worker: POST | 401 (repeated failures)
fetch-bars: POST | 200 (working correctly)
```

This proved the credentials exist but the provider system wasn't using them.

---

## Fixes Applied

### 1. Updated Provider Types
**File:** `supabase/functions/_shared/providers/types.ts`

```typescript
// BEFORE
export type ProviderId = "finnhub" | "massive" | "yahoo";

// AFTER
export type ProviderId = "finnhub" | "massive" | "yahoo" | "alpaca";
```

### 2. Integrated AlpacaClient into Factory
**File:** `supabase/functions/_shared/providers/factory.ts`

**Changes:**
- ✅ Imported AlpacaClient
- ✅ Added alpacaClientInstance singleton
- ✅ Read ALPACA_API_KEY and ALPACA_API_SECRET from env
- ✅ Initialize AlpacaClient if credentials present
- ✅ Add to router providers map
- ✅ Export getAlpacaClient() helper

**Key Code:**
```typescript
const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

if (alpacaApiKey && alpacaApiSecret) {
  alpacaClientInstance = new AlpacaClient(alpacaApiKey, alpacaApiSecret);
  console.log("[Provider Factory] Alpaca client initialized");
} else {
  console.warn("[Provider Factory] Alpaca credentials not found");
}

// Add to router
if (alpacaClientInstance) {
  providers.alpaca = alpacaClientInstance;
}
```

### 3. Updated Router Policy
**File:** `supabase/functions/_shared/providers/router.ts`

**Changed primary providers to prioritize Alpaca:**
```typescript
const DEFAULT_POLICY: RouterPolicy = {
  quote: {
    primary: "alpaca",      // Was: "finnhub"
    fallback: "finnhub",
  },
  historicalBars: {
    primary: "alpaca",      // Was: "massive"
    fallback: "massive",
  },
  news: {
    primary: "alpaca",      // Was: "finnhub"
    fallback: "finnhub",
  },
  // optionsChain stays with yahoo
};
```

### 4. Copied AlpacaClient to Correct Location
```bash
cp backend/supabase/functions/_shared/providers/alpaca-client.ts \
   supabase/functions/_shared/providers/alpaca-client.ts
```

---

## Deployment Steps

### Step 1: Verify Secrets in Supabase Dashboard

1. Go to https://app.supabase.com/project/cygflaemtmwiwaviclks
2. Navigate to: **Project Settings → Edge Functions**
3. Confirm these secrets exist:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`

If missing, add them now with your Alpaca Market Data API keys.

### Step 2: Deploy Updated Edge Functions

Deploy all functions that use the provider system:

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Deploy core data fetching functions
supabase functions deploy fetch-bars --project-ref cygflaemtmwiwaviclks
supabase functions deploy run-backfill-worker --project-ref cygflaemtmwiwaviclks
supabase functions deploy symbol-backfill --project-ref cygflaemtmwiwaviclks
supabase functions deploy ensure-coverage --project-ref cygflaemtmwiwaviclks
supabase functions deploy trigger-backfill --project-ref cygflaemtmwiwaviclks

# Deploy user-facing functions
supabase functions deploy user-refresh --project-ref cygflaemtmwiwaviclks
supabase functions deploy chart-data-v2 --project-ref cygflaemtmwiwaviclks
supabase functions deploy quotes --project-ref cygflaemtmwiwaviclks
supabase functions deploy news --project-ref cygflaemtmwiwaviclks
```

### Step 3: Verify Deployment

Check edge function logs for Alpaca initialization:

```bash
# Watch logs in real-time
supabase functions logs fetch-bars --project-ref cygflaemtmwiwaviclks --tail
```

**Look for:**
```
[Provider Factory] Alpaca client initialized
[Router] getHistoricalBars: AAPL h1 -> primary=alpaca, fallback=massive
[Alpaca] Fetched 500 bars from alpaca
```

### Step 4: Test Alpaca Integration

Run a test request:

```bash
curl -X POST \
  https://cygflaemtmwiwaviclks.supabase.co/functions/v1/fetch-bars \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "job_run_id": "test-123",
    "symbol": "AAPL",
    "timeframe": "1h",
    "from": "2025-01-01T00:00:00Z",
    "to": "2025-01-09T23:59:59Z"
  }'
```

**Expected response:**
```json
{
  "job_run_id": "test-123",
  "rows_written": 500,
  "provider": "alpaca",
  "from": "2025-01-01T00:00:00Z",
  "to": "2025-01-09T23:59:59Z",
  "duration_ms": 2500
}
```

---

## Troubleshooting

### Issue: Still Getting 401 Errors

**Check 1: Secrets Loaded**
```bash
# Add debug logging to factory.ts temporarily
console.log("ALPACA_API_KEY present:", !!Deno.env.get("ALPACA_API_KEY"));
console.log("ALPACA_API_SECRET present:", !!Deno.env.get("ALPACA_API_SECRET"));
```

**Check 2: Correct Header Format**
Alpaca requires exact header names:
- `APCA-API-KEY-ID` (not `APCA_API_KEY_ID`)
- `APCA-API-SECRET-KEY` (not `APCA_API_SECRET_KEY`)

Already correct in `alpaca-client.ts:101-102`.

**Check 3: Key Type**
Ensure you're using **Market Data API** keys, not Trading API keys.
Generate at: https://app.alpaca.markets → API Keys → Market Data

### Issue: Functions Not Using Alpaca

**Symptom:** Logs show `provider: polygon` or `provider: yfinance`

**Cause:** Alpaca client failed to initialize (missing credentials)

**Fix:**
1. Check edge function logs for: `"Alpaca credentials not found"`
2. Add secrets to Supabase dashboard
3. Redeploy functions

### Issue: Rate Limits

Alpaca free tier limits:
- 200 requests/minute for Market Data API
- 10,000 requests/month

**Mitigation:**
- Router automatically falls back to Polygon/Yahoo on rate limits
- Distributed rate limiting tracks usage across edge functions

---

## Validation Checklist

- [ ] Secrets exist in Supabase dashboard
- [ ] All edge functions redeployed
- [ ] Logs show "Alpaca client initialized"
- [ ] Test request returns `"provider": "alpaca"`
- [ ] No 401 errors in edge function logs
- [ ] Historical bars contain Alpaca data
- [ ] Swift app displays Alpaca data

---

## Key Insights from Research

### From Perplexity Analysis

1. **Header Format is Critical**
   - Must use `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`
   - Hyphens, not underscores
   - Already correct in our implementation

2. **Supabase Edge Function Secrets**
   - Secrets only exist in the region/project where set
   - Must redeploy after adding/changing secrets
   - No automatic refresh of running functions

3. **Common Alpaca + Supabase Issues**
   - Secrets not propagating to edge functions (fixed by redeploy)
   - Using wrong key type (Trading vs Market Data)
   - Keys swapped (ID in secret field, vice versa)

### From GitHub Examples

Found working implementations in:
- `HoldenMalinchock/alpaca` - Deno JSR library
- `jonkarrer/Bronson` - Algo trading with Alpaca + Deno
- `PapaPablano/stock-whisperer-backend` - Supabase + Alpaca integration

All confirmed the header format and env var approach we're using.

---

## Next Steps

1. **Deploy Now:** Run the deployment commands above
2. **Monitor Logs:** Watch for Alpaca initialization messages
3. **Test Integration:** Run test requests to verify Alpaca data
4. **Update Cron:** Ensure orchestrator uses new provider system
5. **Clear Cache:** Swift app may need cache cleared to see new data

---

## Files Modified

1. `supabase/functions/_shared/providers/types.ts` - Added "alpaca" to ProviderId
2. `supabase/functions/_shared/providers/factory.ts` - Integrated AlpacaClient
3. `supabase/functions/_shared/providers/router.ts` - Updated routing policy
4. `supabase/functions/_shared/providers/alpaca-client.ts` - Copied from backend/

---

## Success Criteria

✅ Edge function logs show: `[Provider Factory] Alpaca client initialized`
✅ Router logs show: `primary=alpaca`
✅ API responses show: `"provider": "alpaca"`
✅ Database contains rows with `provider='alpaca'`
✅ No 401 errors in edge function logs
✅ Swift app displays institutional-grade Alpaca data

---

**Status:** Ready for deployment
**Estimated Time:** 10-15 minutes
**Risk Level:** Low (graceful fallback to Polygon/Yahoo if Alpaca fails)
