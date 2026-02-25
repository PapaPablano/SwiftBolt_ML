# Multi-Timeframe & Symbol Tracking Deployment Guide

This guide walks through deploying the complete multi-timeframe backfill system with user symbol tracking integration.

## 🎯 Overview

**What This System Does:**
- ✅ Automatically backfills 3 timeframes (m15, h1, h4) for all symbols
- ✅ Tracks user interest from watchlist, searches, and chart views
- ✅ Prioritizes backfill based on user activity (watchlist > chart view > search)
- ✅ Auto-creates job definitions when users interact with symbols
- ✅ Orchestrator processes jobs automatically every 60 seconds

**Architecture:**
```
Swift App (User Actions)
    ↓
SymbolSyncService → sync-user-symbols Edge Function
    ↓
user_symbol_tracking table (RLS protected)
    ↓
Database Trigger → auto_create_jobs_for_tracked_symbols()
    ↓
job_definitions table (3 timeframes per symbol)
    ↓
Orchestrator (pg_cron every 60s) → Processes jobs by priority
    ↓
ohlc_bars_v2 table (multi-timeframe data)
```

---

## 📋 Phase 1: Database Migration (5 min)

### Step 1: Apply Migration

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase

# Apply the multi-timeframe migration
supabase db push --project-ref cygflaemtmwiwaviclks
```

**What This Creates:**
- `user_symbol_tracking` table with RLS policies
- Auto-trigger function for job creation
- Helper functions for monitoring
- Seeds 60 job definitions (20 symbols × 3 timeframes)

### Step 2: Verify Migration

```bash
# Connect to database
psql "postgresql://postgres.cygflaemtmwiwaviclks:${SUPABASE_DB_PASSWORD}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
```

```sql
-- Check job definitions created
SELECT timeframe, COUNT(*) as job_count
FROM job_definitions
WHERE timeframe IN ('m15', 'h1', 'h4')
  AND enabled = true
GROUP BY timeframe;

-- Expected output:
-- timeframe | job_count
-- ----------|-----------
-- m15       | 20
-- h1        | 20
-- h4        | 20
```

---

## 📋 Phase 2: Deploy Edge Function (5 min)

### Step 1: Deploy sync-user-symbols Function

```bash
cd /Users/ericpeterson/SwiftBolt_ML/backend/supabase

# Deploy the Edge Function
supabase functions deploy sync-user-symbols --project-ref cygflaemtmwiwaviclks
```

### Step 2: Test Edge Function

```bash
# Test with curl (replace with your anon key)
curl -X POST \
  'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/sync-user-symbols' \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL"],
    "source": "watchlist",
    "timeframes": ["m15", "h1", "h4"]
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "symbols_tracked": 1,
  "symbols_requested": 1,
  "timeframes": 3,
  "jobs_updated": 3,
  "priority": 300,
  "source": "watchlist"
}
```

---

## 📋 Phase 3: Swift App Integration (Already Complete)

The following files have been updated:

### Created:
- `client-macos/SwiftBoltML/Services/SymbolSyncService.swift`

### Modified:
- `client-macos/SwiftBoltML/ViewModels/WatchlistViewModel.swift`
  - Calls `SymbolSyncService` when adding to watchlist
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
  - Calls `SymbolSyncService` when loading chart
- `client-macos/SwiftBoltML/ViewModels/SymbolSearchViewModel.swift`
  - Added `trackSymbolSelection()` method
- `client-macos/SwiftBoltML/Views/SymbolSearchView.swift`
  - Calls tracking when symbol selected

### Environment Variables Required:

Ensure these are set in your Xcode scheme or `.env`:
```bash
SUPABASE_URL=https://cygflaemtmwiwaviclks.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
```

---

## 📋 Phase 4: Verification & Testing (10 min)

### Test 1: Watchlist Integration

1. **Open Swift App**
2. **Add TSLA to watchlist**
3. **Check database:**

```sql
-- Verify symbol tracked
SELECT * FROM user_symbol_tracking 
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'TSLA')
ORDER BY created_at DESC;

-- Verify jobs created
SELECT symbol, timeframe, priority, enabled
FROM job_definitions
WHERE symbol = 'TSLA'
  AND timeframe IN ('m15', 'h1', 'h4');

-- Expected: 3 jobs with priority 300 (watchlist)
```

### Test 2: Search Integration

1. **Search for "NVDA"**
2. **Select NVDA from results**
3. **Check database:**

```sql
SELECT * FROM user_symbol_tracking 
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'NVDA')
  AND source = 'recent_search';

-- Expected: 1 entry with priority 100
```

### Test 3: Chart View Integration

1. **Open chart for AMD**
2. **Check database:**

```sql
SELECT * FROM user_symbol_tracking 
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AMD')
  AND source = 'chart_view';

-- Expected: 1 entry with priority 200
```

### Test 4: Orchestrator Processing

Wait 2-3 minutes for orchestrator to run, then check:

```sql
-- Check job runs created
SELECT 
  symbol,
  timeframe,
  status,
  rows_written,
  created_at
FROM job_runs
WHERE symbol IN ('TSLA', 'NVDA', 'AMD')
  AND created_at > now() - interval '10 minutes'
ORDER BY created_at DESC;

-- Check bars written
SELECT 
  s.ticker,
  o.timeframe,
  COUNT(*) as bars,
  MIN(o.timestamp) as earliest,
  MAX(o.timestamp) as latest
