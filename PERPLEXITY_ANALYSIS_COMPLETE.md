# Perplexity Expert Analysis - Complete Report

## Executive Summary

After consulting Perplexity as a senior software engineer, the core issues with your system are:

1. **❌ CRITICAL: Multiple competing ingestion mechanisms** - You have Python scripts, GitHub Actions, Edge Functions all trying to ingest data with no clear owner
2. **❌ No single source of truth** for "what's the last bar we ingested"
3. **❌ File-based caching instead of proper database** on client
4. **❌ No monitoring/alerting** for stale data
5. **✅ Database query is correct** (we fixed this)
6. **✅ Chart rendering is correct**
7. **✅ API layer is correct**

---

## What Perplexity Recommends (Production Best Practices)

### 1. Data Ingestion Architecture

**Single Ingestion Service Pattern:**
```
┌─────────────────────────────────────────────────┐
│  Single Containerized Service (Python/Node)     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ 15m Job  │ │  1h Job  │ │  d1 Job  │ ...    │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                  │
│  Shared:                                        │
│  - Alpaca client with rate limiting             │
│  - State store (last_ts per symbol/timeframe)  │
│  - Retry/error handling                         │
│  - Monitoring/metrics                           │
└─────────────────────────────────────────────────┘
         ↓
    PostgreSQL
    ┌──────────────────┐
    │ ohlc_bars        │
    │ ingestion_state  │
    └──────────────────┘
```

**Key Principles:**
- **ONE service owns ALL ingestion** (all symbols, all timeframes)
- **Incremental fetches only** (not full refreshes)
- **Idempotent upserts** (safe to re-run)
- **State tracking** (last ingested timestamp per symbol/timeframe)

### 2. Scheduling Strategy

**Recommended Cron Schedule:**
- **15m bars:** Every 5 minutes
- **1h bars:** Every 15 minutes  
- **4h bars:** Every 30-60 minutes
- **Daily bars:** Once per day at 22:15 UTC (after market close)
- **Weekly bars:** Once per week Friday 23:00 UTC

**Implementation:**
- AWS: EventBridge Scheduler → Lambda (container)
- GCP: Cloud Scheduler → Cloud Run
- Self-hosted: Single cron job that runs different timeframe jobs

### 3. Client-Side Caching (iOS/macOS)

**WRONG (Your Current Approach):**
```swift
// ❌ File-based JSON cache
// ❌ Age-based invalidation (hours old)
// ❌ No way to know if server has newer data
ChartCache.save("AAPL_d1.json")
```

**RIGHT (Industry Standard):**
```swift
// ✅ SQLite database
// ✅ Incremental fetch by timestamp
// ✅ Server-driven freshness

// Local DB Schema
CREATE TABLE local_candles (
    symbol TEXT,
    timeframe TEXT,
    start_time INTEGER,  -- Unix timestamp
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY(symbol, timeframe, start_time)
);

// Fetch pattern
func loadChart(symbol: String, tf: String) {
    // 1. Load from local DB immediately
    let localBars = db.lastNBars(symbol, tf, limit: 1000)
    renderChart(localBars)  // Instant UI
    
    // 2. Fetch incremental updates in background
    let lastTime = localBars.last?.timestamp
    api.fetchIncremental(symbol, tf, since: lastTime) { newBars in
        db.mergeBars(newBars)  // Upsert
        let updated = db.lastNBars(symbol, tf, limit: 1000)
        renderChart(updated)
    }
}
```

### 4. API Design

**Incremental Endpoint (Critical):**
```http
GET /ohlc/incremental?symbol=AAPL&tf=d1&since=2024-07-17T04:00:00Z
```

Returns only bars **newer than `since`**:
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "bars": [
    {"t": "2024-07-18T04:00:00Z", "o": 230, "h": 232, ...},
    {"t": "2024-07-19T04:00:00Z", "o": 231, "h": 233, ...}
  ]
}
```

**Key Points:**
- Client tracks "last known timestamp"
- Server returns only new/updated bars
- No need for ETags/cache headers for incremental
- Use HTTP caching (ETag/Last-Modified) for historical bulk fetches

### 5. Monitoring & Alerting

**Required Metrics:**
```python
# Job-level
ingestion_job_success{timeframe="d1"} = 1
ingestion_job_duration_seconds{timeframe="d1"} = 12.5

