# Options Ranker Setup & Troubleshooting

## Overview

The Options Ranker system has three components:
1. **Python ML Job**: Ranks options contracts and saves to database
2. **Edge Function API**: Serves ranked data to the client
3. **Swift UI**: Displays ranked options with filters

## Problem: "No rankings available for SYMBOL"

When you switch to a new symbol and see spinning/loading followed by the "No rankings available" message, it means:

1. The symbol has no rankings in the `options_ranks` database table
2. The ranking job needs historical OHLC data to calculate the ML score
3. OHLC data is fetched on-demand for charting but not automatically persisted

## Solution: Generate Rankings Manually

### Quick Fix: Rank a Single Symbol

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
source venv/bin/activate
python src/options_ranking_job.py --symbol CRWD
```

**Note**: This will fail if the symbol doesn't have OHLC data in the database. Only AAPL currently has data.

### Rank All Watchlist Symbols

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
./scripts/rank_all_watchlist_symbols.sh
```

This will attempt to rank 12 common symbols. Symbols without OHLC data will be skipped.

## Root Cause: Missing OHLC Data

The ranking job requires:
- At least 20 days of OHLC data for the underlying symbol (to calculate historical volatility and trend)
- Current options chain data (fetched via `/options-chain` Edge Function)

### Check Which Symbols Have Data

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
source venv/bin/activate
python -c "
from src.data.supabase_db import db
symbols = ['AAPL', 'CRWD', 'NVDA', 'MSFT', 'TSLA']
for s in symbols:
    df = db.fetch_ohlc_bars(s, 'd1', limit=5)
    print(f'{s}: {len(df)} bars')
"
```

## Architecture Limitation

**Current State**:
- The `/chart` Edge Function fetches OHLC data on-demand from Polygon.io but **does not persist it**
- The Python ranking job can only access data in the database
- This creates a gap where charts work but rankings fail

**Workarounds**:

### Option A: Backfill OHLC Data (Recommended)

Create a script to backfill OHLC data for watchlist symbols:

```bash
# TODO: Create backfill script
cd backend
deno run --allow-net --allow-env scripts/backfill-ohlc.ts --symbol CRWD --days 100
```

### Option B: Modify /chart to Persist Data

Update `backend/supabase/functions/chart/index.ts` to save fetched OHLC bars to the database.

###  C: Run Ranking Job with Fetch-on-Demand

Modify `ml/src/options_ranking_job.py` to fetch OHLC data directly from Polygon if not in DB:

```python
# In process_symbol_options():
df_ohlc = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=100)

if df_ohlc.empty:
    # Fetch from Polygon API directly
    df_ohlc = fetch_from_polygon(symbol, days=100)
    # Optionally save to DB
    save_ohlc_to_db(df_ohlc)
```

## UI Behavior

The Swift app shows these states:

1. **Loading**: `isLoading = true` while fetching rankings
2. **Empty**: `rankings.isEmpty` → Shows "No rankings available" with "Generate Rankings" button
3. **Generating**: `isGeneratingRankings = true` → Shows progress view for 30 seconds
4. **Success**: Displays ranked options with filters

### Current "Generate Rankings" Button Limitation

When you click "Generate Rankings":
1. It calls `POST /trigger-ranking-job` Edge Function
2. Edge Function responds with "Job triggered"
3. **BUT** the actual Python job doesn't run (Edge Function has no access to local Python environment)
4. After 30 seconds, it re-queries the database (still empty)
5. Shows empty state again

**Fix**: Manually run the Python job in terminal while the UI is waiting.

## Production Solution (Future)

For production, implement one of these:

### Option 1: Scheduled Job (pg_cron)
```sql
-- Run ranking job every 10 minutes for all active symbols
SELECT cron.schedule(
  'rank-options',
  '*/10 * * * *',  -- Every 10 minutes
  $$
  -- Trigger external service or Edge Function
  $$
);
```

### Option 2: Cloud Function
Deploy Python job as:
- **Google Cloud Run** (containerized Python)
- **AWS Lambda** (Python runtime)
- **Supabase Edge Functions** (via Deno subprocess - not recommended for Python)

Then `trigger-ranking-job` Edge Function would call this service.

### Option 3: Message Queue
1. `trigger-ranking-job` adds job to queue (Redis, BullMQ, Inngest)
2. Worker process picks up job and runs Python script
3. Client polls for completion or receives webhook

## Testing the Current System

### 1. Verify AAPL Rankings Work

```bash
# Check if AAPL has rankings
curl -s -H "Authorization: Bearer <YOUR_SERVICE_KEY>" \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL&limit=5" \
  | python3 -m json.tool
```

Expected: 5 ranked options with ML scores

### 2. Generate Rankings for New Symbol

```bash
# Terminal 1: Run the job
cd ml
source venv/bin/activate
python src/options_ranking_job.py --symbol AAPL

# Terminal 2: Verify in database
curl -s -H "Authorization: Bearer <YOUR_SERVICE_KEY>" \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL" \
  | python3 -m json.tool
```

### 3. Test in macOS App

1. Build and run app in Xcode
2. Select AAPL symbol
3. Navigate to Options tab → ML Ranker
4. Should see ranked options
5. Try selecting CRWD (will show empty state)
6. Click "Generate Rankings" (will spin for 30s then show empty)
7. Manually run: `python src/options_ranking_job.py --symbol CRWD` in terminal
8. Refresh in app → should show rankings

## Summary

**What Works**:
- ✅ ML ranking algorithm (multi-factor scoring)
- ✅ Python job to generate rankings
- ✅ Edge Function to serve rankings
- ✅ Swift UI to display rankings
- ✅ Filtering by expiry, side, ML score

**What Needs Manual Work**:
- ⚠️ Running the Python job (not automated yet)
- ⚠️ Backfilling OHLC data for new symbols
- ⚠️ Connecting "Generate Rankings" button to actual job execution

**Quick Start for Development**:
```bash
# 1. Rank AAPL (has data)
cd ml
source venv/bin/activate
python src/options_ranking_job.py --symbol AAPL

# 2. Open app and view AAPL rankings
# 3. For new symbols, run ranking job manually first
```
