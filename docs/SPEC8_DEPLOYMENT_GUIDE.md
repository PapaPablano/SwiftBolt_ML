# SPEC-8: Unified Market Data Orchestrator - Deployment Guide

## Overview

SPEC-8 consolidates all market data operations (intraday, historical, forecasting) into a single, observable, and reliable orchestration system. This guide walks through deployment and verification.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Cron                       │
│                    (Every 1 minute)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Function                     │
│  • Scans job_definitions                                     │
│  • Checks coverage_status for gaps                           │
│  • Creates job_runs (slices)                                 │
│  • Dispatches to workers                                     │
└────────┬────────────────────────────┬─────────────────────┘
         │                            │
         ▼                            ▼
┌──────────────────┐        ┌──────────────────┐
│  fetch-bars      │        │  forecast-worker │
│  • Calls provider│        │  (Phase 2)       │
│  • Upserts bars  │        │                  │
│  • Updates status│        │                  │
└──────────────────┘        └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Tables                           │
│  • job_definitions (templates)                               │
│  • job_runs (execution slices with Realtime)                │
│  • coverage_status (quick lookup)                            │
│  • ohlc_bars_v2 (data storage)                              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Client (SwiftUI)                          │
│  • Calls ensure-coverage on symbol select                    │
│  • Subscribes to job_runs via Realtime                       │
│  • Shows progress ribbon                                     │
│  • Queries chart-data-v2 for display                         │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Supabase project with service role key
- GitHub repository with Actions enabled
- Provider API keys (Finnhub, Yahoo, Tradier)

## Step 1: Database Migration

Deploy the database schema:

```bash
cd backend/supabase
supabase db push
```

Or manually apply:

```bash
psql $DATABASE_URL < migrations/20260106000000_unified_orchestrator.sql
```

**Verify:**

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('job_definitions', 'job_runs', 'coverage_status');

-- Check seed data
SELECT symbol, timeframe, job_type, enabled, priority 
FROM job_definitions 
ORDER BY priority DESC;
```

## Step 2: Deploy Edge Functions

Deploy all orchestrator functions:

```bash
cd backend/supabase

# Deploy orchestrator
supabase functions deploy orchestrator

# Deploy fetch-bars worker
supabase functions deploy fetch-bars

# Deploy ensure-coverage
supabase functions deploy ensure-coverage

# Deploy ops endpoint
supabase functions deploy ops-jobs
```

**Set environment variables:**

```bash
# Required
supabase secrets set FINNHUB_API_KEY=your_key
supabase secrets set MASSIVE_API_KEY=your_key
supabase secrets set TRADIER_API_KEY=your_key

# Already set (verify)
supabase secrets list
```

**Verify deployment:**

```bash
# Test orchestrator
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/orchestrator?action=status"

# Test ensure-coverage
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","timeframe":"1h","window_days":7}' \
  "$SUPABASE_URL/functions/v1/ensure-coverage"

# Test ops endpoint
curl -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/ops-jobs?symbol=AAPL&timeframe=1h"
```

## Step 3: Enable Realtime

Enable Realtime for the `job_runs` table:

1. Go to Supabase Dashboard → Database → Replication
2. Enable replication for `job_runs` table
3. Or via SQL:

```sql
-- Already done in migration, but verify:
SELECT schemaname, tablename 
FROM pg_publication_tables 
WHERE pubname = 'supabase_realtime' 
AND tablename = 'job_runs';
```

## Step 4: Configure GitHub Actions

Add secrets to your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY`: Service role key

**Verify workflow:**

```bash
# Manually trigger the workflow
gh workflow run orchestrator-cron.yml

# Check workflow runs
gh run list --workflow=orchestrator-cron.yml

# View logs
gh run view --log
```

**Note:** GitHub Actions cron has a minimum interval of 5 minutes. For true 1-minute intervals, consider:
- Supabase Cron (pg_cron extension)
- External cron service (cron-job.org)
- Cloud Functions with Cloud Scheduler

## Step 5: Seed Initial Jobs

Add job definitions for your watchlist:

```sql
-- Add intraday jobs (high priority)
INSERT INTO job_definitions (job_type, symbol, timeframe, window_days, priority, enabled)
VALUES
  ('fetch_intraday', 'AAPL', '15m', 5, 200, true),
  ('fetch_intraday', 'AAPL', '1h', 5, 190, true),
  ('fetch_intraday', 'NVDA', '15m', 5, 200, true),
  ('fetch_intraday', 'NVDA', '1h', 5, 190, true),
  ('fetch_intraday', 'TSLA', '15m', 5, 200, true),
  ('fetch_intraday', 'TSLA', '1h', 5, 190, true)
ON CONFLICT (symbol, timeframe, job_type) DO UPDATE
SET enabled = true, priority = EXCLUDED.priority;

-- Add historical jobs (medium priority)
INSERT INTO job_definitions (job_type, symbol, timeframe, window_days, priority, enabled)
VALUES
  ('fetch_historical', 'AAPL', 'd1', 365, 100, true),
  ('fetch_historical', 'NVDA', 'd1', 365, 100, true),
  ('fetch_historical', 'TSLA', 'd1', 365, 100, true)
ON CONFLICT (symbol, timeframe, job_type) DO UPDATE
SET enabled = true;
```

