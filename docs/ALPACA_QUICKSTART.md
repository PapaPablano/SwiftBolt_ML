# Alpaca Integration Quick Start Guide

This guide will help you integrate Alpaca Market Data API into SwiftBoltML in under 10 minutes.

## Prerequisites

- Supabase project set up
- Supabase CLI installed
- Node.js/Deno runtime for Edge Functions

## Step 1: Get Alpaca API Keys (2 minutes)

1. Visit https://app.alpaca.markets/brokerage/dashboard/overview
2. Sign up for a free account (no credit card required)
3. Navigate to **API Keys** section in the right sidebar
4. Click **Generate New Keys**
5. Save both the **API Key ID** and **Secret Key** securely

## Step 2: Configure Secrets (1 minute)

Set your Alpaca credentials as Supabase secrets:

```bash
cd backend/supabase

# Set Alpaca credentials
supabase secrets set ALPACA_API_KEY=your-alpaca-api-key-id
supabase secrets set ALPACA_API_SECRET=your-alpaca-api-secret-key

# Verify secrets are set
supabase secrets list
```

## Step 3: Deploy Migration (2 minutes)

Apply the database migration to enable Alpaca support:

```bash
# Push all pending migrations
supabase db push

# Or apply specific migration
psql $DATABASE_URL -f migrations/20260109150000_add_alpaca_provider.sql
```

## Step 4: Deploy Edge Functions (3 minutes)

Deploy the updated Edge Functions with Alpaca support:

```bash
# Deploy all functions
supabase functions deploy

# Or deploy specific functions
supabase functions deploy chart-data-v2
supabase functions deploy fetch-bars
```

## Step 5: Test the Integration (2 minutes)

### Test 1: Fetch Historical Bars

```bash
curl -X POST 'https://your-project.supabase.co/functions/v1/chart-data-v2' \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "timeframe": "d1",
    "days": 30,
    "includeForecast": false
  }'
```

Expected response:
```json
{
  "symbol": "AAPL",
  "timeframe": "d1",
  "layers": {
    "historical": {
      "count": 30,
      "provider": "alpaca",
      "data": [...]
    }
  }
}
```

### Test 2: Verify Provider in Database

```sql
-- Check that Alpaca data is being stored
SELECT 
  provider,
  COUNT(*) as bar_count,
  MIN(ts) as earliest,
  MAX(ts) as latest
FROM ohlc_bars_v2
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
GROUP BY provider
ORDER BY bar_count DESC;
```

Expected output:
```
 provider | bar_count |      earliest       |       latest        
----------+-----------+---------------------+---------------------
 alpaca   |       250 | 2025-01-01 00:00:00 | 2026-01-09 00:00:00
 yfinance |       180 | 2024-06-01 00:00:00 | 2025-12-31 00:00:00
```

## Verification Checklist

- [ ] Alpaca API keys are set in Supabase secrets
- [ ] Migration applied successfully (check `supabase_migrations` table)
- [ ] Edge Functions deployed without errors
- [ ] Test API call returns data with `provider: "alpaca"`
- [ ] Database contains bars with `provider = 'alpaca'`

## Troubleshooting

### Issue: "Missing required API keys"

**Symptom**: Edge Function logs show `ALPACA_API_KEY or ALPACA_API_SECRET not set`

**Solution**: 
```bash
# Verify secrets are set
supabase secrets list

# Re-set if missing
supabase secrets set ALPACA_API_KEY=your-key
supabase secrets set ALPACA_API_SECRET=your-secret

# Redeploy functions to pick up new secrets
supabase functions deploy
```

### Issue: "401 Unauthorized" from Alpaca

**Symptom**: API calls fail with authentication error

**Solution**:
1. Verify your API keys are correct in Alpaca dashboard
2. Check if keys are for the correct environment (paper vs live)
3. Regenerate keys if needed and update secrets

### Issue: No data returned

**Symptom**: Empty bars array in response

**Solution**:
1. Check if symbol exists: `SELECT * FROM symbols WHERE ticker = 'AAPL'`
2. Verify date range is valid (not weekends/holidays)
3. Check Alpaca API status: https://status.alpaca.markets
4. Review Edge Function logs: `supabase functions logs chart-data-v2`

### Issue: Rate limit errors

**Symptom**: `429 Too Many Requests`

**Solution**:
1. Free tier has ~200 calls/min limit
2. Implement caching on client side
3. Reduce polling frequency
4. Consider upgrading to paid tier

## Next Steps

### Enable Backfilling

Backfill historical data for your watchlist:

```bash
# Run backfill for specific symbols
curl -X POST 'https://your-project.supabase.co/functions/v1/backfill' \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "timeframe": "d1",
    "days": 365
  }'
```

### Monitor Provider Health

Check provider health and usage:

```sql
-- Provider usage statistics
SELECT 
  provider,
  COUNT(*) as total_bars,
  COUNT(DISTINCT symbol_id) as symbols_covered,
  MAX(fetched_at) as last_fetch
FROM ohlc_bars_v2
WHERE fetched_at > NOW() - INTERVAL '7 days'
GROUP BY provider
ORDER BY total_bars DESC;
```

### Configure Rate Limits

Adjust rate limits for your tier:

```bash
# For paid Alpaca tier with unlimited calls
supabase secrets set ALPACA_MAX_RPS=50
supabase secrets set ALPACA_MAX_RPM=1000
```

## Performance Tips

1. **Cache aggressively**: Historical bars don't change
2. **Use WebSocket**: For real-time data (future enhancement)
3. **Batch requests**: Fetch multiple symbols in one call when possible
4. **Monitor costs**: Track API usage via Alpaca dashboard

## Support

- **Alpaca API Issues**: https://alpaca.markets/support
- **Integration Issues**: See `docs/ALPACA_INTEGRATION.md`
- **General Help**: Open a GitHub issue

## Resources

- [Full Integration Guide](./ALPACA_INTEGRATION.md)
- [Alpaca Documentation](https://docs.alpaca.markets)
- [API Reference](https://docs.alpaca.markets/reference)
- [Data Plans & Pricing](https://alpaca.markets/data)
