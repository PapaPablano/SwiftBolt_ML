# Part 6-8: Implementation Checklist, Key Decisions, Expected Improvements

## Part 6: Phase-by-Phase Implementation Plan

### Phase 1: Foundation (Days 1-2)

**Objective**: Build core data preparation and model training

#### Day 1: Data Preparation
- [ ] Create `ml/src/training/` directory
  ```bash
  mkdir -p ml/src/training
  touch ml/src/training/__init__.py
  ```

- [ ] Create `ml/src/training/data_preparation.py` (from `TRAINING_PIPELINE_IMPLEMENTATION.md`)
  - [ ] `collect_training_data()` function
  - [ ] `create_labels()` function with threshold
  - [ ] `prepare_train_validation_split()` with temporal ordering
  - [ ] `validate_data_integrity()` checks

- [ ] Test data preparation
  ```bash
  cd /Users/ericpeterson/SwiftBolt_ML
  python -c "
  from ml.src.training.data_preparation import collect_training_data, create_labels
  data = collect_training_data(['AAPL'], lookback_days=60)
  print(f'Collected: {list(data.keys())}')
  "
  ```

- [ ] Verify no data leakage
  - [ ] Check: train data ends before validation data starts
  - [ ] Check: labels only on future data
  - [ ] Check: no NaN values

#### Day 2: Model Training
- [ ] Create `ml/src/training/model_training.py`
  - [ ] `ModelTrainer` class initialization
  - [ ] `train_random_forest()` method
  - [ ] `train_gradient_boosting()` method
  - [ ] `train_all_models()` orchestrator

- [ ] Test model training
  ```bash
  python -c "
  from ml.src.training.data_preparation import *
  from ml.src.training.model_training import ModelTrainer
  
  # Get data
  data = collect_training_data(['AAPL'])
  df = data['d1']['AAPL']
  features, labels = create_labels(df)
  train_f, valid_f, train_l, valid_l = prepare_train_validation_split(features, labels)
  
  # Train
  trainer = ModelTrainer('AAPL', 'd1')
  results = trainer.train_all_models(train_f, train_l, valid_f, valid_l)
  print(f'Results: {results}')
  "
  ```

- [ ] Verify model accuracy
  - [ ] Check: RF valid accuracy between 50-65%
  - [ ] Check: GB valid accuracy between 50-65%
  - [ ] Check: No excessive overfitting (train > valid by >20%)

**Checkpoint 1**: Can train RF + GB on single symbol/timeframe ✅

---

### Phase 2: Ensemble Integration (Days 3-4)

**Objective**: Optimize weights and serialize models

#### Day 3: Weight Optimization
- [ ] Create `ml/src/training/weight_optimizer.py`
  - [ ] `EnsembleWeightOptimizer` class
  - [ ] `optimize_weights()` using Ridge regression
  - [ ] `validate_weights()` checks

- [ ] Test weight optimization
  ```bash
  python -c "
  from ml.src.training.weight_optimizer import EnsembleWeightOptimizer
  import numpy as np
  
  # Create mock predictions
  predictions = {
      'rf': np.random.rand(100, 3),
      'gb': np.random.rand(100, 3),
  }
  
  labels = np.random.choice(['BULLISH', 'NEUTRAL', 'BEARISH'], 100)
  
  optimizer = EnsembleWeightOptimizer()
  weights = optimizer.optimize_weights(predictions, labels)
  print(f'Weights: {weights}')
  print(f'Valid: {optimizer.validate_weights()}')
  "
  ```

- [ ] Verify weights
  - [ ] Check: weights sum to 1.0
  - [ ] Check: all weights positive
  - [ ] Check: weights reflect model performance

#### Day 4: Full Orchestration
- [ ] Create `ml/src/training/ensemble_training_job.py` (from `TRAINING_PIPELINE_IMPLEMENTATION.md`)
  - [ ] `train_ensemble_for_symbol_timeframe()` main function
  - [ ] Steps 1-8 chained together
  - [ ] Model serialization to disk
  - [ ] Database storage of metrics
  - [ ] `train_all_timeframes_all_symbols()` orchestrator

- [ ] Create `trained_models/` directory
  ```bash
  mkdir -p /Users/ericpeterson/SwiftBolt_ML/trained_models
  ```

