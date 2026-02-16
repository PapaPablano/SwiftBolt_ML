# Multi-Level Forecasting Action Plan

## 🎯 Goal
Implement a hierarchical forecasting strategy that chains 4-bar predictions from lower timeframes (15m) to higher timeframes (1h, 4h, daily), creating a cohesive multi-timeframe prediction system.

## 📊 Current State
- **Level 1**: 15-minute predictions working with daily git testing
- **Foundation**: Multi-timeframe forecaster exists (`multi_timeframe_forecaster.py`)
- **Streamlined**: Clean forecasting pipeline (`streamlined_forecaster.py`)
- **Testing**: Walk-forward validation framework in place

## 🏗️ Architecture Overview

```
Level 1 (15m) → 4-bar prediction
         ↓
    Data aggregation
         ↓
Level 2 (1h) → 4-bar prediction
         ↓
    Data aggregation
         ↓
Level 3 (4h) → 4-bar prediction
         ↓
    Data aggregation
         ↓
Level 4 (Daily) → Weekly trend prediction
```

---

## 📋 Phase 1: 4-Bar Horizon Implementation (15m → 1h)

### Task 1.1: Design 4-Bar Prediction Schema
- [ ] Define prediction output format for 4-bar horizons
- [ ] Document expected return structure with confidence scores
- [ ] Create validation metrics for 4-bar accuracy

**File**: `ml/src/forecast_models/4bar_forecaster.py` (NEW)

```python
# Expected output structure
{
    'symbol': 'AAPL',
    'timestamp': '2026-02-15 10:30:00',
    'horizon': 4,  # bars
    'timeframe': '15m',
    'direction': 'UP',  # or DOWN
    'probability': 0.65,
    'confidence_score': 0.72,
    'support_level': 178.50,
    'resistance_level': 182.30,
    'expected_move_pct': 2.1
}
```

### Task 1.2: Implement Level 1 Forecaster (15m)
- [ ] Create 15-minute data loader with proper bar counting
- [ ] Implement 4-bar prediction logic
- [ ] Add confidence calibration based on regime

**File**: `main_production_system/forecasting_platform/level1_15m_forecaster.py` (NEW)

**Key Functions**:
- `load_15m_data(symbol, lookback_days)`
- `predict_4bar(symbol)`
- `calibrate_confidence(regime, accuracy_history)`

### Task 1.3: Implement Data Aggregation Layer
- [ ] Create function to aggregate 15m → 1h data
- [ ] Preserve price action integrity during resampling
- [ ] Calculate momentum transfer ratios

**File**: `main_production_system/forecasting_platform/aggregation_layer.py` (NEW)

```python
# Key metrics to track
- Volume-weighted average price (VWAP) transfer
- Momentum consistency ratio (4-bar confirmation)
- Volatility transition factor
- Trend persistence score
```

---

## 📋 Phase 2: Level 2 Implementation (1h → 4h)

### Task 2.1: Design Level 2 Architecture
- [ ] Input: 4-bar predictions from Level 1
- [ ] Validation: Check prediction convergence
- [ ] Output: 1h timeframe predictions

**File**: `main_production_system/forecasting_platform/level2_1h_forecaster.py` (NEW)

### Task 2.2: Implement Convergence Validator
- [ ] Compare Level 1 predictions with Level 2 expectations
- [ ] Flag divergent signals for manual review
- [ ] Calculate ensemble weight based on agreement

```python
# Divergence threshold: ±0.15 probability difference
# If Level 1 says UP (0.65) and Level 2 says DOWN (0.55) → flag as UNCERTAIN
```

### Task 2.3: Implement 1h 4-Bar Prediction
- [ ] Use aggregated 15m data as feature set
- [ ] Add time-of-day seasonality
- [ ] Incorporate Level 1 confidence as feature

---

## 📋 Phase 3: Level 3 Implementation (4h → Daily)

### Task 3.1: Design Level 3 Architecture
- [ ] Input: Multi-timeframe consensus
- [ ] Focus: Medium-term trend (4h)
- [ ] Output: Daily forecast with weekly outlook

**File**: `main_production_system/forecasting_platform/level3_4h_forecaster.py` (NEW)

### Task 3.2: Implement Multi-Timeframe Ensemble
- [ ] Combine signals from all levels
- [ ] Timeframe weighting based on market regime
- [ ] Regime-aware confidence adjustment

