# ML Integration - Deployment Status

## 📋 Pending Deployments

The following Edge Functions have been created locally but **NOT yet deployed** to Supabase:

### New Edge Functions (Phase 1 & 2)

1. **technical-indicators** ✅ Created
   - Path: `supabase/functions/technical-indicators/index.ts`
   - Status: ⏳ **NOT DEPLOYED**
   - Purpose: Calculate and return technical indicators for a symbol/timeframe

2. **backtest-strategy** ✅ Created
   - Path: `supabase/functions/backtest-strategy/index.ts`
   - Status: ⏳ **NOT DEPLOYED**
   - Purpose: Run backtests for trading strategies (SuperTrend AI, SMA Crossover, Buy & Hold)

3. **walk-forward-optimize** ✅ Created
   - Path: `supabase/functions/walk-forward-optimize/index.ts`
   - Status: ⏳ **NOT DEPLOYED**
   - Purpose: Run walk-forward optimization for ML forecasters

4. **portfolio-optimize** ✅ Created
   - Path: `supabase/functions/portfolio-optimize/index.ts`
   - Status: ⏳ **NOT DEPLOYED**
   - Purpose: Optimize portfolio allocation (Max Sharpe, Min Variance, Risk Parity, Efficient)

5. **stress-test** ✅ Created
   - Path: `supabase/functions/stress-test/index.ts`
   - Status: ⏳ **NOT DEPLOYED**
   - Purpose: Run stress tests on portfolios using historical scenarios

## 🚀 Deployment Instructions

### Option 1: Deploy All at Once (Recommended)

```bash
cd /Users/ericpeterson/SwiftBolt_ML
./scripts/deploy_ml_functions.sh
```

### Option 2: Deploy Individually

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Deploy each function
supabase functions deploy technical-indicators
supabase functions deploy backtest-strategy
supabase functions deploy walk-forward-optimize
supabase functions deploy portfolio-optimize
supabase functions deploy stress-test
```

### Option 3: Verify Current Status

```bash
# List all deployed functions
supabase functions list

# Check if new functions are deployed
supabase functions list | grep -E "(technical-indicators|backtest-strategy|walk-forward-optimize|portfolio-optimize|stress-test)"
```

## ⚠️ Prerequisites

Before deploying, ensure:

1. **Python Scripts Accessible**: The Edge Functions call Python scripts at these paths:
   - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/get_technical_indicators.py`
   - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_backtest.py`
   - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_walk_forward.py`
   - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/optimize_portfolio.py`
   - `/Users/ericpeterson/SwiftBolt_ML/ml/scripts/run_stress_test.py`

   **Note**: In production, these paths may need to be:
   - Set via environment variables in Supabase Dashboard
   - Or the scripts need to be accessible from the Edge Function runtime
   - Or use a FastAPI server instead of direct Python calls

2. **Project Linked**: ✅ Confirmed - Project is linked to `cygflaemtmwiwaviclks`

3. **Environment Variables**: The Edge Functions use:
   - `SUPABASE_URL` (auto-set by Supabase)
   - `SUPABASE_SERVICE_ROLE_KEY` (auto-set by Supabase)
   - Optional: Custom script paths via environment variables

## 📝 Deployment Checklist

- [ ] Deploy `technical-indicators`
- [ ] Deploy `backtest-strategy`
- [ ] Deploy `walk-forward-optimize`
- [ ] Deploy `portfolio-optimize`
- [ ] Deploy `stress-test`
- [ ] Verify all functions appear in `supabase functions list`
- [ ] Test each function via Swift app or curl
- [ ] Set environment variables for Python script paths (if needed)

## 🔍 Verification

After deployment, verify each function:

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

## 📊 Current Status

**Project**: swiftbolt_db (cygflaemtmwiwaviclks)  
**Region**: East US (North Virginia)  
**Linked**: ✅ Yes  
**New Functions Deployed**: ❌ 0/5

---

**Last Updated**: $(date)
