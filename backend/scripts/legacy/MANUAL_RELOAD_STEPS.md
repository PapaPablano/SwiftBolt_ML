# Manual Watchlist Reload - Simple Steps

## Step 1: Clear Data (Run in Supabase Dashboard)

Go to Supabase SQL Editor and run:

```sql
-- Clear watchlist chart data (preserves ML forecasts)
WITH watchlist_symbols AS (
  SELECT UNNEST(ARRAY['AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR']) as ticker
)
DELETE FROM ohlc_bars_v2 
WHERE symbol_id IN (
  SELECT s.id 
  FROM symbols s 
  JOIN watchlist_symbols ws ON s.ticker = ws.ticker
)
AND provider != 'ml_forecast';

-- Verify deletion
SELECT 
  s.ticker,
  COUNT(*) as bars_remaining,
  STRING_AGG(DISTINCT provider, ', ') as providers
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
GROUP BY s.ticker
ORDER BY s.ticker;
```

## Step 2: Backfill Hourly Data

From `/Users/ericpeterson/SwiftBolt_ML/ml`:

```bash
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe h1
```

## Step 3: Backfill Daily Data

```bash
python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe d1
```

## Step 4: Verify

Run in Supabase SQL Editor:

```sql
SELECT 
  s.ticker,
  ob.provider,
  ob.timeframe,
  COUNT(*) as bar_count,
  MAX(ob.ts) as latest_bar
FROM ohlc_bars_v2 ob
JOIN symbols s ON s.id = ob.symbol_id
WHERE s.ticker IN ('AAPL', 'AMD', 'AMZN', 'CRWD', 'MU', 'NVDA', 'PLTR')
AND ob.provider = 'alpaca'
GROUP BY s.ticker, ob.provider, ob.timeframe
ORDER BY s.ticker, ob.timeframe;
```

Expected: ~100 bars per symbol for h1 and d1 timeframes.