- [ ] Test full training pipeline
  ```bash
  cd /Users/ericpeterson/SwiftBolt_ML
  python -m ml.src.training.ensemble_training_job --symbol AAPL --timeframe d1
  ```

- [ ] Verify outputs
  - [ ] Check: `trained_models/AAPL_d1_*.pkl` file created
  - [ ] Check: File size > 1MB
  - [ ] Check: Console shows training progress

**Checkpoint 2**: Can train, optimize, and serialize full ensemble ✅

---

### Phase 3: Production Connection (Days 5-6)

**Objective**: Load trained models and integrate with forecast job

#### Day 5: Model Loading
- [ ] Create `ml/src/models/ensemble_loader.py` (from `ENSEMBLE_INTEGRATION_GUIDE.md`)
  - [ ] `EnsembleLoader` class
  - [ ] `load_latest_model()` method
  - [ ] `list_available_models()` method
  - [ ] `get_model_info()` method
  - [ ] `get_production_ensemble_with_trained_weights()` factory

- [ ] Test model loading
  ```bash
  python -c "
  from ml.src.models.ensemble_loader import (
      EnsembleLoader,
      get_production_ensemble_with_trained_weights
  )
  
  # List available
  models = EnsembleLoader.list_available_models()
  print(f'Available: {models}')
  
  # Load specific
  model_info = EnsembleLoader.get_model_info('AAPL', 'd1')
  if model_info:
      print(f'Loaded: {model_info}')
  
  # Load into ensemble
  ensemble = get_production_ensemble_with_trained_weights('AAPL', 'd1')
  print(f'Ensemble trained: {ensemble.is_trained}')
  "
  ```

#### Day 6: Integration with Forecast Job
- [ ] Backup current `multi_horizon_forecast_job.py`
  ```bash
  cp ml/src/multi_horizon_forecast_job.py ml/src/multi_horizon_forecast_job.py.backup
  ```

- [ ] Modify `multi_horizon_forecast_job.py`
  - [ ] Add import: `from src.models.ensemble_loader import get_production_ensemble_with_trained_weights`
  - [ ] Replace `get_production_ensemble()` calls
  - [ ] Add check: `if not ensemble.is_trained: logger.error(...); return None`
  - [ ] Add helpful error message with training command

- [ ] Test integration end-to-end
  ```bash
  # First train
  python -m ml.src.training.ensemble_training_job --symbol AAPL
  
  # Then run forecast
  python -m ml.src.multi_horizon_forecast_job --symbols AAPL
  ```

- [ ] Verify database has forecast results
  ```sql
  SELECT * FROM ml_forecasts WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL') LIMIT 5;
  ```

**Checkpoint 3**: Can train models → load in forecast job → produce forecasts ✅

---

### Phase 4: Monitoring (Days 7)

**Objective**: Set up drift monitoring and automated alerts

#### Day 7: Drift Monitoring
- [ ] Create `ml/src/training/drift_monitor.py` (from `DRIFT_MONITORING_SYSTEM.md`)
  - [ ] `PerformanceMetrics` dataclass
  - [ ] `DriftMonitor` class
  - [ ] `compute_daily_metrics()` method
  - [ ] `get_drift_status()` method
  - [ ] `store_metrics_to_db()` method

- [ ] Create `ml/src/training/drift_check_job.py`
  - [ ] `fetch_yesterday_forecasts()` function
  - [ ] `fetch_actual_results()` function
  - [ ] `run_daily_drift_check()` orchestrator
  - [ ] Alert generation

- [ ] Create database table
  ```sql
  CREATE TABLE drift_monitoring (
      id BIGSERIAL PRIMARY KEY,
      symbol_id BIGINT NOT NULL REFERENCES symbols(id),
      timeframe TEXT NOT NULL,
      date DATE NOT NULL,
      accuracy FLOAT,
      n_predictions INT,
      baseline_accuracy FLOAT,
      drift_margin FLOAT,
      drift_detected BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT NOW(),
      UNIQUE(symbol_id, timeframe, date)
  );
  
  CREATE INDEX idx_drift_monitoring_symbol_timeframe 
      ON drift_monitoring(symbol_id, timeframe, date DESC);
  ```

