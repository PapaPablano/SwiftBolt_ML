# Deployment Checklist - FastAPI Integration

## ✅ Pre-Deployment Status

### FastAPI Server
- ✅ FastAPI server code created (`ml/api/`)
- ✅ Docker setup complete (`ml/Dockerfile`, `ml/docker-compose.yml`)
- ✅ All 5 endpoints implemented and tested locally
- ✅ Server running locally at `http://localhost:8000`

### Edge Functions
- ✅ All 5 Edge Functions updated to use FastAPI
- ✅ Shared FastAPI client created (`_shared/fastapi-client.ts`)
- ✅ Python script execution removed
- ✅ Timeout handling added
- ✅ Error handling improved

## 📋 Deployment Steps

### Step 1: Deploy FastAPI Server

Choose one deployment option:

#### Option A: Railway (Recommended)
1. Create account at [railway.app](https://railway.app)
2. Create new project
3. Connect GitHub repository
4. Add environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
5. Deploy from `ml/` directory
6. Get deployment URL (e.g., `https://swiftbolt-ml-api.railway.app`)

#### Option B: Render
1. Create account at [render.com](https://render.com)
2. Create new Web Service
3. Connect GitHub repository
4. Set build command: `cd ml && pip install -r requirements.txt`
5. Set start command: `cd ml && uvicorn api.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables
7. Deploy and get URL

#### Option C: Docker (Self-hosted)
```bash
cd ml
docker build -t swiftbolt-ml-api .
docker run -d -p 8000:8000 --env-file .env swiftbolt-ml-api
```

### Step 2: Set FastAPI URL in Supabase

```bash
# Using Supabase CLI
supabase secrets set FASTAPI_URL=https://your-fastapi-server.com

# Or in Supabase Dashboard:
# Project Settings → Edge Functions → Environment Variables
# Add: FASTAPI_URL = https://your-fastapi-server.com
```

### Step 3: Deploy Edge Functions

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Deploy all 5 functions
supabase functions deploy technical-indicators
supabase functions deploy backtest-strategy
supabase functions deploy walk-forward-optimize
supabase functions deploy portfolio-optimize
supabase functions deploy stress-test

# Or use deployment script
./scripts/deploy_ml_functions.sh
```

### Step 4: Verify Deployment

Test each endpoint:

```bash
# Set your project URL and keys
PROJECT_URL="https://cygflaemtmwiwaviclks.supabase.co"
ANON_KEY="your-anon-key"

# Test technical indicators
curl "${PROJECT_URL}/functions/v1/technical-indicators?symbol=AAPL&timeframe=d1" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H "apikey: ${ANON_KEY}"

# Test backtest
curl -X POST "${PROJECT_URL}/functions/v1/backtest-strategy" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H "apikey: ${ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "buy_and_hold",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

## 🔍 Verification Checklist

- [ ] FastAPI server deployed and accessible
- [ ] `FASTAPI_URL` set in Supabase environment variables
- [ ] All 5 Edge Functions deployed
- [ ] Technical indicators endpoint working
- [ ] Backtest endpoint working
- [ ] Walk-forward endpoint working
- [ ] Portfolio optimization endpoint working
- [ ] Stress test endpoint working
- [ ] Swift app can call endpoints successfully

## 🐛 Troubleshooting

### Edge Function Errors

**Error: "FASTAPI_URL environment variable not set"**
- Solution: Set `FASTAPI_URL` in Supabase Dashboard

**Error: "Request timeout"**
- Solution: Increase timeout in `fastapi-client.ts` or check FastAPI server performance

**Error: "Connection refused"**
- Solution: Verify FastAPI server is running and accessible
- Check firewall/network settings
- Verify URL is correct (no trailing slash)

### FastAPI Server Errors

**Error: "Module not found"**
- Solution: Ensure all dependencies in `requirements.txt` are installed

**Error: "Database connection failed"**
- Solution: Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set correctly

## 📝 Post-Deployment

1. Monitor Edge Function logs in Supabase Dashboard
2. Monitor FastAPI server logs
3. Test from Swift app
4. Check error rates and response times
5. Set up alerts for failures

## 🔄 Rollback Plan

If issues occur:

1. **Temporary**: Revert Edge Functions to previous version
2. **Permanent**: Keep both code paths and use feature flag
3. **Alternative**: Use Supabase Edge Functions with Python subprocess (original approach)
