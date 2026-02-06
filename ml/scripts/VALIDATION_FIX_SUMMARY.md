# Validation Script Fix - Threshold Mismatch Resolution

## Problem Identified

**Symptom:** Validation accuracy of 31.7% (worse than random 50%)

**Root Cause:** Training and validation used different label thresholds

| Component | Threshold Method | Example (PG) | Example (NVDA) |
|-----------|------------------|--------------|----------------|
| **Training** (BEFORE) | Adaptive Percentile (35th/65th) | ±0.3% | ±2.5% |
| **Validation** (BEFORE) | Fixed ±1.0% | ±1.0% | ±1.0% |
| **Validation** (AFTER FIX) | Adaptive Percentile (35th/65th) | ±0.3% | ±2.5% |

## The Mismatch Explained

### For Low-Volatility Stock (PG):
```
Training says:     < -0.3% = bearish, > +0.3% = bullish, else neutral
Validation (OLD):  < -1.0% = bearish, > +1.0% = bullish, else neutral

Actual return: +0.5%
  → Model predicts: "bullish" (trained on ±0.3% threshold)
  → Validation evaluates: "neutral" (using ±1.0% threshold)
  → Result: WRONG! ❌
```

### For High-Volatility Stock (NVDA):
```
Training says:     < -2.5% = bearish, > +2.5% = bullish, else neutral
Validation (OLD):  < -1.0% = bearish, > +1.0% = bullish, else neutral

Actual return: -1.5%
  → Model predicts: "neutral" (trained on ±2.5% threshold)
  → Validation evaluates: "bearish" (using ±1.0% threshold)
  → Result: WRONG! ❌
```

## Fix Applied

### File Modified:
`ml/scripts/blind_walk_forward_validation.py`

### Changes:

1. **Import adaptive thresholds:**
```python
from src.features.adaptive_thresholds import AdaptiveThresholds
```

2. **Replace fixed thresholds with adaptive (line ~230):**
```python
# BEFORE (WRONG):
if actual_return > 0.01:  # Fixed 1%
    actual_label = 'bullish'
elif actual_return < -0.01:  # Fixed -1%
    actual_label = 'bearish'
else:
    actual_label = 'neutral'

# AFTER (CORRECT):
bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
    train_df, horizon_days=horizon_days
)

if actual_return > bullish_thresh:
    actual_label = 'bullish'
elif actual_return < bearish_thresh:
    actual_label = 'bearish'
else:
    actual_label = 'neutral'
```

3. **Added threshold logging and recording:**
- Log thresholds for debugging
- Save thresholds in results CSV for analysis

## Expected Results After Fix

### Before Fix:
- Overall accuracy: **31.7%** ❌
- All symbols below 50% (worse than random)
- Systematic mismatch between training and validation

### After Fix (Expected):
- Overall accuracy: **50-65%** ✅
- Model performance properly measured
- Thresholds match training exactly

## How to Run Fixed Validation

### Quick Test (5 minutes):
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

python scripts/blind_walk_forward_validation.py \
  --symbols AAPL \
  --holdout-start 2026-01-15 \
  --holdout-end 2026-02-03
```

### Full Diversified Test (2-3 hours):
```bash
./scripts/run_diversified_validation.sh
```

## Verification Steps

### 1. Check threshold values in results:
```python
import pandas as pd
df = pd.read_csv('validation_results/diversified/validation_results_*.csv')

# Show threshold distribution by symbol
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol]
    print(f"{symbol}:")
    print(f"  Bearish threshold range: {symbol_df['bearish_threshold'].min():.4f} to {symbol_df['bearish_threshold'].max():.4f}")
    print(f"  Bullish threshold range: {symbol_df['bullish_threshold'].min():.4f} to {symbol_df['bullish_threshold'].max():.4f}")
```

**Expected:**
- PG (low volatility): thresholds around ±0.3% to ±0.5%
- NVDA (high volatility): thresholds around ±2.0% to ±3.0%
- MU (high volatility): thresholds around ±1.5% to ±2.5%

### 2. Compare accuracy before/after:

| Metric | Before Fix | After Fix (Expected) |
|--------|------------|---------------------|
| Overall accuracy | 31.7% | 50-65% |
| PG accuracy | 33.2% | 55-60% |
| NVDA accuracy | 31.0% | 50-55% |
| MU accuracy | 39.4% | 52-58% |

## Why This Fix is Critical

**Golden Rule of ML Validation:**
> Validation must use THE EXACT SAME data processing, features, and thresholds as training.

**What we had:**
- Training: "Predict if stock moves >percentile threshold"
- Validation: "Predict if stock moves >1%"
- Result: Apples-to-oranges comparison = meaningless results

**What we have now:**
- Training: "Predict if stock moves >percentile threshold"
- Validation: "Predict if stock moves >percentile threshold"
- Result: Fair evaluation of actual model performance ✅

## Lessons Learned

1. **Always match validation to training** - Every preprocessing step must be identical
2. **Adaptive thresholds are powerful** - They create balanced labels across different volatility regimes
3. **Low accuracy isn't always model failure** - Could be evaluation mismatch
4. **Log everything** - Threshold values are now recorded for transparency

## Next Steps

1. **Run quick test** (5 min) - Verify fix works on 1 symbol
2. **Run full test** (3 hours) - Get real accuracy on 8 diverse stocks
3. **Analyze results** - Use `analyze_validation_diversity.py`
4. **Make deployment decision** - If accuracy >55%, deploy!

---

**Status:** ✅ FIXED - Ready to re-run validation

**Date:** 2026-02-03

**Impact:** Transforms validation from broken (31.7%) to accurate measurement of true model performance
