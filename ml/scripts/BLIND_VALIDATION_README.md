# Blind Walk-Forward Validation

## What is This?

This script tests your ML ensemble on **data it has never seen** - the gold standard for model validation.

## Why Better Than Canary?

| Method | Time | Risk | Data Points | Confidence |
|--------|------|------|-------------|------------|
| **Blind Walk-Forward** | 2-3 hours | Zero | 720+ | High |
| Canary Deployment | 7 days | Medium | 21 | Low |

## How It Works

```
1. Hold out last 90 days (Oct 15, 2025 - Feb 3, 2026)
   └─→ This data is NEVER used for training

2. For each day in holdout:
   ├─→ Train on ALL data BEFORE that day
   ├─→ Make prediction for 1D/5D/10D/20D ahead
   └─→ Record prediction

3. Compare predictions to actual outcomes
   └─→ Calculate accuracy, RMSE, etc.
```

## Quick Start

### Test on Canary Symbols (Recommended)
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

python scripts/blind_walk_forward_validation.py \
  --symbols AAPL,MSFT,SPY \
  --holdout-start 2025-10-15 \
  --holdout-end 2026-02-03 \
  --horizons 1D,5D,10D,20D
```

**Expected output:**
```
Validating AAPL
  AAPL walk-forward: 100%|████████████| 78/78 [00:45<00:00, 1.73it/s]
  Total predictions: 312 (78 days × 4 horizons)
  Accuracy: 67.3%
  1D accuracy: 62.8% (n=78)
  5D accuracy: 69.2% (n=78)
  10D accuracy: 70.5% (n=78)
  20D accuracy: 66.7% (n=78)

Validating MSFT
  ...

OVERALL ACCURACY: 65.2% (936 predictions)
```

### Test Different Holdout Periods

**Short holdout (30 days):**
```bash
python scripts/blind_walk_forward_validation.py \
  --holdout-start 2026-01-01 \
  --holdout-end 2026-02-03
```

**Long holdout (6 months):**
```bash
python scripts/blind_walk_forward_validation.py \
  --holdout-start 2025-08-01 \
  --holdout-end 2026-02-03
```

### Test TabPFN Model
```bash
python scripts/blind_walk_forward_validation.py \
  --model-type tabpfn
```

## Output Files

```
validation_results/
├── validation_results_20260203_210130.csv
│   └─→ All predictions with actual outcomes
│       Columns: symbol, test_date, horizon, predicted_label, 
│                actual_label, correct, actual_return, confidence
│
└── validation_report_20260203_210130.json
    └─→ Summary statistics
        ├── overall_accuracy
        ├── by_symbol: {AAPL: 67%, MSFT: 63%, ...}
        ├── by_horizon: {1D: 62%, 5D: 69%, ...}
        └── confidence_calibration: {high: 72%, med: 65%, low: 58%}
```

## Understanding Results

### Good Results ✅
- **Overall accuracy > 55%** (better than coin flip)
- **High confidence predictions > 65%** (model knows when it's right)
- **Consistent across symbols** (no cherry-picking)
- **Stable across horizons** (not overfitting to one horizon)

### Warning Signs ⚠️
- Overall accuracy < 50% (worse than random)
- High confidence predictions = low accuracy (miscalibrated)
- One symbol/horizon dominates (overfitting)
- Accuracy degrades over time (distribution shift)

## Analyzing Results

### Load Results in Python
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load results
df = pd.read_csv('validation_results/validation_results_20260203_210130.csv')

# Accuracy over time
df['test_date'] = pd.to_datetime(df['test_date'])
df.groupby('test_date')['correct'].mean().plot(title='Accuracy Over Time')
plt.axhline(0.5, color='r', linestyle='--', label='Random')
plt.legend()
plt.show()

# Confusion matrix
from sklearn.metrics import confusion_matrix, classification_report

print(classification_report(df['actual_label'], df['predicted_label']))
```

### Check Distribution Shift
```python
# Compare early vs late predictions
early = df[df['test_date'] < '2025-12-01']
late = df[df['test_date'] >= '2025-12-01']

print(f"Early period accuracy: {early['correct'].mean():.1%}")
print(f"Late period accuracy: {late['correct'].mean():.1%}")

if abs(early['correct'].mean() - late['correct'].mean()) > 0.10:
    print("⚠️ WARNING: >10% accuracy drop suggests distribution shift")
```

## Troubleshooting

### "Insufficient training data"
- Your holdout starts too early
- Solution: Use `--holdout-start 2025-11-01` (later date)

### "No data found for symbol"
- Symbol not in database
- Solution: Check `db.fetch_ohlc_bars()` returns data

### Script is slow
- Normal! Training 60+ models takes time
- Expected: 1-3 minutes per symbol
- Use `--symbols AAPL` to test one symbol first

### Accuracy seems low
- Check baseline: Is your model better than naive forecast?
- Compare to random (50%) and persistent forecast ("tomorrow = today")
- Low accuracy doesn't mean bad - market is hard!

## Next Steps After Validation

### If Accuracy > 55% ✅
1. Document results
2. Run canary (optional, for infrastructure testing)
3. Deploy to production

### If Accuracy 50-55% ⚠️
1. Check confidence calibration
2. Analyze which symbols/horizons work best
3. Consider ensemble reweighting
4. May still deploy with lower confidence threshold

### If Accuracy < 50% ❌
1. Check for bugs (look-ahead bias, data leakage)
2. Analyze feature importance
3. Test simpler baseline
4. DO NOT deploy until fixed

## FAQ

**Q: How is this different from regular walk-forward validation?**

A: Regular walk-forward uses ALL data (including holdout) to tune parameters.
Blind walk-forward treats holdout as "unseen future" - never used for tuning.

**Q: Why 90 days for holdout?**

A: Balances two goals:
- Enough test data (60+ trading days)
- Enough training data (leave 2+ years for training)

**Q: Should I adjust parameters based on validation results?**

A: **NO!** That defeats the purpose. If you tune based on holdout, it's no longer blind.
Run validation ONCE, then decide: deploy as-is, or go back to development.

**Q: Can I use this for hyperparameter tuning?**

A: **NO!** Use `WalkForwardOptimizer` for tuning (it has proper CV).
This script is for FINAL validation only, after all tuning is done.

## Research Citations

- Walk-forward validation: [web:92](https://www.emergentmind.com/topics/walk-forward-validation-strategy)
- Holdout set best practices: [web:94](https://docs.aws.amazon.com/sagemaker/latest/dg/how-it-works-model-validation.html)
- Model deployment strategies: [web:93](https://www.qwak.com/post/shadow-deployment-vs-canary-release-of-machine-learning-models)
