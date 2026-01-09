# Execute Alpaca Fix - Step by Step Guide
**Estimated Time:** 20 minutes + backfill time

---

## Prerequisites Checklist

Before starting, ensure you have:
- [ ] Alpaca Markets account (https://alpaca.markets)
- [ ] Alpaca API keys (Market Data API, not Trading API)
- [ ] Supabase project access (https://app.supabase.com/project/cygflaemtmwiwaviclks)
- [ ] Service Role Key from Supabase

---

## Step 1: Get Your Alpaca API Keys ⏱️ 5 min

### Option A: If you already have an Alpaca account

1. Go to: https://app.alpaca.markets/brokerage/dashboard/overview
2. Click on **"API Keys"** or **"Generate API Key"**
3. Select **"Market Data API"** (NOT "Trading API")
4. Copy both:
   - API Key ID (starts with `PK...` or `AK...`)
   - Secret Key (shown only once!)

### Option B: If you need to create an account

1. Go to: https://alpaca.markets
2. Click **"Sign Up"** → **"Start Trading"**
3. Complete registration (requires email verification)
4. Navigate to API Keys section
5. Generate **Market Data API** keys
6. Copy both API Key ID and Secret Key

**⚠️ IMPORTANT:**
- Use **Market Data API** keys (for quotes/bars)
- NOT Trading API keys (for placing orders)
- Store your Secret Key securely (can't retrieve it later)

---

## Step 2: Set Alpaca Credentials in Supabase ⏱️ 2 min

1. Open Supabase Dashboard:
   - Go to: https://app.supabase.com/project/cygflaemtmwiwaviclks

2. Navigate to Edge Functions Secrets:
   - **Project Settings** (gear icon in sidebar)
   - **Edge Functions** tab
   - Scroll to **"Environment Variables"** section

3. Add two new secrets:

   **Secret 1:**
   - Name: `ALPACA_API_KEY`
   - Value: `[paste your Alpaca API Key ID]`
   - Click **"Add"**

   **Secret 2:**
   - Name: `ALPACA_API_SECRET`
   - Value: `[paste your Alpaca Secret Key]`
   - Click **"Add"**

4. Edge Functions will restart automatically (takes ~30 seconds)

**Verification:**
- Both secrets should appear in the list (values hidden)
- Total secrets should be: FINNHUB_API_KEY, MASSIVE_API_KEY, TRADIER_API_KEY, ALPACA_API_KEY, ALPACA_API_SECRET

---

## Step 3: Get Your Supabase Service Role Key ⏱️ 1 min

1. In Supabase Dashboard, navigate to:
   - **Project Settings** → **API** tab

2. Find the **"Project API keys"** section

3. Copy the **"service_role"** key:
   - It's labeled as `service_role` with a "secret" badge
   - Click the copy icon (📋)
   - Starts with `eyJhbG...` (very long string)

**⚠️ SECURITY WARNING:**
- This key has full database access
- Never commit it to git
- Don't share it publicly
- We'll use it temporarily for setup

---

## Step 4: Configure Cron Authentication ⏱️ 3 min

### Option A: Using Vault (RECOMMENDED - More Secure)

1. In Supabase Dashboard, open **SQL Editor**:
   - Click **"SQL Editor"** in sidebar
   - Click **"New query"**

2. Copy the contents of: `backend/supabase/fix_alpaca_step2_configure_cron_VAULT.sql`

3. **IMPORTANT:** In PART 2 of the script, uncomment the `vault.create_secret()` line and replace `'your-actual-service-role-key'` with your actual service role key from Step 3

4. Execute the entire script (click **"Run"** or press Cmd+Enter)

5. **IMMEDIATELY** comment out the `vault.create_secret()` line again (for security)

6. Check the results:
   - Part 1: Function created successfully
   - Part 2: Secret exists in vault.secrets table
   - Part 3: Cron job scheduled
   - Part 4: Verification queries show everything working

**Expected Output:**
```
✓ Function public.run_orchestrator_tick() created

name         | description                              | created_at
-------------|------------------------------------------|------------------
service_role | Service role key for orchestrator cron   | 2026-01-09...

jobid | schedule   | active | jobname
------|------------|--------|------------------
1     | * * * * *  | true   | orchestrator-tick
```

### Option B: Using Database Settings (Simpler, Less Secure)

1. In Supabase Dashboard, open **SQL Editor**

2. Copy the contents of: `backend/supabase/fix_alpaca_step2_configure_cron.sql`

3. **IMPORTANT:** Replace `YOUR_SERVICE_ROLE_KEY_HERE` with your actual service role key from Step 3

4. Execute the query

5. Verify key_length > 100

**Use Option A (Vault) for production. Option B is OK for development/testing.**

---

## Step 5: Trigger Immediate Backfill ⏱️ 2 min

### Option A: Using the provided script (recommended)

1. Open Terminal and navigate to the backend directory:
   ```bash
   cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase
   ```

2. Set your service role key as an environment variable:
   ```bash
   export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key-here'
   ```

3. Run the backfill script:
   ```bash
   ./fix_alpaca_trigger_backfill.sh
   ```

4. Expected output:
   ```
   🚀 Triggering orchestrator backfill...
   HTTP Status: 200
   Response: { "message": "Tick complete", ... }
   ✅ Orchestrator triggered successfully!
   ```

### Option B: Using curl directly

```bash
curl -X POST "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/orchestrator?action=tick" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY_HERE" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "message": "Tick complete",
  "duration": 234,
  "results": {
    "scanned": 1,
    "slices_created": 5,
    "jobs_dispatched": 5,
    "errors": []
  }
}
```

---

## Step 6: Monitor Backfill Progress ⏱️ 5 min

1. In Supabase **SQL Editor**, run the verification queries from:
   `backend/supabase/fix_alpaca_verify.sql`

2. Key queries to watch:

   **Check Alpaca data appearing:**
   ```sql
   select provider, count(*) as bar_count
   from ohlc_bars_v2
   group by provider
   order by bar_count desc;
   ```

   **Expected:** You'll start seeing rows with `provider = 'alpaca'`

   **Check job runs:**
   ```sql
   select symbol, timeframe, status, rows_written, provider, created_at
   from job_runs
   order by created_at desc
   limit 10;
   ```

   **Expected:** Rows with `status = 'success'` or `'running'`

3. Wait 2-3 minutes between checks to see progress

**Backfill Timeline:**
- First few jobs: Complete in ~30 seconds each
- AAPL h1 full backfill: ~10-30 minutes
- All symbols: ~1-2 hours (runs automatically in background)

---

## Step 7: Clear Swift App Cache ⏱️ 2 min

The Swift app has cached the old broken data (9 bars). We need to clear it.

### Option A: Manual file deletion (fastest)

1. Open Terminal:
   ```bash
   rm -rf ~/Library/Containers/com.yourapp.SwiftBoltML/Data/Library/Caches/*.json
   ```

2. Restart your Swift app

### Option B: Add clear cache functionality to app

1. Open: `client-macos/SwiftBoltML/Services/ChartCache.swift`

2. Add this method to the `ChartCache` class:
   ```swift
   func clearAll() {
       do {
           let contents = try FileManager.default.contentsOfDirectory(
               at: cacheDirectory,
               includingPropertiesForKeys: nil
           )
           for file in contents {
               try FileManager.default.removeItem(at: file)
           }
           print("[ChartCache] Cleared all cached files: \(contents.count)")
       } catch {
           print("[ChartCache] Error clearing cache: \(error)")
       }
   }
   ```

3. Call it from a debug menu or add to your app:
   ```swift
   // In ContentView or a debug menu:
   Button("Clear Cache") {
       ChartCache.shared.clearAll()
   }
   ```

4. Run the app, click "Clear Cache", then restart

---

## Step 8: Verify Everything Works ⏱️ 5 min

### 1. Check Edge Function Logs

1. In Supabase Dashboard → **Edge Functions** → **Logs**
2. Look for recent entries
3. Expected logs:
   ```
   [Provider Factory] Initializing provider system...
   [Provider Factory] Alpaca assets cache warmed
   [Router] Using Alpaca (primary) for h1 with fallback: tradier
   ```

### 2. Check Database Data

Run in SQL Editor:
```sql
select count(*) as alpaca_bars
from ohlc_bars_v2
where provider = 'alpaca';
```

**Expected:** > 100 (and growing)

### 3. Test Swift App

1. Launch your app
2. Load AAPL chart
3. Switch to h1 (hourly) timeframe
4. Check console logs

**Expected Console Output:**
```
[DEBUG] ChartViewModel.loadChart() - V2 SUCCESS!
[DEBUG] - Historical: 1500 (provider: alpaca)
[DEBUG] - Intraday: 100 (provider: alpaca)
[DEBUG] - Final bars: 1600
```

**Key Changes:**
- ✅ `provider: alpaca` (not polygon/tradier)
- ✅ Hundreds/thousands of bars (not 9)
- ✅ Chart shows complete historical data

### 4. Visual Verification

The chart should now show:
- ✅ Smooth, continuous price action
- ✅ No huge gaps
- ✅ Correct current price
- ✅ Full historical coverage

---

## Troubleshooting

### Issue: "Rate limit exceeded" in logs

**Cause:** Hitting Alpaca free tier limit (200 req/min)

**Fix:** This is normal during initial backfill. The orchestrator will automatically retry. Just wait 1-2 minutes.

### Issue: Still showing polygon/tradier provider

**Possible causes:**
1. **Credentials not set correctly** → Go back to Step 2, verify both secrets are added
2. **App using cached data** → Complete Step 7 to clear cache
3. **Backfill not started yet** → Wait 5 minutes, check job_runs table

### Issue: No job_runs appearing in database

**Cause:** Cron authentication failed

**Fix:**
1. Verify Step 4 was completed correctly
2. Check the database settings:
   ```sql
   select current_setting('app.supabase_service_role_key', true);
   ```
3. Should return your key (not NULL)
4. If NULL, re-run Step 4 SQL

### Issue: Jobs stuck in "queued" status

**Cause:** Orchestrator not dispatching jobs

**Fix:** Manually trigger again:
```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase
./fix_alpaca_trigger_backfill.sh
```

### Issue: "Invalid API key" errors in Edge Function logs

**Cause:** Wrong Alpaca keys or wrong type

**Fix:**
1. Verify you used **Market Data API** keys (not Trading API)
2. Check for typos in the secrets
3. Regenerate keys from Alpaca dashboard if needed

---

## Success Checklist

After completing all steps, verify:

- [ ] Edge Function logs show: "Alpaca assets cache warmed"
- [ ] Database has rows where `provider = 'alpaca'` (>100)
- [ ] job_runs table shows recent successes
- [ ] Swift console shows `provider: alpaca`
- [ ] Charts display hundreds/thousands of bars (not 9)
- [ ] No huge gaps in price data
- [ ] Orchestrator cron running every minute

---

## Next Steps

Once everything is working:

1. **Monitor for 24 hours:**
   - Check job_runs for failures
   - Watch for rate limit errors
   - Verify data quality

2. **Add more symbols to watchlist:**
   - Each will auto-backfill via orchestrator

3. **Consider Alpaca paid tier:**
   - If you need more than 200 req/min
   - For real-time data (no 15-min delay)
   - Check pricing: https://alpaca.markets/data

4. **Set up monitoring dashboard:**
   - Track provider usage
   - Monitor job success rates
   - Alert on failures

---

## Timeline Summary

| Step | Time | What Happens |
|------|------|--------------|
| 1. Get Alpaca keys | 5 min | Create account, generate keys |
| 2. Set credentials | 2 min | Add to Supabase secrets |
| 3. Get service key | 1 min | Copy from Supabase |
| 4. Configure cron | 3 min | Run SQL to enable auth |
| 5. Trigger backfill | 2 min | Kick off orchestrator |
| 6. Monitor progress | 5 min | Watch jobs complete |
| 7. Clear app cache | 2 min | Remove old data |
| 8. Verify working | 5 min | Test everything |
| **Total** | **25 min** | |
| **Plus backfill** | **10-30 min** | Runs in background |

---

## Questions or Issues?

If you get stuck:

1. Check the specific troubleshooting section above
2. Review the logs:
   - Supabase → Edge Functions → Logs
   - Supabase → SQL Editor → Run verification queries
   - Swift app console output
3. Look for error messages and search the fix plan

Still stuck? Gather these details:
- Screenshot of Edge Function logs (last 50 lines)
- Result of SQL query: `select * from job_runs order by created_at desc limit 5;`
- Swift console output when loading chart
- Error messages (if any)

---

**Ready to start? Begin with Step 1! ⬆️**
