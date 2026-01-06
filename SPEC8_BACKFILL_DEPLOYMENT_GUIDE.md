# SPEC-8: Intraday Backfill Orchestration - Deployment Guide

## Overview

This implementation eliminates UI blocking during intraday data loading by moving backfill to server-side Edge Functions with chunked, resumable processing. The client renders immediately from existing data while backfill hydrates in the background.

## Architecture

```
User selects symbol/timeframe
    ↓
Client: loadChart() → render immediately from stored bars
    ↓
Client: ensureCoverageAsync() → POST /ensure-coverage (non-blocking)
    ↓
Server: Check coverage → Create job + chunks if needed
    ↓
Cron: run-backfill-worker (every minute)
    ↓
Worker: Claim chunks → Fetch bars → Upsert to DB
    ↓
Client: (Optional) Realtime updates or manual refresh
```

## Components Implemented

### 1. Database Schema
**File:** `backend/supabase/migrations/20260106000000_backfill_orchestration.sql`

- `backfill_jobs`: Job header with status, progress, error tracking
- `backfill_chunks`: Daily chunks for parallel processing
- Functions: `get_coverage()`, `claim_backfill_chunks()`, `update_job_progress()`
- RLS policies and Realtime publication enabled

### 2. Edge Functions

**ensure-coverage** (`supabase/functions/ensure-coverage/index.ts`)
- Checks existing coverage for symbol/timeframe/window
- Creates idempotent job if coverage missing
- Seeds daily chunks for worker processing
- Returns: `{ hasCoverage, jobId?, coverageFrom, coverageTo }`

**run-backfill-worker** (`supabase/functions/run-backfill-worker/index.ts`)
- Claims 4 pending chunks atomically (SKIP LOCKED)
- Fetches bars via shared provider router
- Upserts to `ohlc_bars_v2` with conflict handling
- Updates chunk status and job progress
- Retries failed chunks up to 3 times

### 3. Shared Provider Adapter
**File:** `supabase/functions/_shared/backfill-adapter.ts`

- `fetchIntradayForDay()`: Fetches bars for single day
- Uses existing `ProviderRouter` (Yahoo Finance primary)
- Normalizes output for `ohlc_bars_v2` schema
- Handles timeframe mapping (15m → m15, etc.)

### 4. Cron Schedule
**File:** `backend/supabase/migrations/20260106010000_backfill_cron_schedule.sql`

- Schedules worker to run every minute via pg_cron
- Uses pg_net to HTTP POST to Edge Function
- Requires `app.settings.service_role_key` and `app.settings.supabase_url` DB settings

### 5. Swift Client Integration

**APIClient.swift**
- `ensureCoverage()`: Calls ensure-coverage Edge Function
- Returns `EnsureCoverageResponse` model

**ChartViewModel.swift**
- `isHydrating`, `backfillProgress`, `backfillJobId` state properties
- `ensureCoverageAsync()`: Non-blocking coverage check
- Triggered automatically on intraday timeframe selection

**Timeframe.swift**
- `backfillWindowDays`: 30 days for 15m, 90 days for 1h/4h

**HydrationBanner.swift**
- Minimal UI indicator: "Hydrating intraday… 45%"
- Shows only when `isHydrating == true`

## Deployment Steps

### Step 1: Apply Database Migrations

```bash
cd backend/supabase
supabase db push
```

This creates:
- `backfill_jobs` and `backfill_chunks` tables
- Helper functions for coverage and chunk claiming
- RLS policies and Realtime publication

### Step 2: Set Database Configuration

Connect to your Supabase database and set required settings:

```sql
-- Set Supabase URL (replace with your project URL)
ALTER DATABASE postgres SET app.settings.supabase_url = 'https://your-project.supabase.co';

-- Set service role key (replace with your actual key from Supabase dashboard)
ALTER DATABASE postgres SET app.settings.service_role_key = 'your-service-role-key-here';
```

**Security Note:** Store the service role key securely. Consider using Supabase Vault in production.

### Step 3: Deploy Edge Functions

