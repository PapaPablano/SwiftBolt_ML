# Deployment Instructions for Data Layer Separation

## Step 1: Deploy Database Migrations

### Option A: Using Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Execute the following migrations in order:

#### Migration 1: Create ohlc_bars_v2 table
Copy and paste the contents of:
```
backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql
```

#### Migration 2: Migrate existing data
Copy and paste the contents of:
```
backend/supabase/migrations/20260105000001_migrate_to_v2.sql
```

### Option B: Using Supabase CLI

```bash
cd backend/supabase

# Mark migrations as applied (if needed)
supabase migration repair --status applied 20260105000000
supabase migration repair --status applied 20260105000001

# Push migrations
supabase db push
```

## Step 2: Test Historical Backfill

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Test with single symbol
python ml/src/scripts/deep_backfill_ohlc_v2.py --symbol AAPL

# Test with multiple symbols
python ml/src/scripts/deep_backfill_ohlc_v2.py --symbols AAPL NVDA TSLA

# Backfill all watchlist symbols
python ml/src/scripts/deep_backfill_ohlc_v2.py --all --timeframe d1
```

## Step 3: Test ML Forecast Generation

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Test with single symbol
python -m ml.src.services.forecast_service_v2 --symbol AAPL --horizon 10

# Test with multiple symbols
python -m ml.src.services.forecast_service_v2 --symbols AAPL NVDA --horizon 10

# Generate forecasts for all watchlist
python -m ml.src.services.forecast_service_v2 --all --horizon 10
```

## Step 4: Verify Data in Database

Run these queries in Supabase SQL Editor to verify:

```sql
-- Check ohlc_bars_v2 table exists
SELECT COUNT(*) as total_bars, 
       provider, 
       is_intraday, 
       is_forecast,
       data_status
FROM ohlc_bars_v2
GROUP BY provider, is_intraday, is_forecast, data_status;

-- Check historical data for AAPL
SELECT COUNT(*) as bar_count,
       MIN(ts) as earliest,
       MAX(ts) as latest
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND provider = 'polygon'
  AND is_forecast = false;

-- Check forecasts for AAPL
SELECT ts, close, upper_band, lower_band, confidence_score
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND provider = 'ml_forecast'
  AND is_forecast = true
ORDER BY ts ASC;
```

## Step 5: Deploy Edge Functions

```bash
cd backend/supabase

# Deploy chart-data-v2 function
supabase functions deploy chart-data-v2

# Test the function
curl -X POST \
  "https://your-project.supabase.co/functions/v1/chart-data-v2" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "days": 60, "includeForecast": true}'
```

## Step 6: Update Client Applications

Update your client code to use the new endpoint:

```typescript
// Old endpoint
const response = await fetch('/functions/v1/chart-data', {
  method: 'POST',
  body: JSON.stringify({ symbol: 'AAPL' })
});

// New endpoint with layer separation
const response = await fetch('/functions/v1/chart-data-v2', {
  method: 'POST',
  body: JSON.stringify({ 
    symbol: 'AAPL',
    days: 60,
    includeForecast: true,
    forecastDays: 10
  })
});

const data = await response.json();
// data.layers.historical - Polygon data
// data.layers.intraday - Tradier data (today only)
// data.layers.forecast - ML predictions
```

## Step 7: Enable GitHub Actions

After testing, enable the automated workflows:

1. Verify secrets are set in GitHub:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `TRADIER_TOKEN`
   - `MASSIVE_API_KEY` (for Polygon)

2. Enable workflow:
```bash
# The workflow will run automatically every 15 minutes during market hours
# File: .github/workflows/intraday-update-v2.yml
```

3. Test manual trigger:
   - Go to GitHub Actions
   - Select "Intraday Update V2 (Tradier)"
   - Click "Run workflow"
   - Enter test symbols (e.g., "AAPL,NVDA")

## Verification Checklist

- [ ] ohlc_bars_v2 table created with proper schema
- [ ] Validation triggers active and blocking invalid writes
- [ ] Historical data migrated from ohlc_bars
- [ ] AAPL backfill test successful (should have ~500 bars)
- [ ] AAPL forecast test successful (should have 10 future bars)
- [ ] Chart API returns three separate layers
- [ ] Client app renders historical, intraday, and forecast distinctly
- [ ] GitHub Action runs successfully during market hours
- [ ] No data corruption (historical data unchanged after intraday updates)

## Rollback Plan

If issues occur:

1. Client apps can continue using old `ohlc_bars` table
2. Disable GitHub Actions workflow
3. Drop `ohlc_bars_v2` table if needed:
```sql
DROP TABLE IF EXISTS ohlc_bars_v2 CASCADE;
```

## Monitoring

After deployment, monitor:

1. **Data quality**: Check for gaps or anomalies
2. **API performance**: Monitor chart-data-v2 response times
3. **Workflow success**: Check GitHub Actions logs
4. **Database size**: Monitor storage growth

```sql
-- Monitor data growth
SELECT 
  DATE(created_at) as date,
  provider,
  COUNT(*) as bars_added
FROM ohlc_bars_v2
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), provider
ORDER BY date DESC, provider;
```
