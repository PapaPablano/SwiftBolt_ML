# Apply H1 Query Fix

## Problem
The `get_chart_data_v2` function currently queries the `intraday_bars` table for h1 data, but our Alpaca backfill writes to `ohlc_bars_v2`. This means the 506+ Alpaca bars we've successfully backfilled aren't being returned by the chart API.

## Solution
Update the `get_chart_data_v2` function to query `ohlc_bars_v2` for historical h1 data (dates before today) and only use `intraday_bars` for today's real-time data.

## How to Apply

### Option 1: Via Supabase Dashboard SQL Editor (Recommended)

1. Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql/new
2. Copy the entire SQL content from: `backend/supabase/migrations/20260109220000_fix_h1_query_to_use_ohlc_bars_v2.sql`
3. Paste it into the SQL editor
4. Click "Run"
5. You should see "Success. No rows returned"

### Option 2: Via psql (If you have database credentials)

```bash
cd backend
psql "postgresql://postgres:[YOUR_PASSWORD]@aws-1-us-east-1.pooler.supabase.com:5432/postgres" \
  -f supabase/migrations/20260109220000_fix_h1_query_to_use_ohlc_bars_v2.sql
```

### Option 3: Manual Copy-Paste

If you can't access the files, here's the SQL to run:

```sql
-- Just run the contents of: backend/supabase/migrations/20260109220000_fix_h1_query_to_use_ohlc_bars_v2.sql
```

## Verification

After applying, run this script to verify it's working:

```bash
./backend/scripts/check-chart-provider.sh
```

You should now see:
- `"provider": "alpaca"` instead of `"provider": "polygon"`
- Bar count much higher (500+ instead of 4)
- Dates spanning back to 2024-01-09

## What Changes

### Before (Current Behavior)
- h1 timeframe: Queries `intraday_bars` table only
- Result: Only sees today's real-time Polygon/Tradier data
- Alpaca backfill data is invisible

### After (Fixed Behavior)
- h1 timeframe historical (before today): Queries `ohlc_bars_v2` table (where Alpaca writes)
- h1 timeframe today: Queries `intraday_bars` table (real-time data)
- Result: Full historical data from Alpaca + today's real-time data

## Technical Details

The function now uses a UNION of two CTEs:
1. `historical_h1`: Selects from `ohlc_bars_v2` WHERE date < today
2. `realtime_h1`: Aggregates from `intraday_bars` WHERE date = today

This gives us the best of both worlds:
- Historical coverage from Alpaca backfill (2 years)
- Real-time intraday updates from Polygon/Tradier (today)
