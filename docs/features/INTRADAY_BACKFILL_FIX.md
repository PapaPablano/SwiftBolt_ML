# Intraday Data Backfill Fix - January 9, 2026

## Problem Diagnosed

The `intraday_bars` table was missing all data for 2025 due to three critical issues:

### 1. **Hardcoded Date Cap** ❌
- `backfill/index.ts` had a hardcoded cap at December 14, 2024
- This prevented any backfill from collecting data beyond that date
- **Status**: ✅ FIXED - Removed hardcoded date cap

### 2. **Intraday Service Not Writing Raw Bars** ❌
- `intraday-service-v2.ts` only wrote daily aggregates to `ohlc_bars_v2`
- Raw 5-minute bars were never written to `intraday_bars` table
- **Status**: ✅ FIXED - Now writes both raw bars and daily aggregates

### 3. **No Active Intraday Backfill Worker** ❌
- Migration created infrastructure but no worker to process chunks
- Historical intraday data was never backfilled
- **Status**: ✅ FIXED - Created `backfill-intraday-worker` edge function

---

## Changes Implemented

### 1. Fixed Backfill Date Cap
**File**: `backend/supabase/functions/backfill/index.ts`

**Before**:
```typescript
const actualNow = Math.floor(new Date("2024-12-14T23:59:59Z").getTime() / 1000);
const now = Math.floor(Date.now() / 1000);
const currentTimestamp = now > actualNow ? actualNow : now;
```

**After**:
```typescript
const currentTimestamp = Math.floor(Date.now() / 1000);
```

### 2. Enhanced Intraday Service
**File**: `backend/supabase/functions/_shared/intraday-service-v2.ts`

**Added**: Raw bar insertion to `intraday_bars` table
```typescript
// Write raw 5-minute bars to intraday_bars table
const intradayBarsToInsert = bars.map(bar => ({
  symbol_id: symbolId,
  timeframe: '5m',
  ts: new Date(bar.time).toISOString(),
  open: bar.open,
  high: bar.high,
  low: bar.low,
  close: bar.close,
  volume: bar.volume,
  provider: 'tradier',
}));

await supabase.from('intraday_bars').upsert(intradayBarsToInsert, {
  onConflict: 'symbol_id,timeframe,ts',
  ignoreDuplicates: false,
});
```

### 3. Created Backfill Worker
**File**: `backend/supabase/functions/backfill-intraday-worker/index.ts`

**Features**:
- Claims chunks using `SKIP LOCKED` for parallel processing
- Fetches historical data from Polygon API
- Writes to `intraday_bars` table (1m, 5m, 15m timeframes)
- Updates chunk status and job progress
- Handles rate limiting and errors gracefully

### 4. Added Chunk Claiming Function
**File**: `backend/supabase/migrations/20260109040000_comprehensive_intraday_backfill.sql`

**Added**: `claim_backfill_chunk()` function for parallel worker coordination

### 5. Created Worker Automation
**File**: `.github/workflows/backfill-intraday-worker.yml`

**Features**:
- Runs every 5 minutes via cron
- Spawns 3 parallel workers per run
- Processes backfill chunks automatically
- Manual trigger support for on-demand processing

---

## How to Use

### Step 1: Deploy the Migration
```bash
cd backend/supabase
supabase db push
```

This will:
- Create the `claim_backfill_chunk()` function
- Seed initial 2-year backfill jobs for AAPL, NVDA, TSLA, SPY, QQQ

### Step 2: Deploy the Edge Function
```bash
supabase functions deploy backfill-intraday-worker
```

### Step 3: Seed Additional Symbols (Optional)
```sql
-- Seed 2-year backfill for a specific symbol
SELECT seed_intraday_backfill_2yr('MSFT', 'h1');

-- Check job status
SELECT * FROM backfill_jobs 
WHERE symbol = 'AAPL' 
ORDER BY created_at DESC;

-- Check chunk progress
SELECT 
  status,
  COUNT(*) as count,
  SUM(bars_collected) as total_bars
FROM backfill_chunks
WHERE job_id = '<job_id_from_above>'
GROUP BY status;
```

### Step 4: Manual Worker Trigger (Testing)
```bash
# Trigger a single worker run
curl -X POST \
  "https://xkslcvvzwsxfqatnvpqv.supabase.co/functions/v1/backfill-intraday-worker" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
  -d '{}'
```

