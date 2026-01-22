# SwiftBolt_ML: Statistically Sound Training System

## Executive Summary

Your multi-horizon forecasting system has **excellent architecture** but faces three critical training gaps:

1. **Ensemble Not Trained** - The "Ensemble not trained" log indicates the enhanced ensemble lacks calibrated weights for your 5-model architecture (RF, GB, ARIMA-GARCH, Prophet, LSTM)
2. **No Unified Training Pipeline** - Training currently happens ad-hoc (GA job, evaluation job, intraday calibrator) without integrated coordination
3. **Walk-Forward Validation Incomplete** - You have walk-forward logic but it's not connected to production retraining

This document provides a **complete, production-ready training system** that:
- ✅ Trains ensemble with proper statistical rigor (walk-forward validation, cross-validation)
- ✅ Calibrates model weights using ridge regression on holdout data
- ✅ Validates on recent unseen data (prevents data leakage, ensures realistic performance)
- ✅ Detects performance drift automatically
- ✅ Coordinates with your multi-horizon forecasting pipeline

**Time to implement**: 3-4 days (training pipeline) + 2 days (integration) = 1 week to fully operational

---

## Part 1: Current System State

### The Problem: "Ensemble Not Trained"

When you run `multi_horizon_forecast_job.py`:

```python
ensemble = get_production_ensemble()
ensemble_result = ensemble.predict(df)  # ERROR: RuntimeError("Ensemble not trained.")
```

**Root causes**:

1. **No Persistent Model Artifacts** - Trained models aren't serialized to disk/database
2. **No Training Entry Point** - No scheduled job calls `ensemble.train()`
3. **Weight Optimization Missing** - Even if models train individually, ensemble weights aren't optimized
4. **Manual Initialization Only** - Ensemble expects manual `.train()` call but never receives it

### Current Training Fragmentation

Your system has 5 separate training paths (all incomplete):

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| **GA Options Trainer** | `ga_training_job.py` | Optimize options Greeks weights | ✓ Designed |
| **Intraday Calibrator** | `intraday_weight_calibrator.py` | Update M15/H1 model weights | ✗ Not integrated |
| **Symbol Weight Trainer** | `symbol_weight_training_job.py` | Per-symbol weight optimization | ✗ Not integrated |
| **Evaluation Job** | `evaluation_job.py` | Backtest and evaluate | ✗ Produces reports only |
| **Walk-Forward** | `walk_forward_ensemble.py` | Validation framework | ✗ Not connected to production |

**Missing**: Central coordinator that chains these together in proper order.

### Data Flow: Current (Broken)

```
Multi-Horizon Forecast Job (daily 6am UTC)
    ↓
  get_production_ensemble()
    ↓
  Is ensemble trained? NO → RuntimeError
    ↓
  Job exits, no forecasts persisted
```

---

## Part 2: Statistically Sound Training Architecture

### Principles

1. **Temporal Structure** - Always respect time ordering:
   - Train on: Past data (oldest 60-70%)
   - Validate on: Recent unseen data (newest 30-40%)
   - Test on: Live data only (never backtest on this)

