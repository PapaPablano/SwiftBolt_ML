# Intraday Forecast Quality - Next Steps

## Current Status: ✅ Primary Issue FIXED

The ensemble is now training properly (not stuck at 40% minimum). However, 3 symbols still need attention.

---

## Remaining Work

### High Priority: Indicator Data Issues

#### Issue 1: CRWD - Missing Indicator Data
**Symptom**: Showing 40% confidence despite having OHLC data
**Root Cause**: `intraday_forecast_job.py` not saving indicators for CRWD
**Evidence**:
- ✅ OHLC data available (h1 bars)
- ❌ No indicator data in last 3 hours
- ❌ Confidence stuck at 40%

**Debug Steps**:
1. Run single-symbol test for CRWD:
   ```bash
   cd ml
   python -m src.intraday_forecast_job --symbol CRWD 2>&1 | grep -A 5 "indicator"
   ```
2. Check if indicators are being calculated
3. Check if save is failing silently
4. Verify `indicator_values` table structure

**Expected Output**: Should see indicators being saved for CRWD

---

#### Issue 2: NVDA - Missing Indicator Data
**Symptom**: Showing 40% confidence despite having OHLC data
**Root Cause**: `intraday_forecast_job.py` not saving indicators for NVDA
**Evidence**:
- ✅ OHLC data available (h1 bars)
- ❌ No indicator data in last 3 hours
- ❌ Confidence stuck at 40%

**Debug Steps**:
1. Run single-symbol test for NVDA:
   ```bash
   cd ml
   python -m src.intraday_forecast_job --symbol NVDA 2>&1 | grep -A 5 "indicator"
   ```
2. Check if indicators are being calculated
3. Check if save is failing silently
4. Look for symbol-specific data issues

**Expected Output**: Should see indicators being saved for NVDA

---

#### Issue 3: AAPL - Has Indicators but Training Fails
**Symptom**: Showing 40% confidence even though indicator data exists
**Root Cause**: Ensemble training fails despite having features
**Evidence**:
- ✅ Indicator data available (h8 timeframe)
- ❌ Ensemble not using the data
- ❌ Confidence stuck at 40%

**Debug Steps**:
1. Check what timeframe intraday_forecast_job uses for AAPL
2. Run debug script:
   ```bash
   cd ml
   python -c "
   from src.data.supabase_db import db
   aapl_id = db.get_symbol_id('AAPL')
   # Check what indicators actually exist
   indicators = db.client.table('indicator_values').select('*').eq('symbol_id', aapl_id).limit(5).execute()
   print('AAPL indicators:', [list(i.keys()) for i in indicators.data[:2]])
   "
   ```
3. Run standalone ensemble training with AAPL data
4. Check if specific indicators are missing or malformed

**Expected Output**: Should identify what's blocking AAPL's ensemble training

---

### Medium Priority: Verification and Monitoring

#### Task 1: Monitor Next Scheduled Workflow Run
**When**: Tomorrow (or next scheduled run)
**What to Check**:
- Confidence levels for all symbols
- Are CRWD/NVDA/AAPL still at 40%?
- Are the 4 good symbols still > 50%?
- Is model_agreement still populated?

**Success Criteria**:
- At least 4/7 symbols > 50% (consistent with current results)
- No regressions

---

#### Task 2: Document Performance Baseline
**Goal**: Establish what "healthy" looks like for confidence levels

**Steps**:
1. Run forecasts for 1 week with current settings
2. Record average confidence by symbol
3. Check if higher confidence correlates with forecast accuracy
4. Use as baseline for future improvements

---

### Low Priority: Future Enhancements

#### Task 1: Re-enable Transformer Model
**When**: Once TensorFlow is available in CI environment
**Steps**:
1. Add `tensorflow` to `requirements-ml.txt`
2. Update workflow to include TensorFlow installation
3. Change ENABLE_TRANSFORMER back to `true` (or use new variable)
4. Test ensemble produces higher confidence with Transformer

**Expected Benefit**: Potentially 2-5% improvement in forecast confidence

---

#### Task 2: Add Monitoring and Alerting
**Goal**: Catch silent failures earlier

**Implementation**:
1. Add metrics export from `unified_forecast_job.py`
2. Track ensemble failure count per symbol
3. Set up alerts if:
   - All symbols stuck at minimum confidence
   - Ensemble fails > 10% of attempts
   - Indicator data not updated for 2+ hours

---

## Work Timeline

### Today/Tomorrow
- [ ] Wait for next scheduled workflow run to verify consistency
- [ ] Check if fix is stable across multiple runs

### This Week
- [ ] Debug CRWD indicator saving issue
- [ ] Debug NVDA indicator saving issue
- [ ] Debug AAPL ensemble training issue
- [ ] Document any schema mismatches or data issues found

### Next Week
- [ ] Implement monitoring/alerting
- [ ] Plan TensorFlow integration for Transformer re-enablement

---

## Testing Commands

### Quick Confidence Check
```bash
# See latest confidence levels
python -c "
from datetime import datetime, timedelta
from src.data.supabase_db import db
from dotenv import load_dotenv
import os

load_dotenv()

query = db.client.table('ml_forecasts_intraday').select(
    'symbol_id,confidence,ensemble_label,created_at'
).gte(
    'created_at',
    (datetime.utcnow() - timedelta(hours=1)).isoformat()
).order('created_at', desc=True).limit(50).execute()

symbols = {}
for row in query.data:
    if row['symbol_id'] not in symbols:
        symbols[row['symbol_id']] = row

for sid, fc in sorted(symbols.items()):
    conf = float(fc['confidence']) * 100
    print(f'{sid[:8]}: {conf:5.1f}% {fc[\"ensemble_label\"]:8} @ {fc[\"created_at\"][:16]}')
"
```

### Full Diagnostic
```bash
python -m src.scripts.diagnose_intraday_forecast_issues
```

### Test Single Symbol
```bash
python -m src.intraday_forecast_job --symbol CRWD
python -m src.intraday_forecast_job --symbol NVDA
python -m src.intraday_forecast_job --symbol AAPL
```

---

## Summary

**What We Fixed**: ✅ Transformer model causing 100% forecasts to fail
**What's Working**: ✅ 4/7 symbols now showing healthy confidence (57-87%)
**What Needs Work**: ⏳ 3 symbols at 40% (indicator data or training issues)

The primary issue is resolved. The remaining work is secondary debugging of symbol-specific problems.