```python
# Regime-specific weights
TRENDING_UP:    {15m: 0.2, 1h: 0.3, 4h: 0.5}
TRENDING_DOWN:  {15m: 0.2, 1h: 0.3, 4h: 0.5}
RANGING:        {15m: 0.4, 1h: 0.3, 4h: 0.3}
HIGH_VOL:       {15m: 0.5, 1h: 0.3, 4h: 0.2}
```

---

## 📋 Phase 4: Validation & Testing

### Task 4.1: Walk-Forward Validation for 4-Bar
- [ ] Implement rolling window validation
- [ ] Track 4-bar accuracy over time
- [ ] Generate performance reports

**File**: `ml/scripts/test_4bar_horizon.py` (NEW)

```python
# Metrics to track
- 4-bar directional accuracy
- Average confidence score
- Prediction turnaround time
- Error rate by regime
```

### Task 4.2: Hierarchical Consistency Test
- [ ] Verify Level 2 predictions align with Level 1
- [ ] Test aggregation quality metrics
- [ ] Validate multi-level signal convergence

### Task 4.3: Backtest Pipeline
- [ ] Create historical backtest for multi-level system
- [ ] Simulate 4-bar -> 1h -> 4h -> daily trading
- [ ] Calculate Sharpe ratio, max drawdown, win rate

---

## 📋 Phase 5: Production Integration

### Task 5.1: Pipeline Setup
- [ ] Create daily cron job for Level 1 predictions
- [ ] Implement async Level 2/3 processing
- [ ] Set up alert system for high-confidence signals

**File**: `main_production_system/pipelines/multi_level_pipeline.py` (NEW)

### Task 5.2: Dashboard Integration
- [ ] Display multi-level predictions in UI
- [ ] Show confidence hierarchy
- [ ] Add divergence alerts

### Task 5.3: Monitoring & Alerts
- [ ] Track prediction accuracy by level
- [ ] Monitor system health
- [ ] Set up alert rules for low-confidence or divergent signals

---

## 🚀 Quick Start (Immediate Actions)

### Action 1: Create 4-Bar Prediction Module
```bash
# Create the main forecaster module
touch main_production_system/forecasting_platform/4bar_forecaster.py

# Add basic structure
# - Data loading for 15m
# - 4-bar prediction logic
# - Confidence calibration
```

### Action 2: Create Test Script
```bash
# Test 15m 4-bar prediction
touch ml/scripts/test_15m_4bar.py
```

### Action 3: Update Git Workflow
```bash
# Create daily validation workflow
cat > .github/workflows/4bar_validation.yml << 'EOF'
name: 4-Bar Horizon Validation
on:
  schedule:
    - cron: '0 16 * * 1-5'  # Daily at 4 PM ET
EOF
```

---

## 📈 Success Metrics

| Metric | Target | Timeframe |
|--------|--------|-----------|
| 4-bar directional accuracy | >55% | 1 month |
| Level 1 → Level 2 convergence | >70% alignment | 1 month |
| Multi-level confidence score | >65% average | Ongoing |
| Prediction turnaround | <5 minutes | Ongoing |
| Sharpe ratio | >1.0 | 3 months |

---

## 📚 Reference Files to Review

- `main_production_system/forecasting_platform/multi_timeframe_forecaster.py` - Base framework
- `main_production_system/forecasting_platform/streamlined_forecaster.py` - Clean pipeline
- `walkforward_complete_guide.py` - Validation methodology
- `ml/src/models/ensemble_forecaster.py` - Ensemble approach

---

## 🔧 Required Dependencies

```python
# Update requirements.txt
pandas>=2.0.0
numpy>=1.24.0
yfinance>=0.2.0
xgboost>=2.0.0
lightgbm>=4.0.0
scikit-learn>=1.3.0
```

---

## 💡 Key Design Principles

1. **Decoupled Levels**: Each level operates independently but contributes to consensus
2. **Regime-Aware**: Confidence adjusts based on market regime
3. **Conservative Aggregation**: Don't force convergence—flag divergences
4. **Incremental Validation**: Test each level separately before combining
5. **Transparency**: Clear confidence scores at every level

---

## 🎓 Learning Resources

- Multi-timeframe analysis methodology
- Hierarchical forecasting techniques
- Walk-forward validation best practices
- Ensemble prediction weighting strategies