```bash
cd supabase/functions

# Deploy ensure-coverage function
supabase functions deploy ensure-coverage

# Deploy run-backfill-worker function
supabase functions deploy run-backfill-worker
```

Verify deployment:
```bash
supabase functions list
```

### Step 4: Enable pg_cron Schedule

The cron schedule is created by the migration, but verify it's active:

```sql
-- Check cron job status
SELECT * FROM get_backfill_cron_status();

-- Should show: jobname = 'backfill-worker-every-minute', schedule = '* * * * *'
```

If not present, manually create:
```sql
SELECT cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    SELECT net.http_post(
      url := current_setting('app.settings.supabase_url', true) || '/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true)
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);
```

### Step 5: Add HydrationBanner to UI

In your main chart view (e.g., `AnalysisView.swift` or `ChartView.swift`), add the banner:

```swift
import SwiftUI

struct YourChartView: View {
    @StateObject var viewModel: ChartViewModel
    
    var body: some View {
        VStack(spacing: 0) {
            // Existing chart header
            
            // Add hydration banner
            HydrationBanner(
                isHydrating: viewModel.isHydrating,
                progress: viewModel.backfillProgress
            )
            
            // Existing chart content
        }
    }
}
```

### Step 6: Build and Test

1. **Build the macOS app:**
   ```bash
   cd client-macos
   xcodebuild -project SwiftBoltML.xcodeproj -scheme SwiftBoltML -configuration Debug
   ```

2. **Test the flow:**
   - Select a symbol (e.g., AAPL)
   - Switch to 15m timeframe
   - Chart should render immediately with existing data
   - Check console for: `[DEBUG] Backfill job created: <job-id>`
   - Verify banner appears if coverage is missing

3. **Monitor backfill progress:**
   ```sql
   -- Check active jobs
   SELECT * FROM backfill_jobs WHERE status != 'done' ORDER BY created_at DESC;
   
   -- Check chunk status
   SELECT job_id, status, count(*) 
   FROM backfill_chunks 
   GROUP BY job_id, status;
   
   -- Check worker logs (via Supabase dashboard)
   ```

## Configuration

### Backfill Windows (Timeframe.swift)

```swift
var backfillWindowDays: Int {
    switch self {
    case .m15: return 30      // 30 days for 15-minute bars
    case .h1, .h4: return 90  // 90 days for hourly bars
    case .d1, .w1: return 365 // 365 days for daily/weekly
    }
}
```

Adjust based on your data retention and provider limits.

### Worker Concurrency (run-backfill-worker/index.ts)

```typescript
const { data: chunks } = await supabase.rpc("claim_backfill_chunks", {
  p_limit: 4,  // Process 4 chunks in parallel
});
```

Increase for faster backfill (watch provider rate limits).

### Retry Policy (run-backfill-worker/index.ts)

```typescript
const newStatus = try_count >= 2 ? "error" : "pending";  // Max 3 attempts
```

## Monitoring & Observability

### Key Metrics

1. **Worker Throughput:**
   ```sql
   SELECT 
     date_trunc('hour', updated_at) as hour,
     count(*) filter (where status = 'done') as completed,
     count(*) filter (where status = 'error') as errors
   FROM backfill_chunks
   WHERE updated_at > now() - interval '24 hours'
   GROUP BY hour
   ORDER BY hour DESC;
   ```

2. **Job Completion Time:**
   ```sql
   SELECT 
     symbol, timeframe,
     extract(epoch from (updated_at - created_at)) / 60 as minutes,
     progress
   FROM backfill_jobs
   WHERE status = 'done' AND updated_at > now() - interval '24 hours'
   ORDER BY updated_at DESC;
   ```

3. **Error Rate:**
   ```sql
   SELECT 
     last_error,
     count(*) as occurrences
   FROM backfill_chunks
   WHERE status = 'error' AND updated_at > now() - interval '24 hours'
   GROUP BY last_error
   ORDER BY occurrences DESC;
   ```

### Supabase Dashboard

