# Phase 7.1 Testing & Production Improvement Plan

**Project:** SwiftBolt ML Stock Forecasting  
**Phase:** 7.1 Ensemble Canary (AAPL/MSFT/SPY)  
**Models:** LSTM + ARIMA-GARCH (2-model ensemble, 29 features, sentiment disabled)  
**Target:** Divergence <10% avg, <15% max  
**Date Created:** February 3, 2026  

---

## Table of Contents

1. [Testing Phase Overview](#testing-phase-overview)
2. [Phase 1: Pre-Deployment Validation](#phase-1-pre-deployment-validation)
3. [Phase 2: Walk-Forward Testing Audit](#phase-2-walk-forward-testing-audit)
4. [Phase 3: Model Performance Testing](#phase-3-model-performance-testing)
5. [Phase 4: Production Readiness](#phase-4-production-readiness)
6. [Phase 5: Post-Deployment Monitoring](#phase-5-post-deployment-monitoring)
7. [Improvement Items](#improvement-items)
8. [Cursor Implementation Guide](#cursor-implementation-guide)

---

## Testing Phase Overview

### Success Criteria

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Test Pass Rate | 100% | 104/104 ✅ | PASS |
| Divergence (Avg) | <10% | 3.66% ✅ | PASS |
| Divergence (Max) | <15% | 4.00% ✅ | PASS |
| Look-Ahead Bias | 0 instances | Unknown ⚠️ | **AUDIT NEEDED** |
| Walk-Forward Windows | Non-overlapping | Unknown ⚠️ | **AUDIT NEEDED** |
| Feature Variance | No NaN leakage | Unknown ⚠️ | **AUDIT NEEDED** |
| Model Correlation | Decorrelated (<0.7) | Unknown ⚠️ | **TEST NEEDED** |

### Testing Timeline

```
Phase 1: Pre-Deployment (Days 1-2)    → Validation tests
Phase 2: Walk-Forward Audit (Days 2-3) → Historical data integrity
Phase 3: Model Performance (Days 3-4)  → Individual model testing
Phase 4: Production Readiness (Day 5)  → Integration testing
Phase 5: Post-Deploy Monitor (Days 6+) → Live divergence tracking
```

---

## Phase 1: Pre-Deployment Validation

**Goal:** Verify all code is free from look-ahead bias and data leakage before canary launch.

### 1.1 Feature Engineering Audit

**File:** `ml/src/unified_forecast_job.py:150-300` (feature computation section)

#### Items to Verify:

- [ ] **Task 1.1.1:** Scan all 29 features for look-ahead bias
  - **Search for:** `[t]`, `[i]`, `current_`, `future_` patterns in feature computation
  - **Expected:** All features use `[t-N]` where N ≥ 1
  - **Critical:** Any feature using `close[t]` or `volume[t]` must be changed to `close[t-1]`
  - **Test:** Run `grep -n "\[t\]" ml/src/unified_forecast_job.py`

- [ ] **Task 1.1.2:** Verify lag enforcement
  - **File:** `ml/src/unified_forecast_job.py` → feature computation functions
  - **Check:** All moving averages, RSI, MACD, etc. use historical data only
  - **Example Fix:**
    ```python
    # BAD
    df['rsi'] = compute_rsi(df['close'])  # Uses current bar
    
    # GOOD
    df['rsi'] = compute_rsi(df['close']).shift(1)  # Uses previous bar
    ```

- [ ] **Task 1.1.3:** Validate timestamp alignment
  - **File:** `ml/src/unified_forecast_job.py:200-250`
  - **Check:** All features are aligned to predict `price[t+1]` using only `data[t-N]`
  - **Test:** Print first 5 rows of feature matrix with target to verify alignment

#### Expected Outcome:
```python
# All features must look like this:
features_t = [
    close_lag1,      # price[t-1]
    volume_lag1,     # volume[t-1]
    rsi_lag1,        # rsi(t-1)
    sma_20_lag1,     # sma_20(t-1)
    # ... all 29 features with explicit lags
]
target_t = close[t+1]  # Predict tomorrow using yesterday's features
```

---

### 1.2 Train/Test Split Validation

**File:** `ml/src/training/walk_forward_optimizer.py:50-150`

#### Items to Verify:

- [ ] **Task 1.2.1:** Verify TimeSeriesSplit usage
  - **File:** `walk_forward_optimizer.py:80-120`
  - **Check:** Cross-validation uses `TimeSeriesSplit`, NOT `KFold` or `StratifiedKFold`
  - **Critical:** Random splits leak future data into training
  - **Test:**
    ```python
    from sklearn.model_selection import TimeSeriesSplit
    # Verify this is imported and used
    ```

- [ ] **Task 1.2.2:** Window overlap check
  - **File:** `walk_forward_optimizer.py:100-150`
  - **Check:** Training windows and test windows DO NOT overlap
  - **Example:**
    ```python
    # BAD (overlapping)
    train: 2020-01-01 to 2023-06-30
    test:  2023-01-01 to 2023-12-31  # June overlap!
    
    # GOOD (non-overlapping)
    train: 2020-01-01 to 2023-06-30
    test:  2023-07-01 to 2023-12-31  # Clean split
    ```
  - **Test:** Print all window start/end dates and verify no overlap

- [ ] **Task 1.2.3:** Holdout set verification
  - **File:** `walk_forward_optimizer.py:60-80`
  - **Check:** Final 10-20% of data is reserved for ultimate validation
  - **Implementation:** Add `HOLDOUT_FRACTION = 0.15` parameter

#### Expected Outcome:
```python
# Walk-forward configuration should look like:
config = {
    'train_window': '2Y',        # 2 years training
    'test_window': '3M',         # 3 months testing
    'step_size': '3M',           # Move forward 3 months each iteration
    'holdout_fraction': 0.15,    # Reserve final 15% untouched
    'cv_method': TimeSeriesSplit # NOT KFold
}
```

---

### 1.3 NaN and Missing Data Audit

**File:** `ml/src/unified_forecast_job.py:300-400` (data preprocessing)

#### Items to Verify:

- [ ] **Task 1.3.1:** Identify NaN handling strategy
  - **File:** `unified_forecast_job.py` → data cleaning section
  - **Check:** How are NaN values imputed? (forward-fill, mean, drop?)
  - **Critical:** Forward-fill can leak future information if not careful
  - **Recommendation:** Use `fillna(method='ffill', limit=5)` with explicit limit

- [ ] **Task 1.3.2:** Feature variance collapse detection
  - **Create:** New test `test_feature_variance_stability.py`
  - **Check:** Do any features have variance → 0 during OOS periods?
  - **Test:**
    ```python
    def test_feature_variance_oos():
        for feature in features:
            train_var = df_train[feature].var()
            test_var = df_test[feature].var()
            assert test_var > 0.1 * train_var, f"{feature} variance collapsed"
    ```

- [ ] **Task 1.3.3:** Distribution shift detection
  - **Create:** Script `scripts/check_feature_distribution_shift.py`
  - **Check:** Are feature distributions similar in train vs test?
  - **Metric:** KL divergence or Kolmogorov-Smirnov test
  - **Action:** Flag features with significant drift (p < 0.05)

#### Expected Outcome:
```
Feature Distribution Report:
- close_lag1: KS statistic = 0.12, p = 0.45 ✅
- volume_lag1: KS statistic = 0.18, p = 0.22 ✅
- rsi_lag1: KS statistic = 0.45, p = 0.001 ⚠️ (INVESTIGATE)
```

---

## Phase 2: Walk-Forward Testing Audit

**Goal:** Ensure walk-forward implementation mimics true forward trading conditions.

### 2.1 Window Configuration Review

**File:** `ml/src/training/walk_forward_optimizer.py`

#### Items to Verify:

- [ ] **Task 2.1.1:** Document current window configuration
  - **Line:** `walk_forward_optimizer.py:70-90`
  - **Extract:** training_window_size, test_window_size, step_size
  - **Compare to best practices:**
    - Training: 2-4 years
    - Testing: 3-6 months
    - Step: 1-3 months

- [ ] **Task 2.1.2:** Verify parameter freezing during OOS
  - **Line:** `walk_forward_optimizer.py:150-200`
  - **Critical Check:** Are model parameters FROZEN during test phase?
  - **Anti-pattern:** Re-optimizing on test data invalidates results
  - **Test:**
    ```python
    # After optimization:
    model_params_before_test = model.get_params()
    # Run test phase
    test_predictions = model.predict(X_test)
    # Verify params unchanged
    assert model.get_params() == model_params_before_test
    ```

- [ ] **Task 2.1.3:** Gap analysis between windows
  - **Check:** Is there a gap between train end and test start?
  - **Recommendation:** 1-day gap to prevent contamination
  - **Example:**
    ```python
    train_end = '2023-06-30'
    test_start = '2023-07-01'  # ✅ 1-day gap
    ```

#### Expected Outcome:
```python
# Walk-forward timeline visualization
Iteration 1: Train[2020-01-01:2022-12-31] → Test[2023-01-01:2023-03-31]
Iteration 2: Train[2020-04-01:2023-03-31] → Test[2023-04-01:2023-06-30]
Iteration 3: Train[2020-07-01:2023-06-30] → Test[2023-07-01:2023-09-30]
# NO OVERLAP, parameters frozen during test
```

---

### 2.2 Historical Data Integrity

**File:** `ml/src/unified_forecast_job.py:100-150` (data loading)

#### Items to Verify:

- [ ] **Task 2.2.1:** Confirm data source timestamps
  - **Check:** Are prices and features timestamped at bar close?
  - **Critical:** Intraday data must use close timestamp, not open
  - **File:** Data ingestion → `backend/supabase/functions/ingest_ohlcv.sql`

- [ ] **Task 2.2.2:** Verify no future data in historical pulls
  - **File:** `unified_forecast_job.py:120`
  - **Check:** When loading historical data for date T, ensure only data < T is included
  - **Test:**
    ```python
    forecast_date = '2023-07-15'
    historical_data = load_data(forecast_date)
    assert historical_data.index.max() < pd.Timestamp(forecast_date)
    ```

- [ ] **Task 2.2.3:** Corporate actions and splits handling
  - **Check:** Are prices adjusted for splits/dividends?
  - **File:** Data ingestion pipeline
  - **Test:** Pull AAPL data around split dates and verify continuity

#### Expected Outcome:
```
Data Integrity Report:
- AAPL: 2520 bars (2020-2023), 0 gaps, adjusted for 4:1 split (2020-08-31) ✅
- MSFT: 2520 bars (2020-2023), 0 gaps, no splits ✅
- SPY: 2520 bars (2020-2023), 0 gaps, no splits ✅
```

---

## Phase 3: Model Performance Testing

**Goal:** Test individual model performance and ensemble behavior.

### 3.1 Individual Model Validation

**Files:**
- `ml/src/models/ensemble_lstm.py`
- `ml/src/models/arima_garch_model.py`

#### Items to Verify:

- [ ] **Task 3.1.1:** LSTM model OOS performance
  - **Test:** Run LSTM standalone on AAPL/MSFT/SPY (1D)
  - **Metrics:** RMSE, MAE, R², Hit Rate (directional accuracy)
  - **File:** Create `tests/test_lstm_standalone.py`
  - **Baseline:** Should achieve R² > 0.1, Hit Rate > 52%

- [ ] **Task 3.1.2:** ARIMA-GARCH model OOS performance
  - **Test:** Run ARIMA-GARCH standalone on AAPL/MSFT/SPY (1D)
  - **Metrics:** RMSE, MAE, R², Hit Rate
  - **File:** Create `tests/test_arima_garch_standalone.py`
  - **Baseline:** Should achieve R² > 0.05, Hit Rate > 50%

- [ ] **Task 3.1.3:** Model error correlation analysis
  - **Test:** Compute correlation between LSTM errors and ARIMA errors
  - **File:** Create `scripts/analyze_model_correlation.py`
  - **Target:** Correlation < 0.7 (ensures diversification)
  - **Formula:**
    ```python
    lstm_errors = y_true - lstm_predictions
    arima_errors = y_true - arima_predictions
    correlation = np.corrcoef(lstm_errors, arima_errors)[0, 1]
    print(f"Error correlation: {correlation:.2f}")
    # Target: < 0.7 for good diversification
    ```

#### Expected Outcome:
```
Model Performance Report (1D Horizon, OOS):

| Model | Symbol | RMSE | MAE | R² | Hit Rate | Correlation |
|-------|--------|------|-----|----|-----------|--------------|
| LSTM | AAPL | 2.45 | 1.89 | 0.18 | 54.2% | - |
| ARIMA | AAPL | 3.12 | 2.34 | 0.09 | 51.8% | 0.62 ✅ |
| LSTM | MSFT | 3.21 | 2.56 | 0.15 | 53.1% | - |
| ARIMA | MSFT | 3.89 | 3.01 | 0.08 | 50.9% | 0.58 ✅ |
| LSTM | SPY | 4.12 | 3.22 | 0.12 | 52.7% | - |
| ARIMA | SPY | 4.98 | 3.87 | 0.06 | 50.4% | 0.65 ✅ |

Average Error Correlation: 0.62 ✅ (Target: <0.7)
```

---

### 3.2 Ensemble Weighting Validation

**File:** `ml/src/forecast_synthesizer.py:200-300`

#### Items to Verify:

- [ ] **Task 3.2.1:** Document current weighting strategy
  - **File:** `forecast_synthesizer.py:250`
  - **Extract:** How are LSTM and ARIMA weights determined?
  - **Options:** Fixed (50/50), adaptive, dynamic per symbol

- [ ] **Task 3.2.2:** Test weighting impact on divergence
  - **Create:** `tests/test_ensemble_weights.py`
  - **Test configurations:**
    - 50/50 (equal weight)
    - 60/40 (LSTM-heavy)
    - 40/60 (ARIMA-heavy)
    - Dynamic (based on recent performance)
  - **Measure:** Which configuration minimizes divergence?

- [ ] **Task 3.2.3:** Validate weight persistence
  - **Check:** Are weights recomputed during OOS testing?
  - **Expected:** Weights should be fixed per walk-forward window
  - **File:** `forecast_synthesizer.py:280-300`

#### Expected Outcome:
```
Ensemble Weighting Analysis:

Configuration: 50% LSTM + 50% ARIMA-GARCH
Divergence (AAPL): 4.00% ✅
Divergence (MSFT): 3.13% ✅
Divergence (SPY): 3.85% ✅
Average: 3.66% ✅ (Target: <10%)

Alternative Tested: 60% LSTM + 40% ARIMA
Average Divergence: 4.12% (Slightly worse)

Recommendation: Keep 50/50 weighting
```

---

### 3.3 Divergence Tracking Implementation

**File:** `ml/src/monitoring/divergence_monitor.py`

#### Items to Verify:

- [ ] **Task 3.3.1:** Verify divergence calculation formula
  - **File:** `divergence_monitor.py:100-150`
  - **Formula:** `divergence = abs(test_rmse - validation_rmse) / validation_rmse * 100`
  - **Check:** Is this computed correctly per symbol, per window?

- [ ] **Task 3.3.2:** Per-model divergence tracking
  - **Feature:** Track divergence for LSTM separately from ARIMA
  - **File:** Extend `divergence_monitor.py` to add `model_name` parameter
  - **Purpose:** Identify which model is causing divergence spikes

- [ ] **Task 3.3.3:** Create divergence alert thresholds
  - **Implement:** Alert system for divergence > 15%
  - **File:** `divergence_monitor.py:200-250`
  - **Actions:**
    - Divergence 10-15%: WARNING (log only)
    - Divergence 15-20%: ALERT (email/Slack)
    - Divergence >20%: CRITICAL (halt forecasts, manual review)

#### Expected Outcome:
```python
# Divergence monitoring output
Divergence Report (2026-02-03):

Symbol: AAPL
  LSTM divergence: 3.2% ✅
  ARIMA divergence: 4.8% ✅
  Ensemble divergence: 4.0% ✅
  Status: PASS

Symbol: MSFT
  LSTM divergence: 2.9% ✅
  ARIMA divergence: 3.4% ✅
  Ensemble divergence: 3.13% ✅
  Status: PASS

Symbol: SPY
  LSTM divergence: 3.6% ✅
  ARIMA divergence: 4.1% ✅
  Ensemble divergence: 3.85% ✅
  Status: PASS

Overall Status: PASS (avg 3.66%, target <10%)
Alerts: 0 ✅
```

---

## Phase 4: Production Readiness

**Goal:** Ensure system is ready for continuous production deployment.

### 4.1 Database Schema Validation

**File:** `backend/supabase/migrations/20260127_ensemble_validation_metrics.sql`

#### Items to Verify:

- [ ] **Task 4.1.1:** Confirm table exists
  - **Table:** `ensemble_validation_metrics`
  - **Test:**
    ```sql
    SELECT COUNT(*) FROM ensemble_validation_metrics;
    -- Should return 0 or more (table exists)
    ```

- [ ] **Task 4.1.2:** Verify all required columns
  - **Expected columns (24 total):**
    - id (uuid, primary key)
    - symbol (text)
    - horizon (text)
    - validation_date (timestamptz)
    - models_used (text[])
    - test_rmse, validation_rmse (numeric)
    - divergence (numeric)
    - overfitting_alert (boolean)
    - ... (see schema file)

- [ ] **Task 4.1.3:** Test insert/query performance
  - **Insert:** 1000 test records
  - **Query:** Retrieve last 7 days of metrics
  - **Benchmark:** Query time < 100ms

#### Expected Outcome:
```sql
-- Sample query should run fast
SELECT symbol, AVG(divergence) as avg_div
FROM ensemble_validation_metrics
WHERE validation_date >= NOW() - INTERVAL '7 days'
GROUP BY symbol;

-- Expected result (< 100ms):
symbol | avg_div
-------+---------
AAPL   | 3.95
MSFT   | 3.12
SPY    | 3.88
```

---

### 4.2 Integration Testing

**File:** `ml/src/unified_forecast_job.py` (end-to-end)

#### Items to Verify:

- [ ] **Task 4.2.1:** Full pipeline test (canary symbols)
  - **Command:**
    ```bash
    python -m ml.src.unified_forecast_job \
      --symbols AAPL,MSFT,SPY \
      --horizon 1D \
      --mode canary
    ```
  - **Expected:** Forecasts generated, metrics logged, no errors

- [ ] **Task 4.2.2:** Database persistence check
  - **After pipeline run, verify:**
    ```sql
    SELECT COUNT(*) FROM ensemble_validation_metrics
    WHERE validation_date >= NOW() - INTERVAL '1 hour';
    -- Should return 3 (one per symbol)
    ```

- [ ] **Task 4.2.3:** Error handling test
  - **Test:** Introduce artificial error (invalid symbol)
  - **Command:**
    ```bash
    python -m ml.src.unified_forecast_job --symbols INVALID --horizon 1D
    ```
  - **Expected:** Graceful error, logged to monitoring, pipeline doesn't crash

#### Expected Outcome:
```
Integration Test Results:
✅ AAPL forecast generated (1D horizon)
✅ MSFT forecast generated (1D horizon)
✅ SPY forecast generated (1D horizon)
✅ Metrics inserted into ensemble_validation_metrics table
✅ Divergence calculated: avg 3.66%
✅ No overfitting alerts
✅ Pipeline completed in 42 seconds
```

---

### 4.3 Rollback Procedure Test

**File:** `scripts/rollback_to_legacy.sh`

#### Items to Verify:

- [ ] **Task 4.3.1:** Test rollback script (dry run)
  - **Command:**
    ```bash
    bash scripts/rollback_to_legacy.sh --dry-run
    ```
  - **Expected:** Shows what would change, doesn't execute

- [ ] **Task 4.3.2:** Verify 4-model ensemble still works
  - **Test:** Run forecast with `ENSEMBLE_MODEL_COUNT=4`
  - **Expected:** No errors, backward compatibility confirmed

- [ ] **Task 4.3.3:** Document rollback triggers
  - **Conditions for rollback:**
    1. Divergence > 15% avg for 3+ consecutive days
    2. Critical errors in production
    3. Database performance degradation
    4. Unexpected model crashes

#### Expected Outcome:
```
Rollback Test:
✅ Dry run shows correct file changes
✅ 4-model ensemble runs successfully (backward compat)
✅ Rollback documentation complete
✅ Emergency contact list prepared
```

---

## Phase 5: Post-Deployment Monitoring

**Goal:** Track canary performance during 7-day validation period.

### 5.1 Daily Monitoring Checklist

**Script:** `scripts/canary_daily_monitoring_supabase.js`

#### Daily Tasks (6:00 PM CST):

- [ ] **Task 5.1.1:** Run monitoring script
  - **Command:**
    ```bash
    cd /Users/ericpeterson/SwiftBolt_ML
    SUPABASE_URL=$SUPABASE_URL \
    SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
    node scripts/canary_daily_monitoring_supabase.js
    ```
  - **Expected:** Report generated in `canary_monitoring_reports/YYYYMMDD_canary_report.md`

- [ ] **Task 5.1.2:** Review divergence metrics
  - **Check:** Average divergence < 10%
  - **Check:** Max divergence < 15%
  - **Check:** No symbol shows divergence > 15% for 2+ consecutive days

- [ ] **Task 5.1.3:** Review RMSE trends
  - **Check:** RMSE not increasing >5% day-over-day
  - **Check:** Test RMSE within ±10% of validation RMSE

- [ ] **Task 5.1.4:** Check for overfitting alerts
  - **Query:**
    ```sql
    SELECT COUNT(*) FROM ensemble_validation_metrics
    WHERE validation_date >= NOW() - INTERVAL '1 day'
      AND overfitting_alert = true;
    ```
  - **Expected:** 0 alerts

- [ ] **Task 5.1.5:** Log daily summary
  - **File:** `canary_monitoring_reports/DAILY_LOG.md`
  - **Record:** Divergence, RMSE, alerts, notes

#### Expected Daily Report:
```markdown
# Canary Daily Report - 2026-02-03

## Summary
- Status: ✅ PASS
- Average Divergence: 3.72%
- Max Divergence: 4.15% (AAPL)
- Overfitting Alerts: 0

## Symbol Performance

### AAPL
- Divergence: 4.15%
- Test RMSE: 2.48
- Validation RMSE: 2.38
- Status: ✅ PASS

### MSFT
- Divergence: 3.21%
- Test RMSE: 3.25
- Validation RMSE: 3.15
- Status: ✅ PASS

### SPY
- Divergence: 3.80%
- Test RMSE: 4.18
- Validation RMSE: 4.03
- Status: ✅ PASS

## Recommendation
Continue monitoring. No action required.
```

---

### 5.2 Weekly Performance Review

**File:** Create `scripts/weekly_performance_summary.py`

#### Items to Implement:

- [ ] **Task 5.2.1:** 7-day performance aggregation
  - **Metrics:**
    - Average divergence per symbol
    - Min/Max divergence per symbol
    - RMSE trend (linear regression slope)
    - Total overfitting alerts
    - Hit rate (directional accuracy)

- [ ] **Task 5.2.2:** Compare to baseline (4-model ensemble)
  - **If baseline data exists:**
    - Compare 2-model RMSE vs 4-model RMSE
    - Compare 2-model divergence vs 4-model divergence
    - Determine if 2-model is improvement

- [ ] **Task 5.2.3:** GO/NO-GO decision framework
  - **GO Criteria (deploy to production):**
    - Avg divergence < 10% all symbols ✅
    - Max divergence < 15% all symbols ✅
    - <3 total overfitting alerts ✅
    - RMSE stable (no >10% degradation) ✅
    - All reports generated successfully ✅
  - **NO-GO Criteria (rollback or extend canary):**
    - Any symbol avg divergence > 15%
    - Persistent overfitting (3+ alerts same symbol)
    - RMSE degradation > 15% from baseline
    - Pipeline failures or data issues

#### Expected 7-Day Summary:
```markdown
# Phase 7.1 Canary - 7-Day Performance Summary
**Period:** Jan 28 - Feb 4, 2026

## Overall Performance
- **Status:** ✅ GO FOR PRODUCTION
- **Avg Divergence:** 3.81% (Target: <10%) ✅
- **Max Divergence:** 4.52% (Target: <15%) ✅
- **Overfitting Alerts:** 0 (Target: <3) ✅
- **RMSE Trend:** Stable (±2% variation) ✅

## Symbol Breakdown

| Symbol | Avg Div | Max Div | Min Div | RMSE Trend | Alerts |
|--------|---------|---------|---------|------------|--------|
| AAPL   | 4.02%   | 4.52%   | 3.45%   | Flat       | 0 ✅   |
| MSFT   | 3.18%   | 3.89%   | 2.78%   | Flat       | 0 ✅   |
| SPY    | 4.23%   | 4.95%   | 3.62%   | -0.5%/day  | 0 ✅   |

## Recommendation
**PROCEED TO PHASE 7.2:** Full production deployment approved.

## Next Steps
1. Deploy 2-model ensemble to all symbols
2. Expand to 5D and 1W horizons
3. Continue daily monitoring for 30 days
4. Set up weekly performance reviews
```

---

## Improvement Items

### Must-Fix (Breaks Canary - Do Before Launch)

#### MF-1: Look-Ahead Bias Audit
**Priority:** P0 (CRITICAL)  
**File:** `ml/src/unified_forecast_job.py:150-300`  
**Issue:** Potential future data leakage in feature computation  
**Test:** Grep for `[t]` patterns in feature code  
**Fix:** Change all current-bar references to `[t-1]`  
**Validation:** Run `tests/test_look_ahead_bias.py` (create if missing)  
**Est. Time:** 2-3 hours  

##### MF-1 Reference: Feature Pipeline Inventory
The full inference/training path is now documented so we can reason about every place where future data could sneak in:

1. `UnifiedForecastProcessor.process_symbol` pulls fresh OHLC frames via `fetch_or_build_features` (`ml/src/features/feature_cache.py`). When a `cutoff_ts` is supplied the cache is bypassed and `db.fetch_ohlc_bars` truncates any rows with `ts ≥ cutoff`, so only pre-cut data reaches the builders.  
2. The processor selects the `d1` frame, then `BaselineForecaster.prepare_training_data` (`ml/src/models/baseline_forecaster.py`) calls `compute_simplified_features` (`ml/src/features/temporal_indicators.py`). This helper first computes deterministic indicators (no shifts into the future), inserts sentiment (aligned on normalized dates), attaches the fixed lag set, and finally injects default regime columns so slicing never fails.  
3. `TemporalFeatureEngineer.add_features_to_point` consumes those precomputed columns row-by-row—if any feature is missing, it recomputes it by iterating only over indices `≤ idx`, which guarantees there is no access to `idx+1`. The training loop also enforces `start_idx = 50` and `end_idx = len(df) - horizon_days` so the last `horizon_days` rows are never labeled with information from the future window.

###### Simplified Feature Matrix (Base + Derived Inputs)
| Category | Feature(s) | Source (Function/File) | Lookback / Lag Window | Notes on Bias Protection |
| --- | --- | --- | --- | --- |
| Price & Volume | `close`, `volume`, `volume_ratio` | Raw OHLC + `volume / SMA20(volume)` in `TechnicalIndicatorsCorrect.add_all_technical_features_correct` | Instantaneous, 20-bar SMA | Uses only historical bars; ratio divides current volume by trailing 20-bar mean. |
| MACD Family | `macd`, `macd_hist`, `macd_signal` | `calculate_macd` in `technical_indicators_corrected.py` | EMA12/EMA26/Signal9 | Implemented with EMA recursion over `[:idx+1]`; no forward referencing. |
| Oscillators & Bands | `rsi_14`, `bb_lower`, `bb_upper`, `bb_width_pct` | `calculate_rsi` / Bollinger helpers in `technical_indicators_corrected.py` | RSI14, Bollinger20 | Rolling windows are capped at `idx`; rows with insufficient history return `NaN`. |
| Trend Strength & Momentum | `adx`, `supertrend_trend`, `roc_5d`, `roc_20d` | `calculate_adx_correct`, `TemporalFeatureEngineer.compute_supertrend_features`, direct `pct_change` | ADX14, ATR-based ST (10), ROC5/20 | SuperTrend fallback recomputes value using slices ending at `idx`; ROC uses `pct_change(n)` which only references backward rows. |
| Volatility (Stock-specific) | `atr_14`, `vix_proxy_atr`, `historical_volatility_20d/60d`, `atr_normalized`, `bb_width`, `volatility_regime/percentile/change` | `add_volatility_features` | ATR14, Rolling20/60/252 | All derived from past ATR/returns windows; percentile uses rolling apply up to current index. |
| Custom Lag Stack | `supertrend_trend_lag{1,7,14,30}`, `kdj_divergence_lag{1,7,14,30}`, `macd_hist_lag{1,7,14,30}`, `sentiment_score_lag{1,7}` | `create_lag_features` | Explicit positive lags only | Shifts use `.shift(k)` with `k ≥ 1`, so row `t` never sees `t+1`. |
| Sentiment Injection | `sentiment_score` | `compute_simplified_features` | Daily alignment (no lag) | Series is merged on normalized date index; missing values default to `0` before lagging. |
| Regime Context | `spy_above_200ma`, `spy_trend_strength`, `spy_trend_regime`, `vix`, `vix_regime`, `vix_percentile`, `beta_to_spy`, `sector_relative_strength`, etc. | `add_simple_regime_defaults` + `add_regime_defaults` | Precomputed higher-level regimes (≥1-day lag) | Defaults ensure deterministic values when external feeds are disabled; no forward data pulled inside this job. |

> The table mirrors the 29 base indicators referenced in `SIMPLIFIED_FEATURES` plus the deterministic lag scaffolding. Every entry now has an explicit provenance + window so audits can trace potential leakage quickly.

**Action:** Continue with runtime guardrails and automated tests once this inventory is verified during MF-1 triage.

**New validation commands:**
- `STRICT_LOOKAHEAD_CHECK=1 python ml/src/unified_forecast_job.py --symbol AAPL --horizons 1D` (runtime guard recomputes features and raises on truncation drift).
- `pytest tests/test_look_ahead_bias.py` (synthetic guard + per-horizon sampling + ForecastSynthesizer input validation).

#### MF-2: TimeSeriesSplit Enforcement
**Priority:** P0 (CRITICAL)  
**File:** `ml/src/training/walk_forward_optimizer.py:80-120`  
**Issue:** May be using wrong cross-validation method  
**Test:** Search for `KFold` or `StratifiedKFold` imports  
**Fix:** Replace with `TimeSeriesSplit`  
**Validation:** Print CV fold dates and verify no overlap  
**Est. Time:** 1-2 hours  

#### MF-3: Window Overlap Verification
**Priority:** P0 (CRITICAL)  
**File:** `ml/src/training/walk_forward_optimizer.py:100-150`  
**Issue:** Training and test windows may overlap  
**Test:** Print all window boundaries  
**Fix:** Add gap enforcement logic  
**Validation:** Visual timeline of all windows  
**Est. Time:** 2-3 hours  

#### MF-4: Parameter Freezing During OOS
**Priority:** P0 (CRITICAL)  
**File:** `ml/src/training/walk_forward_optimizer.py:150-200`  
**Issue:** Model params may be updated during test phase  
**Test:** Capture params before/after OOS testing  
**Fix:** Add `freeze_params=True` flag  
**Validation:** Assert params unchanged after test  
**Est. Time:** 1-2 hours  

---

### Should-Fix (Important for Canary Success)

#### SF-1: Feature Variance Monitoring
**Priority:** P1  
**File:** Create `tests/test_feature_variance_stability.py`  
**Issue:** Features may collapse during OOS periods  
**Implementation:**
```python
def test_feature_variance():
    for feature in all_features:
        train_var = train_data[feature].var()
        test_var = test_data[feature].var()
        # Variance shouldn't drop below 10% of training variance
        assert test_var > 0.1 * train_var
```
**Est. Time:** 2 hours  

#### SF-2: Model Error Correlation Analysis
**Priority:** P1  
**File:** Create `scripts/analyze_model_correlation.py`  
**Issue:** Need to verify LSTM and ARIMA errors are decorrelated  
**Implementation:**
```python
lstm_errors = y_true - lstm_pred
arima_errors = y_true - arima_pred
corr = np.corrcoef(lstm_errors, arima_errors)[0, 1]
print(f"Error correlation: {corr:.2f}")
assert corr < 0.7, "Models too correlated"
```
**Target:** Correlation < 0.7  
**Est. Time:** 2 hours  

#### SF-3: Per-Model Divergence Tracking
**Priority:** P1  
**File:** `ml/src/monitoring/divergence_monitor.py:100-150`  
**Issue:** Currently only tracking ensemble divergence  
**Enhancement:** Track LSTM divergence and ARIMA divergence separately  
**Purpose:** Identify which model causes divergence spikes  
**Implementation:** Add `model_name` column to `ensemble_validation_metrics`  
**Est. Time:** 3 hours  

#### SF-4: Distribution Shift Detection
**Priority:** P1  
**File:** Create `scripts/check_feature_distribution_shift.py`  
**Issue:** Feature distributions may differ in train vs test  
**Test:** Kolmogorov-Smirnov test for each feature  
**Alert:** Flag features with p < 0.05  
**Est. Time:** 2-3 hours  

#### SF-5: NaN Handling Documentation
**Priority:** P1  
**File:** `ml/src/unified_forecast_job.py:300-400`  
**Issue:** NaN imputation strategy unclear  
**Action:** Document current method (forward-fill? mean? drop?)  
**Recommendation:** Use `fillna(method='ffill', limit=5)` with limit  
**Validation:** Count NaN before/after imputation  
**Est. Time:** 1-2 hours  

---

### Nice-to-Have (Improvements for Phase 7.2+)

#### NH-1: Prediction Interval Calibration
**Priority:** P2  
**File:** Create `ml/src/models/conformal_prediction.py`  
**Feature:** Add confidence intervals to forecasts using conformal prediction  
**Benefit:** Better uncertainty quantification  
**Est. Time:** 1 day  

#### NH-2: Monte Carlo Bootstrap of OOS Trades
**Priority:** P2  
**File:** Create `scripts/bootstrap_oos_performance.py`  
**Feature:** Resample OOS trades 1000x to estimate metric variance  
**Benefit:** Statistical significance of performance claims  
**Est. Time:** 4 hours  

#### NH-3: Feature Importance Analysis
**Priority:** P2  
**File:** Create `scripts/analyze_feature_importance.py`  
**Feature:** SHAP or permutation importance for 29 features  
**Benefit:** Identify low-value features for removal  
**Est. Time:** 4 hours  

#### NH-4: Regime Detection
**Priority:** P2  
**File:** Create `ml/src/models/regime_detector.py`  
**Feature:** Detect market regimes (bull/bear/sideways) and switch models  
**Benefit:** Adaptive models per regime  
**Est. Time:** 2 days  

#### NH-5: Automated Alert System
**Priority:** P2  
**File:** Extend `ml/src/monitoring/divergence_monitor.py`  
**Feature:** Email/Slack alerts when divergence > 15%  
**Benefit:** Faster response to issues  
**Est. Time:** 3 hours  

---

## Cursor Implementation Guide

### How to Use This Document with Cursor AI

This section provides specific prompts to give Cursor for each phase.

---

### Phase 1: Feature Engineering Audit

**Cursor Prompt for Task 1.1.1:**
```
**Goal:** Audit ml/src/unified_forecast_job.py for look-ahead bias in feature computation

**Files:** ml/src/unified_forecast_job.py:150-300

**Concerns:**
1. Are any features computed using current bar data (e.g., close[t], volume[t])?
2. Do all features use explicit lags (e.g., close[t-1], rsi[t-1])?
3. Are there any 'future_' or 'current_' variable names that suggest look-ahead?

**Provide:**
- List of all features computed (line numbers)
- Identify any features that may use current/future data (MUST-FIX)
- Suggest fixes: change to [t-1] or add .shift(1)
- Show example before/after code

**Patterns to follow:**
- All features must use historical data only (t-1 or earlier)
- No feature should reference data from the prediction target bar
- Use pandas .shift(1) to enforce lags explicitly

**Don't:**
- Don't change file structure or add new features
- Don't modify working code unnecessarily
- Focus only on look-ahead bias issues
```

---

**Cursor Prompt for Task 1.2.1:**
```
**Goal:** Verify ml/src/training/walk_forward_optimizer.py uses TimeSeriesSplit

**Files:** ml/src/training/walk_forward_optimizer.py:80-120

**Concerns:**
1. Is cross-validation using TimeSeriesSplit (correct) or KFold/StratifiedKFold (incorrect)?
2. Are CV folds respecting temporal order?
3. Could future data leak into training folds?

**Provide:**
- Identify current CV method (line number)
- If not TimeSeriesSplit: provide fix with code example
- Show how to print fold dates to verify no overlap
- Validate fold boundaries are sequential

**Patterns to follow:**
- MUST use sklearn.model_selection.TimeSeriesSplit
- Folds must be non-overlapping and sequential
- Training data always comes before test data

**Don't:**
- Don't change hyperparameters or model logic
- Don't modify working validation metrics
- Focus only on CV method correctness
```

---

**Cursor Prompt for Task 1.3.1:**
```
**Goal:** Document and validate NaN handling strategy in data preprocessing

**Files:** ml/src/unified_forecast_job.py:300-400

**Concerns:**
1. How are NaN values currently imputed? (forward-fill? mean? drop?)
2. Could forward-fill leak future information?
3. Are there limits on forward-fill propagation?

**Provide:**
- Identify all NaN handling code (line numbers)
- Document current strategy
- Check if fillna uses 'ffill' without limit (risky)
- Suggest fix: add limit parameter (e.g., limit=5)
- Show before/after code

**Patterns to follow:**
- Use fillna(method='ffill', limit=5) to prevent long-range propagation
- Document rationale for chosen imputation method
- Count NaN before/after to verify effectiveness

**Don't:**
- Don't change imputation method without justification
- Don't introduce new dependencies
- Keep changes minimal and documented
```

---

### Phase 2: Walk-Forward Testing Audit

**Cursor Prompt for Task 2.1.2:**
```
**Goal:** Verify model parameters are frozen during out-of-sample testing

**Files:** ml/src/training/walk_forward_optimizer.py:150-200

**Concerns:**
1. Are model parameters optimized during training phase?
2. Are those same parameters frozen (not re-optimized) during test phase?
3. Is there any code that updates params during OOS evaluation?

**Provide:**
- Identify where model.fit() is called (training phase)
- Identify where model.predict() is called (test phase)
- Check if any parameter updates happen between fit and predict
- Add assertion: params before test == params after test
- Show example test code to validate freezing

**Patterns to follow:**
- Training: model.fit(X_train, y_train)
- FREEZE PARAMS (no more updates)
- Testing: predictions = model.predict(X_test)
- Validate: assert model.get_params() unchanged

**Don't:**
- Don't change optimization logic unnecessarily
- Don't add re-optimization during test
- Focus only on parameter freezing validation
```

---

**Cursor Prompt for Task 2.2.2:**
```
**Goal:** Verify historical data loading doesn't include future data

**Files:** ml/src/unified_forecast_job.py:100-150

**Concerns:**
1. When loading data for forecast date T, is only data < T included?
2. Are there any off-by-one errors (loading data <= T instead of < T)?
3. Could bar timestamps cause issues (open vs close timestamp)?

**Provide:**
- Identify data loading function (line number)
- Show how forecast_date is used to filter historical data
- Check for <= vs < comparison (must be <)
- Add test: assert historical_data.index.max() < forecast_date
- Show example validation code

**Patterns to follow:**
- historical_data = data[data.index < forecast_date]  # NOT <=
- Always use strict < to prevent current bar inclusion
- Validate with assertion in test suite

**Don't:**
- Don't change data loading logic without validation
- Don't introduce timezone issues
- Keep timestamp handling consistent
```

---

### Phase 3: Model Performance Testing

**Cursor Prompt for Task 3.1.3:**
```
**Goal:** Analyze error correlation between LSTM and ARIMA-GARCH models

**Files:** Create new script scripts/analyze_model_correlation.py

**Concerns:**
1. Are LSTM errors and ARIMA errors highly correlated (>0.7)?
2. If correlation is high, ensemble diversification is weak
3. Need per-symbol correlation analysis

**Provide:**
- Script to compute error correlation for AAPL, MSFT, SPY
- Load historical predictions from both models
- Calculate: correlation = np.corrcoef(lstm_errors, arima_errors)[0, 1]
- Target: correlation < 0.7 for good diversification
- Output: table with symbol, LSTM RMSE, ARIMA RMSE, correlation
- Interpretation: if corr > 0.7, models are too similar

**Patterns to follow:**
- errors = y_true - y_pred
- correlation = np.corrcoef(errors_model1, errors_model2)[0,1]
- Report per symbol and aggregate

**Don't:**
- Don't modify model code
- Don't change ensemble weights yet
- Focus only on correlation analysis
```

---

**Cursor Prompt for Task 3.2.2:**
```
**Goal:** Test impact of different ensemble weighting configurations on divergence

**Files:** ml/src/forecast_synthesizer.py:200-300, create tests/test_ensemble_weights.py

**Concerns:**
1. Is 50/50 weighting optimal for minimizing divergence?
2. Would 60/40 or 40/60 perform better?
3. Should weights be adaptive per symbol?

**Provide:**
- Test configurations:
  - Config A: 50% LSTM + 50% ARIMA (current)
  - Config B: 60% LSTM + 40% ARIMA
  - Config C: 40% LSTM + 60% ARIMA
- Measure divergence for each config on AAPL, MSFT, SPY
- Output: table with config, avg divergence, max divergence
- Recommendation: which config minimizes divergence?

**Patterns to follow:**
- ensemble_pred = w1 * lstm_pred + w2 * arima_pred
- Measure divergence per config
- Choose config with lowest avg divergence

**Don't:**
- Don't change production weights yet
- Don't introduce dynamic weighting without testing
- Focus on empirical comparison
```

---

**Cursor Prompt for Task 3.3.2:**
```
**Goal:** Extend divergence monitoring to track per-model divergence

**Files:** ml/src/monitoring/divergence_monitor.py:100-150

**Concerns:**
1. Currently only tracking ensemble divergence
2. Need to know if LSTM or ARIMA is causing spikes
3. Requires tracking divergence for each model separately

**Provide:**
- Add model_name parameter to divergence calculation
- Compute divergence for:
  - LSTM only
  - ARIMA only
  - Ensemble (weighted average)
- Store all three in ensemble_validation_metrics table
- Add columns: lstm_divergence, arima_divergence, ensemble_divergence
- Show updated database schema

**Patterns to follow:**
- For each model: divergence = |test_rmse - val_rmse| / val_rmse * 100
- Track separately to identify problem models
- Ensemble divergence is weighted average

**Don't:**
- Don't change divergence formula
- Don't break existing monitoring
- Extend, don't replace
```

---

### Phase 4: Production Readiness

**Cursor Prompt for Task 4.2.1:**
```
**Goal:** Run full end-to-end pipeline test for canary symbols

**Files:** ml/src/unified_forecast_job.py

**Concerns:**
1. Does pipeline run without errors for AAPL, MSFT, SPY?
2. Are forecasts generated and metrics logged?
3. Is data persisted to database correctly?

**Provide:**
- Command to run: python -m ml.src.unified_forecast_job --symbols AAPL,MSFT,SPY --horizon 1D --mode canary
- Expected output: forecasts for all 3 symbols
- Validation queries:
  - Check forecasts table for new entries
  - Check ensemble_validation_metrics for metrics
- Error handling: what happens if one symbol fails?
- Show example successful run output

**Patterns to follow:**
- Run pipeline end-to-end
- Validate database persistence
- Check for errors in logs
- Confirm metrics within expected ranges

**Don't:**
- Don't run on production data yet
- Don't modify pipeline during test
- Focus on validation only
```

---

**Cursor Prompt for Task 4.3.1:**
```
**Goal:** Test rollback script to revert to 4-model ensemble if needed

**Files:** scripts/rollback_to_legacy.sh

**Concerns:**
1. Does rollback script work correctly?
2. Can we revert to 4-model ensemble without data loss?
3. Is backward compatibility maintained?

**Provide:**
- Run: bash scripts/rollback_to_legacy.sh --dry-run
- Show what would change (file diffs)
- Verify 4-model ensemble still runs: ENSEMBLE_MODEL_COUNT=4 python -m ml.src.unified_forecast_job --symbols AAPL --horizon 1D
- Document rollback triggers:
  - Divergence > 15% for 3+ days
  - Critical errors
  - Database performance issues
- Validate rollback doesn't break monitoring

**Patterns to follow:**
- Always test rollback before deploying
- Dry run first, actual rollback only if needed
- Document triggers and process

**Don't:**
- Don't actually rollback during test
- Don't remove 4-model code
- Keep backward compatibility
```

---

### Phase 5: Monitoring Setup

**Cursor Prompt for Task 5.1.1:**
```
**Goal:** Set up automated daily monitoring report generation

**Files:** scripts/canary_daily_monitoring_supabase.js

**Concerns:**
1. Does monitoring script run successfully?
2. Are reports generated in correct format?
3. Are metrics pulled from database correctly?

**Provide:**
- Command to run daily: node scripts/canary_daily_monitoring_supabase.js
- Expected output: canary_monitoring_reports/YYYYMMDD_canary_report.md
- Report should include:
  - Overall status (PASS/FAIL)
  - Per-symbol divergence
  - RMSE values
  - Overfitting alerts
  - Recommendation
- Show example report
- Set up 6 PM CST cron job (optional)

**Patterns to follow:**
- Pull latest metrics from ensemble_validation_metrics
- Calculate daily averages
- Compare to thresholds (10%, 15%)
- Generate markdown report

**Don't:**
- Don't modify database schema during monitoring
- Don't change threshold values without justification
- Keep report format consistent
```

---

**Cursor Prompt for Task 5.2.3:**
```
**Goal:** Implement GO/NO-GO decision framework after 7-day canary

**Files:** Create scripts/weekly_performance_summary.py

**Concerns:**
1. What are objective criteria for deploying to production?
2. When should we rollback or extend canary?
3. How to aggregate 7 days of metrics?

**Provide:**
- Script to aggregate 7 days of canary metrics
- GO criteria (all must pass):
  - Avg divergence < 10% ✅
  - Max divergence < 15% ✅
  - <3 overfitting alerts ✅
  - RMSE stable (±10%) ✅
  - All reports generated ✅
- NO-GO criteria (any fails → rollback):
  - Avg divergence > 15%
  - Persistent overfitting (3+ alerts same symbol)
  - RMSE degradation > 15%
  - Pipeline failures
- Output: recommendation with justification

**Patterns to follow:**
- Aggregate metrics across 7 days
- Apply decision criteria objectively
- Provide clear recommendation
- Document rationale

**Don't:**
- Don't make subjective decisions
- Don't ignore threshold violations
- Follow framework strictly
```

---

## Quick Reference: Priority Order

### Week 1 (Before Canary Launch)

**Day 1-2:**
1. ✅ MF-1: Look-ahead bias audit (unified_forecast_job.py)
2. ✅ MF-2: TimeSeriesSplit enforcement (walk_forward_optimizer.py)
3. ✅ MF-3: Window overlap verification (walk_forward_optimizer.py)
4. ✅ MF-4: Parameter freezing validation (walk_forward_optimizer.py)

**Day 3:**
5. ✅ SF-1: Feature variance monitoring (test_feature_variance_stability.py)
6. ✅ SF-2: Model error correlation analysis (analyze_model_correlation.py)
7. ✅ SF-5: NaN handling documentation (unified_forecast_job.py)

**Day 4:**
8. ✅ SF-3: Per-model divergence tracking (divergence_monitor.py)
9. ✅ SF-4: Distribution shift detection (check_feature_distribution_shift.py)
10. ✅ Task 4.1: Database schema validation

**Day 5:**
11. ✅ Task 4.2: Integration testing (full pipeline)
12. ✅ Task 4.3: Rollback procedure test
13. ✅ Task 5.1: Daily monitoring setup

**Day 6-7:**
14. ✅ Run Phase 1 validation tests (all 104 tests)
15. ✅ Document findings and prepare canary launch
16. ✅ Final review meeting

### Week 2 (Canary Period - Days 1-7)

**Daily (6:00 PM CST):**
- Run monitoring script
- Review divergence metrics
- Check for alerts
- Log daily summary

**Day 7 (End of Canary):**
- Run weekly performance summary
- Apply GO/NO-GO decision framework
- Prepare Phase 7.2 deployment OR rollback plan

---

## File Reference

### Files to Audit:
```
ml/src/unified_forecast_job.py
├── Lines 100-150: Data loading
├── Lines 150-300: Feature computation ⚠️ CRITICAL
├── Lines 300-400: Data preprocessing (NaN handling)
└── Lines 400+: Model training and forecasting

ml/src/training/walk_forward_optimizer.py
├── Lines 50-80: Window configuration
├── Lines 80-120: Cross-validation setup ⚠️ CRITICAL
├── Lines 100-150: Window overlap logic ⚠️ CRITICAL
└── Lines 150-200: Parameter freezing ⚠️ CRITICAL

ml/src/monitoring/divergence_monitor.py
├── Lines 100-150: Divergence calculation
└── Lines 200-250: Alert thresholds

ml/src/forecast_synthesizer.py
└── Lines 200-300: Ensemble weighting
```

### Files to Create:
```
tests/
├── test_look_ahead_bias.py           (MF-1)
├── test_feature_variance_stability.py (SF-1)
└── test_ensemble_weights.py           (SF-2)

scripts/
├── analyze_model_correlation.py       (SF-2)
├── check_feature_distribution_shift.py (SF-4)
└── weekly_performance_summary.py      (Task 5.2.3)
```

### Configuration Files:
```
ml/.env.canary
├── ENSEMBLE_MODEL_COUNT=2
├── ENABLE_LSTM=true
├── ENABLE_ARIMA_GARCH=true
├── ENABLE_GB=false
└── CANARY_SYMBOLS=AAPL,MSFT,SPY
```

---

## Contact & Escalation

### Daily Check-ins:
- **Time:** 6:00 PM CST
- **Action:** Run monitoring script and review report

### Escalation Triggers:
- Divergence > 15% on any symbol
- 2+ overfitting alerts in one day
- Pipeline errors or failures
- Database performance issues

### Emergency Rollback:
```bash
bash scripts/rollback_to_legacy.sh
# Reverts to 4-model ensemble
# Takes ~5 minutes
# No data loss
```

---

## Success Metrics

### Phase 7.1 Canary Success = ALL of:
- ✅ Avg divergence < 10% across all symbols and days
- ✅ Max divergence < 15% across all symbols and days
- ✅ <3 total overfitting alerts in 7 days
- ✅ RMSE stable (±10% from baseline)
- ✅ All 7 daily reports generated successfully
- ✅ Zero critical errors

### If Successful → Phase 7.2:
- Deploy 2-model ensemble to all symbols
- Expand to 5D and 1W horizons
- Continue monitoring for 30 days
- Reduce monitoring intensity to weekly

### If Not Successful:
- Analyze root cause
- Rollback to 4-model ensemble OR
- Extend canary with modifications OR
- Hybrid approach (2-model for stable symbols only)

---

## Appendix: Key Research References

1. **Walk-Forward Analysis:** Prevents overfitting by testing on unseen future data [web:3][web:6][web:9]
2. **TimeSeriesSplit:** Respects temporal order, prevents data leakage [web:4]
3. **Ensemble Diversification:** Low error correlation improves ensemble [web:7][web:10]
4. **Divergence Monitoring:** Tracks train/test performance gap [web:50]
5. **Feature Engineering:** Explicit lags prevent look-ahead bias [web:6]

---

**Document Version:** 1.0  
**Last Updated:** February 3, 2026  
**Status:** Ready for Implementation  
**Next Review:** After Phase 7.1 Canary (Feb 11, 2026)  
