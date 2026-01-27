# Forecast Quality Monitoring and Validation Guide

## Quick Health Check

Run this to verify the ensemble is working correctly:

```bash
# Check latest forecast confidence levels
python -c "
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

os.chdir('ml')
load_dotenv()

from src.data.supabase_db import db

query = db.client.table('ml_forecasts_intraday').select(
    'symbol_id,confidence,ensemble_label,created_at'
).gte(
    'created_at',
    (datetime.utcnow() - timedelta(hours=1)).isoformat()
).order('created_at', desc=True).limit(50).execute()

if query.data:
    symbols = {}
    for row in query.data:
        if row['symbol_id'] not in symbols:
            symbols[row['symbol_id']] = row

    print('Symbol | Confidence | Ensemble')
    print('-------|------------|----------')

    at_40 = 0
    above_50 = 0
    for sid in sorted(symbols.keys())[:7]:
        fc = symbols[sid]
        conf = float(fc['confidence']) * 100
        if conf > 50:
            above_50 += 1
        elif conf == 40:
            at_40 += 1
        print(f'{sid[:8]} | {conf:6.1f}%   | {fc[\"ensemble_label\"]}')

    print()
    print(f'Status: {above_50}/7 > 50%, {at_40}/7 at 40%')
    if above_50 >= 4:
        print('✅ HEALTHY: Ensemble working properly')
    elif above_50 > 0:
        print('⚠️  DEGRADED: Some symbols working')
    else:
        print('❌ FAILED: All at 40% (ensemble broken)')
"
```

---

## Expected Behavior

### ✅ Healthy State
- 4-7 symbols showing confidence > 50%
- Average confidence 55-75%
- Ensemble labels varied: bullish, bearish, neutral
- Model agreement populated
- No symbols stuck at exactly 40%

### ⚠️ Degraded State
- 1-3 symbols showing confidence > 50%
- Some symbols at minimum 40%
- May indicate:
  - Insufficient training data for some symbols
  - Missing indicator data
  - Market stagnation (all models agree to be neutral)

### ❌ Failed State
- All 7 symbols at exactly 40%
- All ensemble_labels identical
- Model agreement NULL
- **Indicates**: Ensemble not training (usually TensorFlow issue)
- **Action**: Check workflow logs for TensorFlow errors

---

## Troubleshooting Guide

### Issue: All Forecasts at 40%

**Diagnostic Steps**:
```bash
# 1. Check if Transformer is enabled (should be false)
grep ENABLE_TRANSFORMER .github/workflows/ml-orchestration.yml | head -1

# 2. Check workflow logs for TensorFlow errors
gh run view <run-id> --log | grep -i tensorflow

# 3. Test ensemble locally
cd ml
python -c "
from src.ensemble import get_production_ensemble
from src.data.supabase_db import db
ensemble = get_production_ensemble()
print('Ensemble models:', ensemble.models)
"
```

**Common Causes**:
1. ENABLE_TRANSFORMER set to true (TensorFlow missing)
2. All required training data missing
3. Database connection issue

**Fixes**:
1. Verify ENABLE_TRANSFORMER=false in workflow
2. Check if OHLC data exists: `db.fetch_ohlc_bars('AAPL', 'h1', limit=10)`
3. Verify database connection with smoke tests

---

### Issue: Some Symbols at 40%, Others Normal

**Diagnostic Steps**:
```bash
# Check indicator data availability
python -c "
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

os.chdir('ml')
load_dotenv()

from src.data.supabase_db import db

symbols = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'AMZN', 'GOOGL']

for ticker in symbols:
    try:
        symbol_id = db.get_symbol_id(ticker)
        indicators = db.client.table('indicator_values').select('timeframe').eq(
            'symbol_id', symbol_id
        ).gte(
            'created_at',
            (datetime.utcnow() - timedelta(hours=2)).isoformat()
        ).execute()

        if indicators.data:
            print(f'✅ {ticker}: {len(indicators.data)} indicator records')
        else:
            print(f'❌ {ticker}: NO indicator data in last 2 hours')
    except Exception as e:
        print(f'⚠️  {ticker}: Error - {str(e)[:50]}')
"
```

**Common Causes**:
1. intraday_forecast_job not saving indicators for that symbol
2. Symbol excluded from indicator calculation
3. Data pipeline incomplete for that symbol

**Fixes**:
1. Run single-symbol test: `python -m src.intraday_forecast_job --symbol NVDA`
2. Check indicator_values table: `select count(*) where symbol_id = 'xxx' and created_at > now() - interval '2 hours'`
3. Verify symbol is in the processing universe

---

### Issue: Model Agreement NULL

**Indicates**: Ensemble voting system not working

**Check**:
```bash
# Verify ensemble is returning predictions
python -c "
import os
os.chdir('ml')
from src.ensemble import get_production_ensemble
from src.data.supabase_db import db

ensemble = get_production_ensemble()
ohlc = db.fetch_ohlc_bars('AAPL', 'h1', limit=100)

result = ensemble.train(ohlc, current_price=ohlc[-1]['close'])
print('Ensemble result:', result)
print('Has agreement:', 'agreement' in result)
"
```