- [ ] Test drift monitoring
  ```bash
  python -m ml.src.training.drift_check_job --symbols AAPL
  ```

**Checkpoint 4**: Drift monitoring running and alerting ✅

---

### Phase 5: GitHub Actions Workflows (Days 7-8)

**Optional but recommended for production**

#### Create `.github/workflows/train-ensemble-monthly.yml`

```yaml
name: Train Ensemble Models - Monthly

on:
  schedule:
    - cron: '0 0 1 * *'  # 1st of month at midnight UTC
  workflow_dispatch:

jobs:
  train-ensemble:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Train ensemble
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
        run: |
          python -m ml.src.training.ensemble_training_job --all
      
      - name: Upload trained models
        uses: actions/upload-artifact@v3
        with:
          name: trained-models
          path: trained_models/
          retention-days: 30
```

#### Create `.github/workflows/check-drift-daily.yml`

```yaml
name: Check Model Drift - Daily

on:
  schedule:
    - cron: '0 10 * * MON-FRI'  # 10am UTC (after market hours)
  workflow_dispatch:

jobs:
  check-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Check drift
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          python -m ml.src.training.drift_check_job --symbols AAPL SPY
      
      - name: Send Slack alert on drift
        if: failure()
        uses: slackapi/slack-github-action@v1.24.0
        with:
          payload: |
            {
              "text": "\ud83d\udea8 Model drift detected!",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "Check drift monitoring for details"
                  }
                }
              ]
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## Part 7: Key Decisions You Must Make

### Decision 1: Retraining Frequency

**Current Recommendation**: Monthly full retrain + weekly weight updates

**Trade-offs Table**:

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **Monthly Full** | Stable, low compute cost | May lag market changes | Conservative, low volatility |
| **Weekly Full** | Adaptive, catches trends | Higher compute cost | Active markets, frequent updates |
| **Daily Full** | Very responsive | Excessive compute, overfitting risk | NOT recommended |
| **Monthly Full + Weekly Weights** | ✅ Balanced | Slightly more complex | **RECOMMENDED** |

**Your Decision**: Start with monthly full + weekly weight updates. Monitor drift daily, trigger emergency retrain if accuracy drops > 20%.

**Action**: 
- [ ] Set training schedule in GitHub Actions
- [ ] Document retraining calendar
- [ ] Set up drift-triggered emergency retraining

---

### Decision 2: Model Selection

**Current Recommendation**: Start with RF + GB, add ARIMA-GARCH after 2 weeks

**Model Complexity Table**:

| Model | Train Time | Stability | Data Requirements | When to Use |
|-------|-----------|-----------|------------------|-------------|
| **RF** | 1 min | Very stable | Medium (500 bars) | Always (core) |
| **GB** | 1 min | Stable | Medium (500 bars) | Always (core) |
| **ARIMA-GARCH** | 5 min | Moderate | Medium (500 bars) | After 2 weeks validation |
| **Prophet** | 3 min | Stable | Medium (500 bars) | After 2 weeks validation |
| **LSTM** | 10+ min | Unstable | High (1000+ bars) | Only after 3+ months live data |

**Your Decision**:
- [ ] Phase 1 (Now): RF + GB only
- [ ] Phase 2 (Week 3): Add ARIMA-GARCH if drift < 10%
- [ ] Phase 3 (Month 2): Add Prophet if drift continuing to decrease
- [ ] Phase 4 (Month 3+): Consider LSTM only with extensive validation

---

### Decision 3: Weight Optimization Method

**Current Recommendation**: Ridge Regression with α=1.0

**Methods Comparison**:

| Method | Complexity | Bias | Variance | When to Use |
|--------|-----------|------|----------|-------------|
| **Equal (0.33 each)** | Trivial | High | Low | Baseline only |
| **Least Squares** | Low | Low | High | Overfitting risk |
| **Ridge (α=1.0)** | Low | Low-Med | Med | ✅ RECOMMENDED |
| **Ridge (α=10.0)** | Low | Med | Low | If weights too specialized |
| **Lasso** | Med | Low | Low | If specific models fail |

**Your Decision**: Ridge α=1.0. Inspect weights monthly - if one model > 80%, increase α to 10.0 to regularize.

**Action**:
- [ ] Start with α=1.0
- [ ] Monitor weight evolution
- [ ] Document when/why you change α

---

### Decision 4: Validation Split

**Current Recommendation**: 70% train / 30% validation, time-ordered, no shuffling

**Why This Split**:
- 70% train = 420 bars for D1 = ~2 years worth of training data
- 30% validation = 180 bars for D1 = ~9 months of unseen data
- Proper temporal ordering prevents look-ahead bias
- Large validation set gives stable weight estimates

**Alternative Splits**:

| Split | Train Samples | Valid Samples | Risk |
|-------|---------------|---------------|------|
| 80/20 | 480 | 120 | Validation set too small, unstable weights |
| **70/30** | 420 | 180 | ✅ BALANCED |
| 60/40 | 360 | 240 | Training set might be too small |
| K-fold | Variable | Variable | Breaks temporal ordering! DON'T USE |

**Your Decision**: Stick with 70/30 time-ordered split. NEVER shuffle data.

---

### Decision 5: Drift Thresholds

**Current Recommendation**:
- Normal: Accuracy > (Baseline - 5%)
- Monitor: (Baseline - 15%) to (Baseline - 5%)
- Drift Alert: Accuracy < (Baseline - 15%)
- Emergency: Accuracy < (Baseline - 25%)

**Reasoning**:
- Baseline = validation accuracy (~55-60%)
- Random baseline = 33% (so 55% is good)
- -5% margin = allow for natural variance
- -15% = real drift has occurred
- -25% = model is nearly random, act immediately

**Your Decision**: Accept defaults but review after 2 weeks of live data.

**Action**:
- [ ] Log all daily accuracies
- [ ] Review accuracy distribution after 2 weeks
- [ ] Adjust thresholds if needed (but stay conservative)

---

## Part 8: Expected Improvements

### Problem Resolution Matrix

| Issue | Before | After | Impact |
|-------|--------|-------|--------|
| "Ensemble not trained" error | ❌ Every run | ✅ Fixed | Forecasts now persist |
| Fragmented training | ❌ 5 separate paths | ✅ Single pipeline | 50% less maintenance |
| Weight optimization | ❌ Hardcoded 0.5/0.5 | ✅ Data-driven | Better accuracy |
| Performance tracking | ❌ Manual inspection | ✅ Automated daily | Catch drift early |
| Reproducibility | ❌ Models lost on restart | ✅ Versioned artifacts | Full reproducibility |
| Model retraining | ❌ Manual, ad-hoc | ✅ Scheduled monthly | Consistent updates |

### Expected Performance Metrics

After 1 month of operation (realistic ranges):

#### Model-Level Metrics
```
Random Forest:
  Train Accuracy: 75-85%
  Validation Accuracy: 52-65%
  Improvement: Consistent retraining