## Step 6: Monitor First Run

Trigger the orchestrator manually and watch the logs:

```bash
# Trigger orchestrator
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/orchestrator?action=tick"

# Check job runs
SELECT id, symbol, timeframe, job_type, status, progress_percent, rows_written
FROM job_runs
ORDER BY created_at DESC
LIMIT 10;

# Check coverage
SELECT symbol, timeframe, from_ts, to_ts, last_success_at, last_rows_written
FROM coverage_status
ORDER BY updated_at DESC;

# Check for errors
SELECT symbol, timeframe, error_code, error_message, attempt
FROM job_runs
WHERE status = 'failed'
ORDER BY finished_at DESC
LIMIT 5;
```

## Step 7: Client Integration (Swift)

Update your SwiftUI client to use the new system:

### 7.1 Add Realtime Subscription

```swift
// In ChartViewModel.swift or similar
import Supabase

class ChartViewModel: ObservableObject {
    @Published var jobProgress: Double = 0
    @Published var isHydrating: Bool = false
    
    private var jobRunsSubscription: RealtimeChannel?
    
    func subscribeToJobProgress(symbol: String, timeframe: String) {
        jobRunsSubscription = supabase.channel("job_runs:\(symbol):\(timeframe)")
            .on(
                .postgresChanges(
                    event: .all,
                    schema: "public",
                    table: "job_runs",
                    filter: "symbol=eq.\(symbol),timeframe=eq.\(timeframe)"
                )
            ) { [weak self] payload in
                guard let self = self else { return }
                
                if let record = payload.record as? [String: Any],
                   let status = record["status"] as? String,
                   let progress = record["progress_percent"] as? Double {
                    
                    DispatchQueue.main.async {
                        self.isHydrating = (status == "running" || status == "queued")
                        self.jobProgress = progress / 100.0
                    }
                }
            }
            .subscribe()
    }
    
    func unsubscribeFromJobProgress() {
        jobRunsSubscription?.unsubscribe()
        jobRunsSubscription = nil
    }
}
```

### 7.2 Call ensure-coverage on Symbol Select

```swift
func ensureCoverage(symbol: String, timeframe: String) async {
    do {
        let response = try await supabase.functions.invoke(
            "ensure-coverage",
            options: FunctionInvokeOptions(
                body: [
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "window_days": 7
                ]
            )
        )
        
        if let data = response.data,
           let json = try? JSONDecoder().decode(EnsureCoverageResponse.self, from: data) {
            print("Coverage status: \(json.status)")
            
            // Subscribe to progress
            subscribeToJobProgress(symbol: symbol, timeframe: timeframe)
        }
    } catch {
        print("Error ensuring coverage: \(error)")
    }
}

struct EnsureCoverageResponse: Codable {
    let job_def_id: String
    let symbol: String
    let timeframe: String
    let status: String
    let coverage_status: CoverageStatus
    
    struct CoverageStatus: Codable {
        let from_ts: String?
        let to_ts: String?
        let last_success_at: String?
        let gaps_found: Int
    }
}
```

### 7.3 Show Progress Ribbon

```swift
// In your chart view
if viewModel.isHydrating {
    HStack {
        ProgressView(value: viewModel.jobProgress)
            .progressViewStyle(.linear)
        Text("\(Int(viewModel.jobProgress * 100))%")
            .font(.caption)
            .foregroundColor(.secondary)
    }
    .padding(.horizontal)
    .padding(.vertical, 8)
    .background(Color.blue.opacity(0.1))
}
```

## Step 8: Operational Monitoring

### Check System Health

```bash
# Get overall stats
curl -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/ops-jobs?hours=24"

# Check specific symbol
curl -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/ops-jobs?symbol=AAPL&timeframe=1h&hours=6"
```

### Retry Failed Jobs

```bash
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  "$SUPABASE_URL/functions/v1/orchestrator?action=retry_failed"
```

### SQL Queries for Monitoring

```sql
-- Success rate by provider (last 24h)
SELECT 
  provider,
  COUNT(*) as total_runs,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_runs,
  ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
  SUM(rows_written) as total_rows
FROM job_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND provider IS NOT NULL
GROUP BY provider
ORDER BY success_rate DESC;

-- Average job duration by type
SELECT 
  job_type,
  COUNT(*) as runs,
  ROUND(AVG(EXTRACT(EPOCH FROM (finished_at - started_at))), 2) as avg_duration_sec,
  ROUND(AVG(rows_written), 0) as avg_rows
FROM job_runs
WHERE status = 'success'
  AND started_at IS NOT NULL
  AND finished_at IS NOT NULL
GROUP BY job_type;

-- Coverage completeness
SELECT 
  symbol,
  timeframe,
  from_ts,
  to_ts,
  EXTRACT(EPOCH FROM (to_ts - from_ts)) / 3600 as coverage_hours,
  last_success_at,
  last_rows_written
FROM coverage_status
ORDER BY last_success_at DESC;

-- Recent errors
SELECT 
  symbol,
  timeframe,
  job_type,
  error_code,
  error_message,
  attempt,
  finished_at
FROM job_runs
WHERE status = 'failed'
ORDER BY finished_at DESC
LIMIT 10;
```