---

## Daily Checks

### Each Morning
- [ ] Check workflow executed successfully
- [ ] Verify at least 4 symbols have confidence > 50%
- [ ] Confirm no TensorFlow errors in logs
- [ ] Check model health report in workflow summary

### Weekly Reviews
- [ ] Monitor average confidence trend
- [ ] Review model accuracy from evaluations
- [ ] Check if any symbols consistently failing
- [ ] Verify evaluation data accumulation

### Monthly Analysis
- [ ] Compare current performance to baseline
- [ ] Identify symbols needing attention
- [ ] Plan any model configuration updates
- [ ] Review TensorFlow integration possibility

---

## Performance Baseline

As of Jan 27, 2026 (post-fix):

| Metric | Value | Status |
|--------|-------|--------|
| Avg Confidence | 56.6% | ✅ Good |
| Symbols > 50% | 4/7 | ✅ Good |
| Symbols at 40% | 3/7 | ⚠️ Needs investigation |
| Transformer Enabled | false | ✅ Correct |
| TensorFlow Required | false | ✅ No dependency |
| Evaluation Data | 26 (spread thin) | ⚠️ Accumulating |

---

## Key Metrics to Monitor

### 1. Confidence Distribution
```
Plot of confidence_level over time for each symbol
Should show:
  - Range: 40% to 95%
  - Variation: Not all same value
  - Trend: Improving over time as models train
```

### 2. Model Agreement
```
Count of symbols where model_agreement is populated
Should be:
  - 100% populated (not NULL)
  - Based on voting among ensemble models
  - Varying values (not all same)
```

### 3. Ensemble Label Distribution
```
Count of bullish vs bearish vs neutral predictions
Should be:
  - Roughly balanced (not all one direction)
  - Market-dependent (trending market = more directional)
  - Varying day-to-day
```

### 4. Evaluation Accuracy
```
Percentage of correct directional forecasts
Should be:
  - > 50% (better than random)
  - Reported in live_predictions table
  - Accumulating over time
```

---

## Alert Thresholds

### Critical (Should Alert)
- ❌ All symbols at exactly 40% confidence
- ❌ Ensemble labels all identical (all bullish/bearish/neutral)
- ❌ workflow fails with non-zero exit code
- ❌ TensorFlow import errors in logs

### Warning (Should Investigate)
- ⚠️ Average confidence < 45%
- ⚠️ > 3 symbols at 40%
- ⚠️ Missing indicator data for > 2 symbols
- ⚠️ Evaluation accuracy < 50%

### Info (Normal Operation)
- ℹ️ Sparse evaluation data (< 3 evaluations per symbol)
- ℹ️ Some symbols at 40% (if others healthy)
- ℹ️ populate_live_predictions warning (insufficient data)

---

## Workflow Status Reference

### ml-orchestration.yml Status

**Should see**:
```
✅ check-trigger: success
✅ ml-forecast: success (no TensorFlow errors)
✅ options-processing: success (or skipped)
✅ model-health: success (continue-on-error on populate step)
✅ smoke-tests: success
```

**Should NOT see**:
```
❌ ml-forecast: failure (indicates ensemble problem)
❌ TensorFlow not found error
❌ "All forecasts at 40%"
```

---

## Configuration Reference

### ENABLE_TRANSFORMER Setting
```yaml
# Current (correct for GitHub Actions)
ENABLE_TRANSFORMER: ${{ vars.ENABLE_TRANSFORMER || 'false' }}

# Alternative (only if TensorFlow added to CI)
ENABLE_TRANSFORMER: ${{ vars.ENABLE_TRANSFORMER || 'true' }}
```

**When to change back to true**:
- [ ] TensorFlow added to ml/requirements.txt
- [ ] GitHub Actions runner has TensorFlow available
- [ ] Test ensemble includes Transformer without errors
- [ ] Verify confidence levels improve with Transformer

---

## Useful Commands

```bash
# Quick health check
cd ml && python -m src.scripts.diagnose_intraday_forecast_issues

# Test single symbol
cd ml && python -m src.intraday_forecast_job --symbol AAPL

# Check evaluation data
cd ml && python -c "
from src.data.supabase_db import db
from datetime import datetime, timedelta
result = db.client.table('forecast_evaluations').select('symbol,horizon,count()').gte(
    'evaluation_date', (datetime.utcnow() - timedelta(days=7)).isoformat()
).execute()
print(result.data)
"

# Run full diagnostic
cd ml && python -m src.scripts.diagnose_intraday_forecast_issues

# Check workflow
gh run view <run-id> --log | grep -E "Confidence|Ensemble|ERROR"

# List recent workflow runs
gh run list --workflow ml-orchestration.yml -L 5
```

---

## Summary

The ensemble forecasting system should now:
1. ✅ Train successfully without TensorFlow
2. ✅ Produce varied confidence levels (not stuck at 40%)
3. ✅ Populate model_agreement through voting
4. ✅ Generate bullish/bearish/neutral labels

Monitor these metrics daily to ensure ongoing health of the forecasting system.