2. **No Data Leakage** - Features calculated from:
   - Technical indicators (don't contain future prices)
   - Historical OHLC only
   - Labels from future direction only on holdout set

3. **Multiple Validation Levels**:
   - **In-Sample**: Train accuracy (should be high, 85%+)
   - **Validation Set**: Holdout test accuracy (realistic, 55-65%)
   - **Walk-Forward**: Rolling retraining (production realistic)
   - **Live**: Real-time performance monitoring

4. **Weight Calibration**:
   - Train individual models independently
   - Optimize ensemble weights on validation set using Ridge Regression
   - Weights reflect **out-of-sample** model performance, not in-sample

5. **Retraining Frequency**:
   - Full retrain: Monthly (30 days of new data)
   - Weight-only update: Weekly (validate on last 5 days)
   - Drift detection: Daily (compare live performance vs baseline)

### Target Architecture

```
Monthly Full Retrain (Day 1 of Month)
  ├─ Step 1: Collect Data (60 days)
  ├─ Step 2: Feature Engineering (M15, H1, H4, D1, W1)
  ├─ Step 3: Train Individual Models (RF, GB, ARIMA-GARCH, Prophet, LSTM)
  ├─ Step 4: Validate on Holdout (30% of data, most recent)
  ├─ Step 5: Optimize Ensemble Weights (Ridge + Cross-Val)
  ├─ Step 6: Walk-Forward Test (simulate daily retraining)
  ├─ Step 7: Performance Report (accuracy by timeframe, symbol)
  ├─ Step 8: Serialize Models (save to /models/trained/)
  └─ Step 9: Deploy to Production (load into ensemble)

Weekly Weight Update (Every Monday)
  ├─ Step 1: Collect Last 60 Days
  ├─ Step 2: Re-train Models (fast, 5 min each)
  ├─ Step 3: Re-optimize Weights (fast, 1 min)
  ├─ Step 4: A/B Test (compare vs current weights)
  └─ Step 5: Deploy if Better

Daily Drift Monitoring (Every Morning)
  ├─ Fetch Yesterday's Forecasts
  ├─ Calculate Actual Directions
  ├─ Compare vs Forecast
  ├─ Alert if Accuracy < 45%
  └─ Log Performance Trending
```

---

## Part 3: Detailed Training Pipeline

See `TRAINING_PIPELINE_IMPLEMENTATION.md` for complete Python implementation with:

- **Data Preparation** - Temporal ordering, label creation, no leakage
- **Model Training** - RF + GB trainers with cross-validation
- **Weight Optimization** - Ridge regression for ensemble weights
- **Full Orchestration** - Chains everything together

---

## Part 4: Integration with Production

See `ENSEMBLE_INTEGRATION_GUIDE.md` for:

- Loading trained models from disk
- Modifying forecast jobs to use trained ensemble
- Serialization format and versioning
- Backward compatibility

---

## Part 5: Drift Monitoring

See `DRIFT_MONITORING_SYSTEM.md` for:

- Daily performance tracking
- Drift detection algorithms
- Alert thresholds and escalation
- Performance trending

---

## Part 6-8: Implementation & Decisions

See `TRAINING_IMPLEMENTATION_CHECKLIST.md` for:

- Phase-by-phase implementation plan
- Key decisions you must make
- Expected performance improvements
- Monitoring dashboard setup

---

## Quick Start

1. **Today**: Review this architecture
2. **Tomorrow**: Implement Phase 1 (data preparation)
3. **Day 3**: Implement Phase 2 (model training)
4. **Day 4**: Implement Phase 3 (weight optimization)
5. **Day 5**: Test end-to-end on AAPL/D1
6. **Day 6**: Expand to all symbols/timeframes
7. **Day 7**: Deploy and monitor

See implementation checklist for detailed tasks.

---

## File Structure

```
ml/
├── src/
│   ├── training/                          (NEW DIRECTORY)
│   │   ├── __init__.py
│   │   ├── data_preparation.py            (Phase 1)
│   │   ├── model_training.py              (Phase 2)
│   │   ├── weight_optimizer.py            (Phase 3)
│   │   ├── ensemble_training_job.py       (Phase 3: Orchestration)
│   │   ├── drift_monitor.py               (Phase 4)
│   │   └── README.md
│   │
│   ├── models/
│   │   ├── ensemble_loader.py             (Phase 3: NEW)
│   │   ├── enhanced_ensemble_integration.py (MODIFIED)
│   │   └── ...existing files...
│   │
│   └── multi_horizon_forecast_job.py      (MODIFIED: use trained ensemble)
│
├── trained_models/                        (NEW DIRECTORY)
│   ├── AAPL_d1_20250121.pkl
│   ├── AAPL_h1_20250121.pkl
│   └── ... (versioned by date)
│
└── docs/
    ├── TRAINING_SYSTEM_ARCHITECTURE.md        (This file)
    ├── TRAINING_PIPELINE_IMPLEMENTATION.md    (Part 3)
    ├── ENSEMBLE_INTEGRATION_GUIDE.md          (Part 4)
    ├── DRIFT_MONITORING_SYSTEM.md             (Part 5)
    └── TRAINING_IMPLEMENTATION_CHECKLIST.md   (Part 6-8)
```

---

## Next Steps

1. ✅ Read this document (you are here)
2. → Read `TRAINING_PIPELINE_IMPLEMENTATION.md` (Part 3)
3. → Read `ENSEMBLE_INTEGRATION_GUIDE.md` (Part 4)
4. → Read `DRIFT_MONITORING_SYSTEM.md` (Part 5)
5. → Follow `TRAINING_IMPLEMENTATION_CHECKLIST.md` to implement

**Estimated Time to Operational**: 5-7 days
**Estimated Compute Cost**: ~$5-10/month (monthly retraining + daily monitoring)