- **Edge Functions → Logs:** View worker execution logs
- **Database → Tables:** Inspect `backfill_jobs` and `backfill_chunks`
- **Database → Cron Jobs:** Verify schedule is running

## Troubleshooting

### Issue: Worker not processing chunks

**Check:**
```sql
-- Verify cron job exists
SELECT * FROM cron.job WHERE jobname = 'backfill-worker-every-minute';

-- Check recent cron runs
SELECT * FROM cron.job_run_details 
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'backfill-worker-every-minute')
ORDER BY start_time DESC LIMIT 10;
```

**Fix:** Ensure DB settings are configured and cron extension is enabled.

### Issue: All chunks stuck in "running"

**Cause:** Worker crashed mid-processing.

**Fix:**
```sql
-- Reset stuck chunks to pending
UPDATE backfill_chunks 
SET status = 'pending', updated_at = now()
WHERE status = 'running' AND updated_at < now() - interval '5 minutes';
```

### Issue: Provider rate limit errors

**Check:**
```sql
SELECT last_error FROM backfill_chunks WHERE status = 'error' LIMIT 10;
```

**Fix:** Reduce `p_limit` in worker or add delay between chunks.

### Issue: UI not showing hydration banner

**Check:**
1. Verify `isHydrating` is set in ChartViewModel
2. Check console for coverage check errors
3. Ensure `HydrationBanner` is added to view hierarchy

## Performance Expectations

### Typical Throughput

- **15m bars:** ~26 bars/day → 780 bars/30 days
- **Worker speed:** ~4 days/minute (4 chunks in parallel)
- **Time to 100%:** ~7-8 minutes for 30-day window

### UI Responsiveness

- **First paint:** < 300ms (from cached data)
- **Coverage check:** < 500ms (non-blocking)
- **Chart interaction:** No freezes during hydration

## Future Enhancements

### Phase 2: Realtime Progress (Optional)

Add Supabase Realtime subscription in ChartViewModel:

```swift
import Supabase

func subscribeToBackfillProgress(jobId: String) {
    let channel = supabase.channel("backfill:\(jobId)")
    
    channel.on(.postgresChanges(
        event: .update,
        schema: "public",
        table: "backfill_jobs",
        filter: "id=eq.\(jobId)"
    )) { payload in
        if let progress = payload.record["progress"] as? Int {
            self.backfillProgress = progress
        }
        if let status = payload.record["status"] as? String, status == "done" {
            self.isHydrating = false
            Task { await self.loadChart() }
        }
    }
    
    channel.subscribe()
}
```

### Phase 3: GitHub Actions Bulk Backfill

For overnight universe rehydration:

```yaml
# .github/workflows/bulk-backfill.yml
name: Bulk Backfill
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily

jobs:
  backfill:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger backfill for S&P 500
        run: |
          for symbol in $(cat sp500.txt); do
            curl -X POST "$SUPABASE_URL/functions/v1/ensure-coverage" \
              -H "Authorization: Bearer $SERVICE_KEY" \
              -d "{\"symbol\":\"$symbol\",\"timeframe\":\"15m\",\"fromTs\":\"...\",\"toTs\":\"...\"}"
          done
```

## Summary

**What was implemented:**
✅ Server-side backfill orchestration with Edge Functions  
✅ Chunked, resumable processing with retry logic  
✅ Non-blocking client integration  
✅ Minimal UI feedback (hydration banner)  
✅ Scheduled worker via pg_cron  
✅ Idempotent job creation  
✅ Provider integration via shared router  

**What this fixes:**
✅ UI no longer freezes during intraday data loading  
✅ Backfill runs in background without blocking chart render  
✅ Failed chunks automatically retry  
✅ Multiple users can trigger backfills without conflicts  

**Next steps:**
1. Deploy migrations and Edge Functions
2. Configure DB settings (URL + service key)
3. Test with a few symbols
4. Monitor worker throughput
5. Optionally add Realtime progress updates

For issues or questions, check the troubleshooting section or Supabase Edge Function logs.