## Troubleshooting

### Issue: No jobs being created

**Check:**
1. Job definitions exist and are enabled
2. Coverage gaps exist
3. Orchestrator is being called

```sql
-- Check job definitions
SELECT * FROM job_definitions WHERE enabled = true;

-- Check for gaps
SELECT * FROM get_coverage_gaps('AAPL', '1h', 7);

-- Manually trigger orchestrator
-- (see Step 6)
```

### Issue: Jobs stuck in "queued"

**Check:**
1. Orchestrator is running
2. No advisory lock conflicts
3. Check logs for errors

```sql
-- Check queued jobs
SELECT id, symbol, timeframe, created_at, attempt
FROM job_runs
WHERE status = 'queued'
ORDER BY created_at ASC;

-- Force retry
UPDATE job_runs
SET status = 'queued', attempt = attempt + 1
WHERE status = 'running' AND started_at < NOW() - INTERVAL '10 minutes';
```

### Issue: High failure rate

**Check:**
1. Provider API keys are valid
2. Rate limits not exceeded
3. Provider health status

```sql
-- Check failure patterns
SELECT 
  error_code,
  COUNT(*) as occurrences,
  MAX(error_message) as example_message
FROM job_runs
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY error_code
ORDER BY occurrences DESC;
```

### Issue: Realtime not working

**Check:**
1. Realtime enabled for job_runs table
2. Client subscription is active
3. RLS policies allow reads

```sql
-- Check Realtime publication
SELECT * FROM pg_publication_tables 
WHERE pubname = 'supabase_realtime';

-- Grant read access (if needed)
GRANT SELECT ON job_runs TO anon, authenticated;
```

## Performance Tuning

### Adjust Slice Sizes

Edit `orchestrator/index.ts`:

```typescript
const SLICE_CONFIGS = {
  fetch_intraday: {
    sliceHours: 2, // Increase for fewer, larger slices
    maxSlicesPerTick: 5, // Increase for more parallelism
  },
  // ...
};
```

### Adjust Concurrency

```typescript
const MAX_CONCURRENT_JOBS = 5; // Increase for more parallelism
```

### Adjust Priorities

```sql
-- Higher priority = processed first
UPDATE job_definitions
SET priority = 250
WHERE symbol IN ('AAPL', 'NVDA', 'TSLA') AND timeframe = '15m';
```

## Migration from Old System

If migrating from existing GitHub Actions workflows:

1. **Disable old workflows:**
   ```bash
   # Rename or delete old workflow files
   mv .github/workflows/daily-historical-sync.yml .github/workflows/daily-historical-sync.yml.disabled
   ```

2. **Backfill existing data:**
   ```sql
   -- Populate coverage_status from existing ohlc_bars_v2
   INSERT INTO coverage_status (symbol, timeframe, from_ts, to_ts, last_success_at, last_rows_written)
   SELECT 
     symbol,
     timeframe,
     MIN(ts) as from_ts,
     MAX(ts) as to_ts,
     MAX(ts) as last_success_at,
     COUNT(*) as last_rows_written
   FROM ohlc_bars_v2
   GROUP BY symbol, timeframe
   ON CONFLICT (symbol, timeframe) DO UPDATE
   SET from_ts = EXCLUDED.from_ts,
       to_ts = EXCLUDED.to_ts,
       last_success_at = EXCLUDED.last_success_at,
       last_rows_written = EXCLUDED.last_rows_written;
   ```

3. **Verify no data loss:**
   ```sql
   -- Compare bar counts before/after
   SELECT symbol, timeframe, COUNT(*) as bar_count
   FROM ohlc_bars_v2
   GROUP BY symbol, timeframe
   ORDER BY symbol, timeframe;
   ```

## Success Metrics

After deployment, monitor these KPIs:

- **Reliability:** <2% run failure rate per day
- **Freshness:** Intraday coverage lag < 2 minutes
- **Performance:** p95 fetch-bars slice < 3s
- **User Experience:** No blank charts on intraday failure

## Next Steps

1. **Phase 2:** Implement forecast-worker
2. **Optimization:** Add dead-letter queue for failed jobs
3. **Observability:** Create ops dashboard UI
4. **Scaling:** Add more provider fallbacks

## Support

For issues or questions:
- Check logs: `supabase functions logs orchestrator`
- Query ops endpoint: `/ops-jobs`
- Review job_runs table for detailed execution history
