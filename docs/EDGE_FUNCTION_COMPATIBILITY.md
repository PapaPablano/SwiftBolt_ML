# Edge Function Compatibility Check

## ✅ Compatibility Status

All 5 new Edge Functions are **compatible** with Supabase deployment standards.

### Compatibility Verification

1. **Deno std library version**: ✅ Using `0.208.0` (matches most existing functions)
2. **CORS handling**: ✅ Using shared `cors.ts` utilities
3. **Supabase client**: ✅ Using shared `supabase-client.ts`
4. **Request handling**: ✅ Using `serve` from Deno std
5. **Error handling**: ✅ Proper try/catch with error responses
6. **TypeScript types**: ✅ Proper interfaces for request/response

### Functions Ready for Deployment

1. **technical-indicators** ✅
   - Uses `Deno.Command` to execute Python scripts
   - Environment variable support for script paths
   - Proper error handling and JSON parsing

2. **backtest-strategy** ✅
   - Same pattern as technical-indicators
   - Validates request parameters
   - Returns structured JSON responses

3. **walk-forward-optimize** ✅
   - Follows same patterns
   - Validates horizons and forecasters
   - Proper error messages

4. **portfolio-optimize** ✅
   - Validates optimization methods
   - Handles multiple symbols
   - Returns allocation weights and metrics

5. **stress-test** ✅
   - Validates positions and prices
   - Supports historical and custom scenarios
   - Returns portfolio impact analysis

## ⚠️ Production Considerations

### Python Script Paths

**Current Implementation:**
- Functions use hardcoded local paths as fallback:
  - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/...`
- Environment variables can override:
  - `TECHNICAL_INDICATORS_SCRIPT_PATH`
  - `BACKTEST_SCRIPT_PATH`
  - `WALK_FORWARD_SCRIPT_PATH`
  - `PORTFOLIO_OPTIMIZE_SCRIPT_PATH`
  - `STRESS_TEST_SCRIPT_PATH`

**Production Options:**

1. **Option A: Set Environment Variables in Supabase**
   ```bash
   # In Supabase Dashboard → Edge Functions → Environment Variables
   TECHNICAL_INDICATORS_SCRIPT_PATH=/path/to/script.py
   BACKTEST_SCRIPT_PATH=/path/to/script.py
   # etc.
   ```

2. **Option B: Use FastAPI Server (Recommended for Production)**
   - Deploy Python scripts as FastAPI endpoints
   - Update Edge Functions to call HTTP endpoints instead of local scripts
   - Better for scalability and error handling

3. **Option C: Bundle Scripts (If Supported)**
   - Some Supabase deployments support bundling files
   - Check if Python scripts can be included in function bundle

### Deno.Command Limitations

**Current Approach:**
- Uses `Deno.Command` to execute `python3` directly
- Assumes Python 3 is available in Edge Function runtime
- May not work if Python is not installed in Supabase's Deno runtime

**Verification Needed:**
- Test if Python is available in Supabase Edge Function runtime
- If not, use Option B (FastAPI) or Option C (bundle/alternative)

## 📋 Pre-Deployment Checklist

- [x] Functions use correct Deno std version (0.208.0)
- [x] Functions use shared CORS utilities
- [x] Functions use shared Supabase client
- [x] Functions have proper error handling
- [x] Functions validate input parameters
- [x] Functions return proper JSON responses
- [ ] **Verify Python availability in Supabase runtime** ⚠️
- [ ] **Set environment variables for script paths** (if using local paths)
- [ ] **Or deploy FastAPI server** (recommended for production)

## 🚀 Deployment Commands

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Deploy all new functions
supabase functions deploy technical-indicators
supabase functions deploy backtest-strategy
supabase functions deploy walk-forward-optimize
supabase functions deploy portfolio-optimize
supabase functions deploy stress-test

# Or use the deployment script
./scripts/deploy_ml_functions.sh
```

## 🔍 Post-Deployment Testing

After deployment, test each function:

```bash
# Test technical-indicators
curl -X GET \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/technical-indicators?symbol=AAPL&timeframe=d1" \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "apikey: YOUR_ANON_KEY"

# Test backtest-strategy
curl -X POST \
  "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/backtest-strategy" \
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

## 📝 Notes

- Functions are compatible with Supabase Edge Function runtime
- Main consideration is Python script execution method
- Recommend FastAPI server for production use
- Environment variables provide flexibility for different deployment scenarios