Gradient Boosting:
  Train Accuracy: 70-80%
  Validation Accuracy: 50-62%
  Improvement: Better than RF on some symbols

Ensemble:
  Train Accuracy: 78-83%
  Validation Accuracy: 53-63%
  Improvement: Better than individual models
```

#### System-Level Metrics
```
Forecasts Generated:
  Before: 0 (RuntimeError)
  After: 500+ daily (all symbols × timeframes)
  
Forecasts Persisted:
  Before: 0%
  After: 100%
  
Drift Detection:
  Before: Never
  After: Daily monitoring, alerts enabled
  
Retraining:
  Before: Manual, monthly
  After: Automatic, monthly + weekly weights + daily monitoring
```

#### User-Facing Improvements
```
Dashboard Forecast Tab:
  Before: "Ensemble not trained" error
  After: 3+ horizons per timeframe, confidence bands, handoff metrics
  
Multi-Horizon System:
  Before: Broken (no forecasts)
  After: Full cascading forecasts across all timeframes
  
Consensus Forecasts:
  Before: Not calculated
  After: Daily consensus across timeframes with agreement scores
  
Model Drift Alerts:
  Before: No monitoring
  After: Daily accuracy reports + Slack alerts on drift
```

### Compute Cost Estimates

**Monthly Full Retrain** (1st of month):
- Training: ~20-30 minutes
- CPU usage: ~100% for 30 min (cloud: ~$0.50-1.00)
- Storage: ~100MB (trained models on disk)
- Total monthly: ~$0.75

**Weekly Weight Updates** (Mondays):
- Training: ~5-10 minutes
- CPU usage: ~100% for 10 min
- Total: ~$0.15 per week = ~$0.60/month

**Daily Drift Checks**:
- Checking: ~2-3 minutes
- CPU usage: ~50% for 5 min
- Total: ~$0.05 per day = ~$1.50/month

**Total Monthly Cost**: ~$3-4/month (in cloud compute)

---

### Success Indicators (Check After 1 Month)

- [ ] Multi-horizon forecasts generate successfully every day (no "Ensemble not trained" errors)
- [ ] At least 500+ forecasts stored in database daily
- [ ] Ensemble validation accuracy between 50-65%
- [ ] Walk-forward accuracy between 48-58%
- [ ] Drift monitoring running daily, generating daily accuracy reports
- [ ] No drift alerts for >5 consecutive days (models stable)
- [ ] Models serialized and versioned by date
- [ ] Retraining job runs without errors
- [ ] Dashboard shows multi-horizon forecasts instead of errors

---

## Implementation Timeline

```
Week 1:
  Day 1: Data preparation layer ✅
  Day 2: Model training layer ✅
  Day 3: Weight optimization + serialization ✅
  Day 4: Full orchestration + test ✅
  Day 5: Integration with forecast job ✅
  Day 6: Full end-to-end test ✅
  Day 7: Drift monitoring setup ✅