FROM ohlc_bars_v2 o
JOIN symbols s ON o.symbol_id = s.id
WHERE s.ticker IN ('TSLA', 'NVDA', 'AMD')
  AND o.timeframe IN ('m15', 'h1', 'h4')
GROUP BY s.ticker, o.timeframe
ORDER BY s.ticker, o.timeframe;
```

---

## 📊 Monitoring Queries

Use the monitoring script for ongoing observation:

```bash
# Run monitoring queries
psql "postgresql://postgres.cygflaemtmwiwaviclks:${SUPABASE_DB_PASSWORD}@aws-0-us-east-1.pooler.supabase.com:6543/postgres" \
  -f /Users/ericpeterson/SwiftBolt_ML/backend/supabase/monitor_multi_timeframe.sql
```

### Quick Health Check

```sql
-- System health across all timeframes
SELECT * FROM get_timeframe_job_stats(1);

-- Coverage for specific symbol
SELECT * FROM get_symbol_timeframe_coverage('AAPL');

-- User tracked symbols status
SELECT * FROM get_user_tracked_symbols_status('your-user-id-here');
```

---

## 🎯 Expected Behavior

### Timeline After User Adds Symbol to Watchlist:

| Time | Event |
|------|-------|
| T+0s | User adds TSLA to watchlist |
| T+0s | Swift app calls `sync-user-symbols` Edge Function |
| T+0s | Edge Function creates `user_symbol_tracking` entry |
| T+0s | Database trigger creates 3 `job_definitions` (m15, h1, h4) |
| T+60s | Orchestrator detects new jobs (next cron tick) |
| T+60s | Orchestrator creates job slices and dispatches workers |
| T+120s | First bars start appearing in `ohlc_bars_v2` |
| T+300s | All 3 timeframes have initial coverage |
| T+600s | Complete backfill finished (30d m15, 90d h1, 365d h4) |

### Priority Processing Order:

1. **Watchlist symbols** (priority 300) - processed first
2. **Chart view symbols** (priority 200) - processed second
3. **Search symbols** (priority 100) - processed third
4. **Background symbols** (priority 100-200) - processed last

---

## 🔧 Troubleshooting

### Issue: Jobs Not Creating

**Check:**
```sql
-- Verify trigger exists
SELECT tgname FROM pg_trigger WHERE tgname = 'trigger_auto_create_jobs';

-- Manually test trigger
INSERT INTO user_symbol_tracking (user_id, symbol_id, source, priority)
VALUES (
  (SELECT id FROM auth.users LIMIT 1),
  (SELECT id FROM symbols WHERE ticker = 'TEST'),
  'watchlist',
  300
);

-- Check if jobs created
SELECT * FROM job_definitions WHERE symbol = 'TEST';
```

### Issue: Orchestrator Not Running

**Check:**
```sql
-- Verify cron job
SELECT * FROM cron.job WHERE jobname = 'orchestrator-tick';

-- Check recent orchestrator logs
SELECT * FROM job_runs 
WHERE created_at > now() - interval '5 minutes'
ORDER BY created_at DESC
LIMIT 10;
```

### Issue: Swift App Not Syncing

**Check:**
1. Environment variables set correctly
2. Console logs for `[SymbolSync]` messages
3. Network requests in Xcode debugger
4. Edge Function logs in Supabase dashboard

---

## 📈 Performance Expectations

### Backfill Speed (per symbol):

| Timeframe | Window | Expected Bars | Time to Complete |
|-----------|--------|---------------|------------------|
| m15       | 30d    | ~3,000 bars   | 2-3 minutes      |
| h1        | 90d    | ~2,000 bars   | 3-5 minutes      |
| h4        | 365d   | ~2,000 bars   | 3-5 minutes      |

### Concurrent Processing:

- Orchestrator dispatches **5 concurrent jobs** per tick
- Each tick runs every **60 seconds**
- With 60 jobs (20 symbols × 3 timeframes), expect **12 minutes** for full backfill

---

## ✅ Success Criteria

After deployment, verify:

- [ ] Migration applied successfully
- [ ] Edge Function deployed and responding
- [ ] Swift app compiles without errors
- [ ] Adding to watchlist creates jobs with priority 300
- [ ] Searching symbol creates jobs with priority 100
- [ ] Viewing chart creates jobs with priority 200
- [ ] Orchestrator processes jobs every 60 seconds
- [ ] Bars appear in all 3 timeframes within 10 minutes
- [ ] Monitoring queries return expected data
- [ ] No errors in Supabase logs

---

## 🚀 Next Steps

1. **Monitor for 24 hours** - Ensure system stability
2. **Expand symbol list** - Add more symbols to job_definitions
3. **Tune priorities** - Adjust based on user patterns
4. **Add alerting** - Set up notifications for job failures
5. **Optimize window_days** - Adjust based on storage/performance needs

---

## 📞 Support

If issues arise:

1. Check Supabase logs: Dashboard → Logs → Edge Functions
2. Check database logs: Dashboard → Logs → Postgres
3. Check Swift console for `[SymbolSync]` messages
4. Run monitoring queries to identify bottlenecks
5. Review job_runs table for error messages

---

## 🎉 Summary

You now have a fully automated multi-timeframe backfill system that:
- Responds to user actions in real-time
- Prioritizes based on user interest
- Processes jobs automatically in the background
- Provides comprehensive monitoring and observability
- Scales to handle hundreds of symbols across multiple timeframes

The system is production-ready and will ensure your users always have fresh data across all timeframes! 🚀
