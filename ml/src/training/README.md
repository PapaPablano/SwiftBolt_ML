# Training Pipeline

Complete training system for SwiftBolt ML ensemble models.

## Overview

This training pipeline:
1. ✅ Fetches historical data from Supabase (via feature cache)
2. ✅ Creates labels from future price movements
3. ✅ Trains Random Forest + Gradient Boosting models
4. ✅ Optimizes ensemble weights using Ridge regression
5. ✅ Saves trained models to `trained_models/` directory
6. ✅ Logs performance metrics to database

## Quick Start

### Train All Symbols/Timeframes

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python ml/src/training/ensemble_training_job.py
```

This will:
- Train models for all symbols in `settings.symbols_to_process`
- Train all timeframes: m15, h1, h4, d1
- Save artifacts to `trained_models/SYMBOL_TIMEFRAME_YYYYMMDD.pkl`
- Log metrics to `training_runs` table

### Train Single Symbol/Timeframe

```python
from src.data.supabase_db import SupabaseDatabase
from src.training.ensemble_training_job import train_ensemble_for_symbol_timeframe

db = SupabaseDatabase()
result = train_ensemble_for_symbol_timeframe(
    db=db,
    symbol="AAPL",
    timeframe="d1",
    lookback_days=90
)

print(f"Success: {result['success']}")
print(f"Accuracy: {result['validation_accuracy']:.1%}")
print(f"Weights: {result['weights']}")
```

## Module Structure

### `data_preparation.py`

**Functions:**
- `collect_training_data()` - Fetches OHLC + features from database
- `create_labels()` - Generates BULLISH/NEUTRAL/BEARISH labels from future returns
- `select_features_for_training()` - Filters to numeric, non-OHLC features
- `prepare_train_validation_split()` - Time-ordered split (70/30)

### `model_training.py`

**Class: `ModelTrainer`**
- `train_random_forest()` - Trains RF classifier (200 trees, max_depth=15)
- `train_gradient_boosting()` - Trains GB classifier (100 trees, lr=0.05)
- `train_all_models()` - Trains both models + returns performance metrics
- `get_model_predictions()` - Gets predictions for weight optimization

### `weight_optimizer.py`

**Class: `EnsembleWeightOptimizer`**
- `optimize_weights()` - Ridge regression to find optimal model weights
- `validate_weights()` - Ensures weights sum to 1 and are non-negative
- `get_ensemble_score()` - Calculates weighted ensemble prediction

### `ensemble_training_job.py`

**Main orchestration script:**
- `train_ensemble_for_symbol_timeframe()` - Complete training for 1 symbol/timeframe
- `train_all_timeframes_all_symbols()` - Batch training for all configs

## Model Artifacts

### Artifact Structure

Saved as `trained_models/AAPL_d1_20260122.pkl`:

```python
{
    "symbol": "AAPL",
    "timeframe": "d1",
    "timestamp": "20260122",
    "models": {
        "rf": <RandomForestClassifier>,
        "gb": <GradientBoostingClassifier>
    },
    "weights": {
        "rf": 0.52,
        "gb": 0.48
    },
    "performances": {
        "rf": {"train_accuracy": 0.85, "valid_accuracy": 0.58, ...},
        "gb": {"train_accuracy": 0.82, "valid_accuracy": 0.60, ...}
    },
    "ensemble_accuracy": 0.59,
    "config": {"bars": 250, "horizon": 5, "threshold": 0.01},
    "n_features": 47,
    "feature_names": ["rsi", "macd", "bb_width", ...]
}
```

### Loading Models in Production

Models are automatically loaded by `EnsemblePredictor`:

```python
from src.models.ensemble_loader import EnsemblePredictor

predictor = EnsemblePredictor(symbol="AAPL", timeframe="d1")
if predictor.is_trained:
    result = predictor.predict(df)
    print(result["forecast"])  # BULLISH/NEUTRAL/BEARISH
    print(result["confidence"])  # 0.72