Week 2:
  GitHub Actions workflows setup
  Production deployment
  Initial monitoring and baseline calibration

Week 3+:
  Monitor drift daily
  Make decision 1-5 adjustments based on real data
  Scale to additional symbols/timeframes
  Integrate with trading signals
```

---

## Rollback Plan

If something breaks in production:

1. **Immediate**: Disable multi-horizon forecast job
   ```bash
   # Temporarily stop daily forecasting
   # Revert multi_horizon_forecast_job.py to backup
   cp ml/src/multi_horizon_forecast_job.py.backup ml/src/multi_horizon_forecast_job.py
   ```

2. **Short-term**: Use previous model version
   ```python
   # Don't update to latest model, use known-good version
   # EnsembleLoader defaults to latest, so just delete bad model file
   rm trained_models/AAPL_d1_20250121.pkl
   ```

3. **Long-term**: Manual investigation
   - Check drift_monitoring table for accuracy trending
   - Review training_runs for model performance
   - Identify what changed (market regime, feature drift, etc.)

---

## Next Steps

1. ✅ Read all 8 parts of this training system documentation
2. → Create directory structure and implement Phase 1-2
3. → Test on single symbol (AAPL, single timeframe D1)
4. → Verify models can be loaded and used for prediction
5. → Implement Phase 3-4 for full monitoring
6. → Deploy to production with daily monitoring
7. → Monitor for 2 weeks, then make Decision 1-5 adjustments

**Estimated Total Time**: 5-7 days to fully operational
**Estimated Maintenance**: ~1 hour/week after deployed

---

## Support & Debugging

### Key Log Files

```bash
# Training logs
ls -lh /Users/ericpeterson/SwiftBolt_ML/logs/training/

# Drift monitoring logs
ls -lh /Users/ericpeterson/SwiftBolt_ML/logs/drift/

# Forecast job logs  
ls -lh /Users/ericpeterson/SwiftBolt_ML/logs/forecasts/
```

### Debug Commands

```bash
# Check if models exist
ls -lh trained_models/

# Load and inspect a model
python -c "import pickle; m=pickle.load(open('trained_models/AAPL_d1_*.pkl','rb')); print(m.keys())"

# Test training pipeline
python -m ml.src.training.ensemble_training_job --symbol AAPL --timeframe d1

# Test forecast generation
python -m ml.src.multi_horizon_forecast_job --symbols AAPL

# Test drift checking
python -m ml.src.training.drift_check_job --symbols AAPL
```

---

**Good luck! 🚀**

Your SwiftBolt_ML system is about to get a massive reliability and accuracy boost. Follow this playbook and you'll have a world-class ML training system in one week.
