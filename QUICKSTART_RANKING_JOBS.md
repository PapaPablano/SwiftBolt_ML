# Quick Start: Options Ranking Jobs

## ✅ System is Now Fully Functional!

When you click "Generate Rankings" in the app, it now **actually works** - it queues a job in the database. You just need to run the worker to process it.

## How to Use (Development)

### Step 1: Start the Worker (Keep Running)

Open a terminal and run:

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
source venv/bin/activate
python src/ranking_job_worker.py --watch
```

**Leave this terminal open!** It will continuously poll for jobs every 10 seconds.

### Step 2: Use the App

1. Open your macOS app in Xcode
2. Select any symbol (e.g., AAPL, MSFT, CRWD)
3. Go to Options tab → ML Ranker
4. Click "Generate Rankings" button
5. Watch the worker terminal - you'll see:
   ```
   📥 Got job: <uuid> for symbol AAPL
   🔄 Processing job...
   ✅ Successfully processed job for AAPL
   ```
6. App will auto-refresh and show ranked options! 🎉

## Important Notes

### First Time for a Symbol?

If you select a brand new symbol that's never been charted:

1. **View the chart first** (Chart tab) - this auto-populates OHLC data
2. **Then** click "Generate Rankings"
3. Worker will process successfully

Or use the backfill script:
```bash
python src/scripts/backfill_ohlc.py --symbol TSLA
```

### Worker Must Be Running

The "Generate Rankings" button queues a job, but **you need the worker running** to actually process it.

**Without worker**: Job sits in queue forever
**With worker**: Job processes in 18-30 seconds

## Quick Commands

### Process Queue Once (Then Exit)
```bash
cd ml
source venv/bin/activate
python src/ranking_job_worker.py
```

### Run Worker Continuously (Recommended)
```bash
cd ml
source venv/bin/activate
python src/ranking_job_worker.py --watch
```

### Backfill OHLC for Multiple Symbols
```bash
cd ml
source venv/bin/activate
python src/scripts/backfill_ohlc.py --symbols AAPL MSFT NVDA TSLA CRWD
```

### Check Job Queue Status
```bash
cd ml
source venv/bin/activate
python -c "
from src.data.supabase_db import db
result = db.client.table('ranking_jobs').select('*').eq('status', 'pending').execute()
print(f'Pending jobs: {len(result.data)}')
for job in result.data:
    print(f'  - {job[\"symbol\"]} (created: {job[\"created_at\"]})')
"
```

## What Changed

### Before
- "Generate Rankings" button → 30 second wait → nothing happened 😞
- Had to manually run: `python src/options_ranking_job.py --symbol AAPL`

### After
- "Generate Rankings" button → queues job in database ✅
- Worker (running in background) → picks up job → processes it ✅
- App refreshes automatically → shows rankings ✅

## Full End-to-End Test

```bash
# Terminal 1: Start worker
cd /Users/ericpeterson/SwiftBolt_ML/ml
source venv/bin/activate
python src/ranking_job_worker.py --watch

# Terminal 2: Trigger a job via API
curl -X POST \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUyMTEzMzYsImV4cCI6MjA4MDc4NzMzNn0.51NE7weJk0PMXZJ26UgtcMZLejjPHDNoegcfpaImVJs" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL"}' \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/trigger-ranking-job"

# Watch Terminal 1 - you'll see the job get processed!
# Then check results:
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YajeNHOQ63uBDDZhJ2YYHK7L-BKmnZAviDqrlk2TQxU" \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL&limit=3"
```

## For Production

To make this fully production-ready, you'd deploy the worker as a service:

- **Docker Container** (recommended)
- **systemd service** (Linux)
- **launchd** (macOS)
- **PM2** (Node.js process manager)
- **Cloud Run** / **Lambda** (serverless)

But for development, just keep the worker running in a terminal! 🚀

## Tested Symbols

These symbols have OHLC data and working rankings:

| Symbol | OHLC Data | Rankings | Status |
|--------|-----------|----------|--------|
| AAPL   | ✅ 100 bars | ✅ 100 contracts | Working |
| CRWD   | ✅ 70 bars  | ✅ 100 contracts | Working |
| NVDA   | ✅ 70 bars  | ✅ 100 contracts | Working |
| MSFT   | ✅ 70 bars  | ✅ 100 contracts | Working |

Any other symbol: Just view the chart once, then rank!