# Data freshness
ohlc_last_bar_ts{symbol="AAPL", timeframe="d1"} = 1736467200
ohlc_bar_lag_seconds{symbol="AAPL", timeframe="d1"} = 86400
```

**Alerts:**
- Job failure: If `ingestion_job_success = 0` for N consecutive runs
- Stale data: If `ohlc_bar_lag_seconds > threshold` (e.g., 30 min for 15m bars, 2 days for daily)
- API issues: High rate of 429/5xx from Alpaca

---

## Where You Went Wrong

### Issue 1: Multiple Ingestion Mechanisms ❌

**What you have:**
```
ml/src/scripts/alpaca_backfill_ohlc_v2.py
.github/workflows/alpaca-intraday-cron.yml
.github/workflows/backfill-ohlc.yml
.github/workflows/daily-data-refresh.yml
supabase/functions/_shared/backfill-adapter.ts
backend/scripts/trigger-alpaca-backfill.sql
```

**Problem:** No one knows which is responsible. They probably conflict or none run correctly.

**Fix:** Pick ONE mechanism. Delete the others.

### Issue 2: No State Tracking ❌

**What you're missing:**
```sql
-- You don't have this!
CREATE TABLE ingestion_state (
    symbol TEXT,
    timeframe TEXT,
    last_ingested_ts TIMESTAMPTZ,
    PRIMARY KEY(symbol, timeframe)
);
```

**Problem:** Each run doesn't know where it left off, so it either:
- Fetches everything (wasteful, hits rate limits)
- Fetches nothing (data goes stale)

**Fix:** Add state table, update it after each successful ingestion.

### Issue 3: File-Based Client Cache ❌

**What you have:**
```swift
// ChartCache.swift
func save(_ data: ChartData, to: "AAPL_d1.json")
```

**Problem:**
- Can't query "give me bars since timestamp X"
- Age-based invalidation is unreliable
- No way to merge incremental updates

**Fix:** Use SQLite/Core Data with proper schema.

### Issue 4: No Incremental API ❌

**What you have:**
```typescript
// chart-data-v2 returns ALL 1000 bars every time
GET /chart-data-v2?symbol=AAPL&timeframe=d1
→ Returns 1000 bars (even if only 1 is new)
```

**Problem:** Wasteful, slow, can't tell if data is fresh.

**Fix:** Add incremental endpoint that takes `since` parameter.

### Issue 5: No Monitoring ❌

**What you're missing:**
- No alerts when data goes stale
- No metrics on ingestion job success/failure
- No visibility into Alpaca API errors

**Fix:** Add CloudWatch/Datadog metrics + alerts.

---

## Course Correction Plan

### Phase 1: Stop the Bleeding (Immediate)

1. **Identify which ingestion mechanism is supposed to be running**
   - Check GitHub Actions logs
   - Check Supabase Edge Function logs
   - Check if Python scripts are scheduled anywhere

2. **Manually backfill AAPL to current**
   ```bash
   cd ml/src/scripts
   python alpaca_backfill_ohlc_v2.py --symbol AAPL --timeframes m15,h1,h4,d1,w1
   ```

3. **Verify data is current**
   ```sql
   SELECT timeframe, MAX(ts) as newest_bar
   FROM ohlc_bars_v2
   WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
   GROUP BY timeframe;
   ```

### Phase 2: Consolidate Ingestion (1-2 days)

1. **Choose ONE ingestion mechanism:**
   - **Option A:** GitHub Actions (simplest, free)
   - **Option B:** Supabase Edge Function with pg_cron
   - **Option C:** AWS Lambda with EventBridge

2. **Implement state tracking:**
   ```sql
   CREATE TABLE ingestion_state (
       symbol_id UUID REFERENCES symbols(id),
       timeframe VARCHAR(10),
       last_ingested_ts TIMESTAMPTZ NOT NULL,
       last_run_at TIMESTAMPTZ DEFAULT NOW(),
       last_run_status VARCHAR(20), -- 'success', 'failed'
       PRIMARY KEY(symbol_id, timeframe)
   );
   ```

3. **Rewrite ingestion to be incremental:**
   ```python
   def ingest_incremental(symbol, timeframe):
       # 1. Get last ingested timestamp
       last_ts = db.get_last_ts(symbol, timeframe)
       
       # 2. Fetch only new bars from Alpaca
       bars = alpaca.get_bars(
           symbol, 
           timeframe,
           start=last_ts + timedelta(timeframe),
           end=now() - timedelta(minutes=2)
       )
       
       # 3. Upsert bars
       for bar in bars:
           db.upsert_bar(bar)
       
       # 4. Update state
       if bars:
           db.update_state(symbol, timeframe, max(bar.ts for bar in bars))
   ```

4. **Delete all other ingestion code**

### Phase 3: Fix Client Caching (2-3 days)

1. **Replace file cache with SQLite:**
   ```swift
   // Use GRDB.swift or Core Data
   class BarStore {
       func lastNBars(symbol: String, timeframe: String, limit: Int) -> [Bar]
       func mergeBars(symbol: String, timeframe: String, bars: [Bar])
   }
   ```

2. **Implement incremental fetch in ChartViewModel:**
   ```swift
   func loadChart() {
       // Load from local DB
       let local = barStore.lastNBars(symbol, timeframe, 1000)
       self.chartData = local
       
       // Fetch incremental
       let lastTime = local.last?.timestamp
       api.fetchIncremental(symbol, timeframe, since: lastTime) { new in
           barStore.mergeBars(symbol, timeframe, new)
           self.chartData = barStore.lastNBars(symbol, timeframe, 1000)
       }
   }
   ```

3. **Add incremental endpoint to Edge Function:**
   ```typescript
   // chart-data-v2/index.ts
   const since = req.query.since;
   const query = since 
       ? `SELECT * FROM get_chart_data_v2_since($1, $2, $3)`
       : `SELECT * FROM get_chart_data_v2($1, $2, $3)`;
   ```

### Phase 4: Add Monitoring (1 day)

1. **Add metrics to ingestion:**
   ```python
   cloudwatch.put_metric_data(
       Namespace='SwiftBoltML',
       MetricData=[
           {
               'MetricName': 'IngestionSuccess',
               'Dimensions': [
                   {'Name': 'Timeframe', 'Value': timeframe}
               ],
               'Value': 1.0 if success else 0.0
           }
       ]
   )
   ```

2. **Add CloudWatch alarms:**
   - Alert if ingestion fails 3 times in a row
   - Alert if data is >2 hours stale for intraday
   - Alert if data is >1 day stale for daily

3. **Add dashboard:**
   - Last bar timestamp per symbol/timeframe
   - Ingestion job success rate
   - Alpaca API error rate

---

## Recommended Tech Stack (Based on What You Have)

**Keep:**
- ✅ PostgreSQL (Supabase)
- ✅ Swift + SwiftUI (client)
- ✅ Lightweight Charts (chart.js)
- ✅ Alpaca Markets API

**Change:**
- ❌ File-based cache → ✅ SQLite (GRDB.swift)
- ❌ Multiple ingestion → ✅ Single GitHub Action or Edge Function
- ❌ No state tracking → ✅ `ingestion_state` table
- ❌ No monitoring → ✅ CloudWatch or Supabase logs + alerts

**Add:**
- ✅ Incremental API endpoint (`/chart-data-v2/incremental`)
- ✅ Monitoring dashboard
- ✅ Alerting for stale data

---

## Next Steps (Priority Order)

1. **[URGENT]** Manually backfill AAPL to verify ingestion works
2. **[URGENT]** Identify which ingestion mechanism should be running
3. **[HIGH]** Add `ingestion_state` table
4. **[HIGH]** Consolidate to single ingestion service
5. **[MEDIUM]** Replace file cache with SQLite
6. **[MEDIUM]** Add incremental API endpoint
7. **[LOW]** Add monitoring/alerting

---

## Key Takeaways from Perplexity

1. **Simplicity wins** - One service, one scheduler, one state store
2. **Incremental is king** - Never fetch all 1000 bars if only 1 is new
3. **State is critical** - Track "last ingested timestamp" per symbol/timeframe
4. **Client should use DB** - SQLite, not JSON files
5. **Monitor everything** - You can't fix what you can't see
6. **Idempotency matters** - Safe to re-run jobs without duplicates

The good news: Your database query and chart rendering are correct. The bad news: Your data ingestion pipeline is fundamentally broken and needs to be rebuilt from scratch following the patterns above.
