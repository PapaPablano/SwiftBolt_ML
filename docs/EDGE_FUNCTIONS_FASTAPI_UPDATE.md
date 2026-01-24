# Edge Functions Updated for FastAPI

All 5 ML Edge Functions have been updated to call FastAPI instead of executing Python scripts directly.

## ✅ Updated Functions

1. **technical-indicators** - Now calls `GET /api/v1/technical-indicators`
2. **backtest-strategy** - Now calls `POST /api/v1/backtest-strategy`
3. **walk-forward-optimize** - Now calls `POST /api/v1/walk-forward-optimize`
4. **portfolio-optimize** - Now calls `POST /api/v1/portfolio-optimize`
5. **stress-test** - Now calls `POST /api/v1/stress-test`

## 🔧 Changes Made

### Shared FastAPI Client

Created `supabase/functions/_shared/fastapi-client.ts` with:
- `fetchWithTimeout()` - HTTP requests with timeout
- `getFastApiUrl()` - Gets FastAPI URL from environment
- `callFastApi<T>()` - Generic function to call FastAPI endpoints

### Function Updates

Each Edge Function now:
- ✅ Imports `callFastApi` from shared module
- ✅ Removed `Deno.Command` and Python script execution
- ✅ Removed `getPythonScriptPath()` functions
- ✅ Uses HTTP requests to FastAPI instead
- ✅ Includes appropriate timeouts (30s-120s depending on operation)

## 📋 Environment Variables Required

Set in Supabase Dashboard → Edge Functions → Environment Variables:

```bash
FASTAPI_URL=https://your-fastapi-server.com
```

For local testing:
```bash
FASTAPI_URL=http://localhost:8000
```

## 🚀 Deployment Steps

### 1. Deploy FastAPI Server

First, deploy your FastAPI server to a hosting platform (Railway, Render, AWS, etc.) and get the URL.

### 2. Set Environment Variable in Supabase

```bash
# Using Supabase CLI
supabase secrets set FASTAPI_URL=https://your-fastapi-server.com

# Or in Supabase Dashboard
# Go to: Project Settings → Edge Functions → Environment Variables
# Add: FASTAPI_URL = https://your-fastapi-server.com
```

### 3. Deploy Updated Edge Functions

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Deploy all 5 functions
supabase functions deploy technical-indicators
supabase functions deploy backtest-strategy
supabase functions deploy walk-forward-optimize
supabase functions deploy portfolio-optimize
supabase functions deploy stress-test

# Or use the deployment script
./scripts/deploy_ml_functions.sh
```

### 4. Verify Deployment

Test each endpoint:

```bash
# Test technical indicators
curl "https://your-project.supabase.co/functions/v1/technical-indicators?symbol=AAPL&timeframe=d1" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "apikey: YOUR_ANON_KEY"

# Test backtest
curl -X POST "https://your-project.supabase.co/functions/v1/backtest-strategy" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "buy_and_hold",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

## ⚠️ Important Notes

1. **FastAPI Must Be Running**: Edge Functions will fail if FastAPI server is not accessible
2. **Network Access**: Ensure Supabase Edge Functions can reach your FastAPI server
3. **CORS**: FastAPI CORS is configured to allow all origins (update for production)
4. **Timeouts**: Different operations have different timeouts:
   - Technical Indicators: 30s
   - Backtesting: 60s
   - Walk-Forward: 120s
   - Portfolio Optimization: 60s
   - Stress Testing: 30s

## 🔄 Rollback Plan

If you need to rollback to Python script execution:

1. Revert the Edge Function changes (remove FastAPI calls, restore `Deno.Command`)
2. Or set `FASTAPI_URL` to empty and functions will throw an error (not ideal)
3. Better: Keep both code paths and use environment variable to switch

## 📝 Next Steps

1. ✅ Edge Functions updated to use FastAPI
2. ⏳ Deploy FastAPI server to production
3. ⏳ Set `FASTAPI_URL` in Supabase environment variables
4. ⏳ Deploy updated Edge Functions
5. ⏳ Test all endpoints
6. ⏳ Monitor logs for any issues