```

## Timeframe Configurations

```python
TIMEFRAME_CONFIGS = {
    "m15": {"bars": 500, "horizon": 5, "threshold": 0.002},  # Predict 5 bars (~75min)
    "h1": {"bars": 500, "horizon": 5, "threshold": 0.003},   # Predict 5 bars (~5hrs)
    "h4": {"bars": 300, "horizon": 3, "threshold": 0.005},   # Predict 3 bars (~12hrs)
    "d1": {"bars": 250, "horizon": 5, "threshold": 0.01},    # Predict 5 bars (~1wk)
}
```

- **bars**: Number of historical bars to fetch
- **horizon**: Number of bars ahead to predict
- **threshold**: Minimum return to classify as BULLISH/BEARISH (e.g., 0.01 = 1%)

## Expected Performance

### Typical Metrics

| Metric | Target |
|--------|--------|
| Train Accuracy | 80-90% |
| Validation Accuracy | 55-65% |
| Ensemble Accuracy | 57-62% |
| Overfit Margin | <20% |

### Training Time

| Scope | Time |
|-------|------|
| Single symbol/timeframe | 1-2 min |
| All timeframes (1 symbol) | 5-8 min |
| All symbols (5) × 4 timeframes | 30-40 min |

## Validation Strategy

### Time-Ordered Split

```
|<-------- Training (70%) -------->|<-- Validation (30%) -->|
    Oldest data               Newest data
```

**Why time-ordered?**
- Prevents data leakage (model never sees future data during training)
- Realistic simulation of production performance
- Validation set represents "unseen" recent market conditions

### Walk-Forward Testing

For production validation, use `walk_forward_tester.py`:

```bash
python ml/src/backtesting/walk_forward_tester.py --symbol AAPL --timeframe d1
```

## Retraining Schedule

**Recommended:**
- **Full retrain**: Monthly (Day 1 of each month)
- **Weight update**: Weekly (every Monday)
- **Drift check**: Daily (via `drift_monitor.py`)

**Why monthly?**
- Market regimes change slowly
- Prevents overfitting to recent noise
- Balances stability vs. adaptability

## Troubleshooting

### Error: "No data for AAPL/d1"

**Cause:** Symbol not in database or no OHLC bars

**Fix:**
```python
from src.data.supabase_db import SupabaseDatabase
db = SupabaseDatabase()
df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=500)
print(len(df))  # Should be > 0
```

### Error: "Insufficient  X rows"

**Cause:** Less than 100 bars available

**Fix:** Reduce `bars` in `TIMEFRAME_CONFIGS` or backfill historical data

### Error: "No numeric feature columns found"

**Cause:** Technical indicators not computed

**Fix:** Check `technical_indicators.py` is adding features:
```python
from src.features.technical_indicators import add_technical_features
df_with_features = add_technical_features(df)
print(df_with_features.columns)
```

### Low Validation Accuracy (<50%)

**Possible causes:**
1. Too much overfitting (train acc >> valid acc)
2. Market regime shift (retrain needed)
3. Insufficient features
4. Wrong threshold (too sensitive)

**Fixes:**
1. Reduce model complexity (`max_depth`, `n_estimators`)
2. Retrain with recent data
3. Add more technical indicators
4. Increase threshold (e.g., 0.005 → 0.01)

## Integration with Production

Once trained, models are automatically used by:

1. **Multi-Horizon Forecast Job** (`multi_horizon_forecast_job.py`)
   - Runs daily at 6am UTC
   - Loads trained weights via `EnsembleLoader`
   - Generates forecasts for all symbols/timeframes

2. **Validation Dashboard** (Swift app)
   - Displays model performance metrics
   - Shows weight distributions
   - Tracks live accuracy vs. baseline

3. **Drift Monitor** (TODO)
   - Compares daily accuracy to baseline
   - Triggers retraining if accuracy drops >15%

## Next Steps

1. ✅ Run training: `python ml/src/training/ensemble_training_job.py`
2. ✅ Verify artifacts: `ls trained_models/`
3. ✅ Test loading: `python ml/src/training/test_training.py`
4. ✅ Run forecast job: `python ml/src/multi_horizon_forecast_job.py`
5. ⏳ Add drift monitoring
6. ⏳ Schedule monthly retraining (GitHub Actions or cron)

## References

- [Part 4: Integration with Production](../../TRAINING_SYSTEM_PART4_COMPLETE.md)
- [Multi-Horizon Forecasting](../../docs/Multi-Horizon-Forecasting-Implementation.md)
- [Ensemble Loader](../models/ensemble_loader.py)
- [Walk-Forward CV](../backtesting/walk_forward_tester.py)
