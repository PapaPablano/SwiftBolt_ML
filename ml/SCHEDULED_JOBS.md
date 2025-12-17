# Scheduled Jobs - Options Ranking

This document explains how to set up automated options ranking for priority symbols.

## Overview

The options ranking job automatically scores and ranks options contracts for priority symbols (watchlist + popular stocks). This keeps the ML ranker data fresh without manual intervention.

## Files

- `scripts/rank_priority_symbols.sh` - Main scheduled job script
- `src/scripts/get_watchlist_symbols.py` - Fetches symbols from database
- `src/options_ranking_job.py` - Core ranking logic

## Manual Execution

Test the job manually:

```bash
cd ml
./scripts/rank_priority_symbols.sh
```

This will:
1. Fetch symbols from your watchlist
2. Add popular stocks (AAPL, MSFT, TSLA, SPY, etc.)
3. Rank options for each symbol
4. Save rankings to the database

## Automated Scheduling with Cron

### Setup Cron Job (Hourly during market hours)

```bash
# Edit crontab
crontab -e

# Add this line (runs every hour from 9 AM to 4 PM ET on weekdays)
0 9-16 * * 1-5 cd /Users/ericpeterson/SwiftBolt_ML/ml && ./scripts/rank_priority_symbols.sh >> logs/ranking_job.log 2>&1
```

### Create logs directory

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
mkdir -p logs
```

### View job logs

```bash
tail -f logs/ranking_job.log
```

## Priority Symbols

The job processes two types of symbols:

### 1. Watchlist Symbols (Dynamic)
- Fetched from the `symbols` table in Supabase
- Automatically includes all symbols users are tracking

### 2. Popular Stocks (Static)
Always ranked regardless of watchlist:
- AAPL (Apple)
- MSFT (Microsoft)
- TSLA (Tesla)
- SPY (S&P 500 ETF)
- QQQ (Nasdaq ETF)
- NVDA (Nvidia)
- AMZN (Amazon)
- GOOGL (Google)
- META (Meta)
- AMD (AMD)

## Customization

### Change priority stocks

Edit `scripts/rank_priority_symbols.sh`:

```bash
PRIORITY_SYMBOLS=(
    "AAPL"
    "MSFT"
    # Add your symbols here
)
```

### Adjust schedule

Edit the cron expression:

```
# Every 2 hours (9 AM, 11 AM, 1 PM, 3 PM)
0 9,11,13,15 * * 1-5 ...

# Every 30 minutes during market hours
*/30 9-16 * * 1-5 ...
```

## Monitoring

### Check if rankings are fresh

```bash
cd ml
python -c "
from src.data.supabase_db import db
response = db.client.table('options_ranks').select('run_at').order('run_at', desc=True).limit(1).execute()
if response.data:
    print(f'Last ranking: {response.data[0][\"run_at\"]}')
"
```

### Count ranked options per symbol

```bash
cd ml
python -c "
from src.data.supabase_db import db
response = db.client.table('options_ranks').select('underlying_symbol_id').execute()
from collections import Counter
counts = Counter(r['underlying_symbol_id'] for r in response.data)
print(f'Total symbols with rankings: {len(counts)}')
for symbol_id, count in counts.most_common(10):
    print(f'  {symbol_id}: {count} contracts')
"
```

## Troubleshooting

### Job doesn't run

1. Check cron is enabled: `crontab -l`
2. Check logs: `cat logs/ranking_job.log`
3. Test manually: `./scripts/rank_priority_symbols.sh`

### Python errors

1. Verify venv exists: `ls venv/bin/activate`
2. Check .env file: `cat .env | grep SUPABASE`
3. Test Python job directly:
   ```bash
   cd ml
   source venv/bin/activate
   python src/options_ranking_job.py --symbol AAPL
   ```

### No symbols processed

1. Check database connection
2. Verify symbols table has data
3. Check get_watchlist_symbols.py output:
   ```bash
   python src/scripts/get_watchlist_symbols.py
   ```

## Phase 2: On-Demand Ranking

Users can also trigger rankings manually from the macOS app:

1. Open the app
2. Navigate to Options → ML Ranker
3. Click "Generate Rankings" button
4. Wait 20-30 seconds for job to complete

**Note**: Currently this simulates a 30-second wait. To make it functional, you would need to deploy the Python job as a cloud function (AWS Lambda, etc.) and call it from an Edge Function.

## Cost Considerations

- Each symbol requires ~1-2 API calls (options chain + pricing)
- 10 symbols × hourly updates × 7 market hours = ~70 API calls/day
- Monitor your API provider's rate limits and costs

## Next Steps

To make on-demand ranking fully functional:

1. Deploy Python job as AWS Lambda or Google Cloud Function
2. Create Edge Function that triggers the Lambda
3. Update `OptionsRankerViewModel.triggerRankingJob()` to call the Edge Function
4. Remove the 30-second sleep simulation