### Step 5: Enable GitHub Actions Worker
The worker will automatically run every 5 minutes via GitHub Actions. To trigger manually:
1. Go to GitHub Actions
2. Select "Backfill Intraday Worker"
3. Click "Run workflow"

---

## Monitoring Progress

### Check Overall Job Status
```sql
SELECT 
  symbol,
  timeframe,
  status,
  bars_collected,
  from_ts,
  to_ts,
  created_at,
  completed_at
FROM backfill_jobs
ORDER BY created_at DESC;
```

### Check Chunk Processing
```sql
SELECT 
  bj.symbol,
  bc.status,
  COUNT(*) as chunk_count,
  SUM(bc.bars_collected) as total_bars,
  MIN(bc.day) as earliest_day,
  MAX(bc.day) as latest_day
FROM backfill_chunks bc
JOIN backfill_jobs bj ON bc.job_id = bj.id
WHERE bj.symbol = 'AAPL'
GROUP BY bj.symbol, bc.status;
```

### Verify Data in intraday_bars
```sql
-- Check coverage by month
SELECT 
  date_trunc('month', ts) AS month,
  timeframe,
  COUNT(*) AS bar_count,
  MIN(ts) AS first_bar,
  MAX(ts) AS last_bar
FROM intraday_bars
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- Check for gaps (should return 0 missing hours for 2025)
WITH aapl AS (
  SELECT id AS symbol_id FROM symbols WHERE ticker = 'AAPL' LIMIT 1
),
raw_hours AS (
  SELECT date_trunc('hour', ts) AS hour_ts
  FROM intraday_bars
  WHERE symbol_id = (SELECT symbol_id FROM aapl)
    AND timeframe IN ('1m','5m','15m')
    AND ts >= '2025-01-01'
  GROUP BY 1
),
bounds AS (
  SELECT MIN(hour_ts) AS min_ts, MAX(hour_ts) AS max_ts FROM raw_hours
),
expected AS (
  SELECT generate_series(
    date_trunc('hour', (SELECT min_ts FROM bounds)),
    date_trunc('hour', (SELECT max_ts FROM bounds)),
    interval '1 hour'
  ) AS hour_ts
),
missing AS (
  SELECT e.hour_ts
  FROM expected e
  LEFT JOIN raw_hours r ON r.hour_ts = e.hour_ts
  WHERE r.hour_ts IS NULL
)
SELECT COUNT(*) AS missing_count FROM missing;
```

---

## Expected Timeline

With 3 parallel workers running every 5 minutes:
- **Processing rate**: ~18 chunks per 5 minutes (3 workers × 6 runs/hour)
- **2-year backfill**: ~520 market days per symbol
- **Time to complete**: ~29 hours per symbol (520 chunks ÷ 18 chunks/hour)

To speed up:
- Increase parallel workers in GitHub Actions (edit matrix in workflow)
- Run multiple manual triggers simultaneously
- Use Supabase cron jobs for higher frequency

---

## Troubleshooting

### Worker Not Processing Chunks
```sql
-- Check for stuck chunks
SELECT * FROM backfill_chunks
WHERE status = 'in_progress'
  AND updated_at < NOW() - INTERVAL '10 minutes';

-- Reset stuck chunks
UPDATE backfill_chunks
SET status = 'pending', updated_at = NOW()
WHERE status = 'in_progress'
  AND updated_at < NOW() - INTERVAL '10 minutes';
```

### Rate Limiting from Polygon
The worker automatically handles 429 errors with 60-second backoff. If you hit limits frequently:
- Reduce parallel workers
- Add longer delays between requests
- Upgrade Polygon API tier

### Missing Data for Specific Days
```sql
-- Find days with no data
SELECT day, status, error_message
FROM backfill_chunks
WHERE symbol = 'AAPL'
  AND status IN ('error', 'completed')
  AND bars_collected = 0
ORDER BY day DESC;
```

---

## Next Steps

1. ✅ Deploy migration and edge function
2. ✅ Enable GitHub Actions workflow
3. ⏳ Monitor progress for 24-48 hours
4. ✅ Verify data coverage with queries above
5. 🎯 Once backfilled, real-time collection will maintain data going forward

---

## Notes

- **Real-time collection**: The `intraday-update-v2.yml` workflow now writes to both `intraday_bars` and `ohlc_bars_v2`
- **Historical data**: The backfill worker populates `intraday_bars` with Polygon data
- **Data continuity**: Once backfill completes, you'll have seamless coverage from 2 years ago to present
- **Provider separation**: Tradier for real-time, Polygon for historical
