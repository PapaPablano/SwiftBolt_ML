# Walk-Forward Validation Audit: System-Specific Verification Framework
**Prepared**: January 24, 2026  
**For**: SwiftBolt ML Platform  
**Based on**: ML_AND_FORECASTING_FLOWCHART.md architecture + Generic Audit Framework

---

## Overview

This document provides **system-specific verification steps** for the 7 data leakage risks in your SwiftBolt ML platform. Each section maps risks to:
- Actual files in your codebase
- Concrete grep/SQL verification patterns
- Expected findings for a safe implementation

---

## RISK #1: Training Data Cutoff (HIGH PRIORITY)

### System Context
- **Daily Data Refresh** (02:00 UTC): Loads d1, w1 into `ohlc_bars_v2`
- **ML Orchestration** (04:00 UTC): `ml-forecast` job via `forecast_job.py`
- **Reads from**: `ohlc_bars_v2` table
- **Vulnerability**: If training includes forecast horizon data → predictions contaminated

### File to Check
```
ml/src/scripts/forecast_job.py
```

### Verification Steps

#### Step 1: Find data loading section
```bash
cd /Users/ericpeterson/SwiftBolt_ML
grep -n "SELECT.*ohlc" ml/src/scripts/forecast_job.py
grep -n "pd.read_sql" ml/src/scripts/forecast_job.py
grep -n "WHERE timestamp" ml/src/scripts/forecast_job.py
```

**Expected Output**: Should see WHERE clause with timestamp filter

#### Step 2: Verify cutoff logic
```bash
grep -n "CURRENT" ml/src/scripts/forecast_job.py
grep -n "timedelta" ml/src/scripts/forecast_job.py
grep -n "days=1" ml/src/scripts/forecast_job.py
grep -n "datetime.utcnow()" ml/src/scripts/forecast_job.py
```

**Expected Output**: Should see `- timedelta(days=1)` somewhere

#### Step 3: Check for SAFE pattern
Look for code like:
```python
# SAFE - Explicitly excludes today's data
data_cutoff = datetime.utcnow() - timedelta(days=1)
query = """
    SELECT * FROM ohlc_bars_v2 
    WHERE timestamp < %s
    AND timeframe IN ('d1', 'w1')
    ORDER BY symbol_id, timestamp
"""
training_data = pd.read_sql(query, conn, params=[data_cutoff])
```

#### Step 4: Red Flags - Search for these patterns
```bash
# No filter at all?
grep -n "SELECT \* FROM ohlc_bars_v2" ml/src/scripts/forecast_job.py | grep -v "WHERE"

# No -1 day subtraction?
grep "CURRENT_TIMESTAMP" ml/src/scripts/forecast_job.py | grep -v "timedelta"

# Explicit admission of including today's data?
grep -n "train on all\|include.*today\|include.*current" ml/src/scripts/forecast_job.py
```

**Red Flag Examples** (if you see these, STOP and fix):
- `SELECT * FROM ohlc_bars_v2` (no WHERE clause)
- `WHERE timestamp <= today()` (includes today!)
- `WHERE timestamp < CURRENT_TIMESTAMP` (no -1 day)
- `data_cutoff = datetime.utcnow()` (missing timedelta)

#### Step 5: Verify timeframe filtering
```bash
grep -n "timeframe" ml/src/scripts/forecast_job.py | head -10
```

**Expected**: Should see `timeframe IN ('d1', 'w1')` or similar
**Red Flag**: If you see `m15`, `h1` in the WHERE clause for daily forecast

### Database Verification
```sql
-- In Supabase SQL editor, run:
-- Check most recent training cutoff
SELECT 
    forecast_id,
    forecast_generated_at,
    MIN(training_data_ts) as oldest_training_bar,
    MAX(training_data_ts) as newest_training_bar,
    (MAX(training_data_ts) < forecast_generated_at::date) as safe
FROM ml_forecasts
WHERE forecast_generated_at > NOW() - INTERVAL '7 days'
GROUP BY forecast_id, forecast_generated_at
ORDER BY forecast_generated_at DESC
LIMIT 5;

-- If safe = true for all rows → SAFE ✅
-- If any safe = false → LEAKAGE RISK ❌
```

### Checklist
- [ ] Open `ml/src/scripts/forecast_job.py`
- [ ] Find the training data loading query
- [ ] Confirm: `WHERE timestamp < CUTOFF_DATE`
- [ ] NOT: `WHERE timestamp <= TODAY`
- [ ] Cutoff is 1+ days before forecast date
- [ ] Timeframe filtered to `d1`, `w1` only (no intraday)
- [ ] Database query confirms latest training data is from yesterday

---

## RISK #2: Model Weight Update Timing (HIGH PRIORITY)

### System Context
- **ML Orchestration**: `.github/workflows/ml-orchestration.yml`
- **3 jobs**: `ml-forecast`, `options-processing`, `model-health`
- **model-health** contains: `evaluation_job.py` → `populate_live_predictions.py` → `trigger_weight_update()` RPC
- **Next cycle uses updated weights** (1-day lag = correct)
- **Vulnerability**: If weights updated and used in same cycle → look-ahead bias

### Files to Check
```
.github/workflows/ml-orchestration.yml
ml/src/scripts/forecast_job.py
ml/src/scripts/evaluation_job.py
ml/src/scripts/populate_live_predictions.py
```

### Verification Steps

#### Step 1: Check workflow job order
```bash
grep -n "jobs:\|needs:\|- name:" .github/workflows/ml-orchestration.yml | head -30
```

**Expected Output**: Should show `ml-forecast` first, then `model-health` with `needs: ml-forecast`

#### Step 2: Visualize workflow structure
```bash
# Get the complete job dependency tree
grep -A2 "^  [a-z].*:" .github/workflows/ml-orchestration.yml | grep -E "^  [a-z]|needs:"
```

**Expected Structure**:
```yaml
ml-forecast:
  runs-on: ubuntu-latest
  # NO dependencies
  
model-health:
  needs: ml-forecast  # ← Depends on ml-forecast
  runs-on: ubuntu-latest
```

**Red Flag Structure**:
```yaml
model-health:
  # No 'needs', runs independently
  
ml-forecast:
  needs: model-health  # ← BACKWARDS!
```

#### Step 3: Find weight update RPC call
```bash
grep -n "trigger_weight_update\|model_weights" .github/workflows/ml-orchestration.yml
```

#### Step 4: Check if weights loaded in forecast_job.py
```bash
grep -n "load.*weight\|model_weights\|SELECT.*weight" ml/src/scripts/forecast_job.py
```

**Expected**: Should load weights BEFORE job starts (from previous cycle)
**Red Flag**: Should NOT load weights from within the job

#### Step 5: Check when weights are saved
```bash
# In model-health job, search for weight update:
grep -B5 -A5 "trigger_weight_update\|UPDATE.*model_weights" .github/workflows/ml-orchestration.yml

# Should happen AFTER forecast_job completes
```

### Database Verification
```sql
-- Check weight update order in real data
SELECT 
    f.forecast_id,
    f.forecast_generated_at,
    f.horizon,
    m.last_updated as weight_last_updated,
    (f.forecast_generated_at > m.last_updated) as safe_timing
FROM ml_forecasts f
JOIN model_weights m ON f.horizon = m.horizon
WHERE f.forecast_generated_at > NOW() - INTERVAL '10 days'
ORDER BY f.forecast_generated_at DESC
LIMIT 10;

-- If safe_timing = true for ALL rows → SAFE ✅
-- If ANY safe_timing = false → LEAKAGE RISK ❌

-- Also check update reason:
SELECT 
    horizon,
    last_updated,
    update_reason,
    rf_weight,
    gb_weight
FROM model_weights
ORDER BY last_updated DESC
LIMIT 5;
-- Should show daily updates with reason like "daily_refresh_evaluation"
```

### Checklist
- [ ] Check `.github/workflows/ml-orchestration.yml`
- [ ] Verify `ml-forecast` has no `needs:` (runs first)
- [ ] Verify `model-health` has `needs: ml-forecast`
- [ ] Confirm `options-processing` is independent or needs `ml-forecast`
- [ ] Find `trigger_weight_update()` RPC call (should be in model-health job)
- [ ] Verify weight update happens AFTER forecast generation completes
- [ ] Database shows weights updated 1 day before next forecast uses them

---

## RISK #3: Feature Engineering Leakage (MEDIUM PRIORITY)

### System Context
Your system uses:
```
ml/src/features/technical_indicators.py          (RSI, MACD, ADX, etc.)
ml/src/features/support_resistance_detector.py   (S/R levels)
ml/src/features/polynomial_sr_indicator.py       (Polynomial regression S/R)
ml/src/features/feature_cache.py                 (Feature caching)
```

**Vulnerability**: If indicators calculated globally, then sliced → RSI/MACD use future prices for smoothing

### Files to Check
```
ml/src/features/technical_indicators.py
ml/src/features/support_resistance_detector.py
ml/src/features/polynomial_sr_indicator.py
ml/src/features/feature_cache.py
```

### Verification Steps

#### Step 1: Check technical_indicators.py structure
```bash
grep -n "^def " ml/src/features/technical_indicators.py | head -15
```

**Expected**: Functions like:
- `def calculate_rsi(prices, period=14):`
- `def calculate_macd(prices, ...):`
- `def calculate_adx(prices, ...):`

**Red Flag**: Functions like:
- `def calculate_rsi(symbol):` (loads data internally)
- `def get_all_indicators(symbol):` (global calculation)

#### Step 2: Verify window-based calculation for each indicator
```bash
# Pick one indicator and trace it:
grep -A20 "def calculate_rsi" ml/src/features/technical_indicators.py
```

**Expected Pattern**:
```python
def calculate_rsi(prices, period=14):
    """Calculate RSI on provided prices only"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    # ... rest of calculation
    return rsi
```

**Red Flag Pattern**:
```python
def calculate_rsi(symbol):
    """Calculate RSI"""
    all_prices = pd.read_sql(f"SELECT * FROM ohlc_bars_v2 WHERE symbol = {symbol}")
    # Now RSI uses future prices!
    rsi = ta.rsi(all_prices)  # Full dataset
    return rsi[:cutoff_date]  # Slicing after calculation
```

#### Step 3: Check for global database loads
```bash
grep -n "SELECT \* FROM ohlc\|read_sql(\"SELECT\|pd.read_csv.*ohlc" ml/src/features/technical_indicators.py
grep -n "SELECT \* FROM ohlc\|read_sql(\"SELECT\|pd.read_csv.*ohlc" ml/src/features/support_resistance_detector.py
grep -n "SELECT \* FROM ohlc\|read_sql(\"SELECT\|pd.read_csv.*ohlc" ml/src/features/polynomial_sr_indicator.py
```

**Expected**: These searches should return NOTHING (files shouldn't load data globally)
**Red Flag**: If you see `SELECT * FROM ohlc_bars_v2` in feature files

#### Step 4: Check Support/Resistance specific leakage
```bash
grep -n "polyfit\|polynomial\|poly\|regression" ml/src/features/polynomial_sr_indicator.py
```

**Expected**: Should see fitting functions, but verify they're passed only training prices
```python
# SAFE - fit on training prices only
sr_levels = np.polyfit(train_prices.index, train_prices.values, degree=3)

# RISKY - fit on all prices
sr_levels = np.polyfit(all_prices.index, all_prices.values, degree=3)
```

#### Step 5: Check feature_cache for window-aware caching
```bash
grep -n "cache.*key\|cache_key\|def.*cache" ml/src/features/feature_cache.py | head -10
```

**Expected**:
```python
# SAFE - Cache key includes time boundaries
cache_key = f"{symbol}_{period}_{start_date}_{end_date}_{indicator_name}"

# RISKY - Cache doesn't distinguish windows
cache_key = f"{symbol}_{period}_{indicator_name}"  # Could reuse wrong data!
```

#### Step 6: Check where features are calculated in training
```bash
# Trace from forecast_job back to feature calculation:
grep -n "get_features\|calculate_features\|calculate_indicators" ml/src/scripts/forecast_job.py
```

**Expected**: Should pass training_prices (window-specific) to feature function
**Red Flag**: Should NOT pass symbol (which would cause global load)

### Checklist
- [ ] Check `technical_indicators.py` - functions take `prices` parameter
- [ ] Check `support_resistance_detector.py` - no global database loads
- [ ] Check `polynomial_sr_indicator.py` - fitting uses provided data only
- [ ] Check `feature_cache.py` - cache keys include time windows
- [ ] Verify no `SELECT * FROM ohlc` in any feature file
- [ ] Trace from forecast_job to feature functions - confirm window-specific data passed

---

## RISK #4: Multi-Timeframe Data Leakage (MEDIUM PRIORITY)

### System Context
- **Daily Forecast** (04:00 UTC): Should use d1, w1 data ONLY
- **Intraday Forecast** (hourly): Should use m15, h1 data ONLY
- **Stored separately**: `ml_forecasts` vs `ml_forecasts_intraday`
- **Vulnerability**: If daily forecast uses intraday data → LEAKAGE

### Files to Check
```
ml/src/scripts/forecast_job.py           (daily - should use d1, w1)
ml/src/scripts/intraday_forecast.py      (intraday - should use m15, h1)
.github/workflows/ml-orchestration.yml   (daily scheduler)
.github/workflows/intraday-forecast.yml  (intraday scheduler)
```

### Verification Steps

#### Step 1: Daily forecast timeframe filtering
```bash
grep -n "timeframe\|m15\|h1\|d1\|w1" ml/src/scripts/forecast_job.py | grep -E "(WHERE|AND|timeframe)" | head -10
```

**Expected**:
- `WHERE timeframe IN ('d1', 'w1')`
- OR: `WHERE timeframe = 'd1'`
- NO mention of `m15` or `h1` in WHERE clause

**Red Flag**:
- `WHERE timeframe IN ('m15', 'h1', 'd1')`  (mixed!)
- No timeframe filter at all
- `WHERE timeframe = 'd1' OR timeframe = 'h1'`  (shouldn't include intraday)

#### Step 2: Intraday forecast timeframe filtering
```bash
grep -n "timeframe\|m15\|h1\|d1\|w1" ml/src/scripts/intraday_forecast.py | grep -E "(WHERE|AND|timeframe)" | head -10
```

**Expected**:
- `WHERE timeframe IN ('m15', 'h1')`
- NO mention of `d1` or `w1`

**Red Flag**:
- `WHERE timeframe IN ('d1', 'w1')`  (shouldn't use daily)
- Mixed timeframes

#### Step 3: Verify separate storage
```bash
grep -n "INSERT INTO ml_forecasts[^_]" ml/src/scripts/forecast_job.py
grep -n "INSERT INTO ml_forecasts_intraday" ml/src/scripts/intraday_forecast.py
```

**Expected**:
- Daily forecast → `INSERT INTO ml_forecasts`
- Intraday forecast → `INSERT INTO ml_forecasts_intraday`

#### Step 4: Check feature engineering doesn't mix
```bash
grep -n "get_features\|calculate_features" ml/src/scripts/forecast_job.py
# Then check what that function does:
grep -B2 -A10 "^def get_features\|^def calculate_features" ml/src/scripts/forecast_job.py
```

**Expected**: Features calculated from d1/w1 data only
**Red Flag**: Features calculated from all timeframes

#### Step 5: Verify workflow scheduling doesn't overlap dangerously
```bash
# Daily schedule:
grep -n "schedule:\|cron:" .github/workflows/ml-orchestration.yml

# Intraday schedule:
grep -n "schedule:\|cron:" .github/workflows/intraday-forecast.yml
```

**Expected**:
- Daily: `0 4 * * *` (04:00 UTC) - after market closes previous day
- Intraday: `0 * 9-16 * * 1-5` or similar (during market hours only)

**Red Flag**:
- Intraday starting before 09:00 UTC
- Intraday running outside market hours

### Database Verification
```sql
-- Verify data separation by table
SELECT 
    'ml_forecasts' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT horizon) as unique_horizons
FROM ml_forecasts
UNION ALL
SELECT 
    'ml_forecasts_intraday',
    COUNT(*),
    COUNT(DISTINCT horizon)
FROM ml_forecasts_intraday;

-- Check timeframes in daily training
SELECT DISTINCT timeframe 
FROM ohlc_bars_v2 
WHERE symbol_id IN (SELECT id FROM symbols LIMIT 5)
ORDER BY timeframe;
-- Should see: d1, w1, m15, h1 (with different data)

-- Verify forecast cutoffs are separate
SELECT 
    f.horizon,
    MAX(f.created_at) as latest_daily_forecast
FROM ml_forecasts f
WHERE f.created_at > NOW() - INTERVAL '1 day'
GROUP BY horizon;

SELECT 
    f.horizon,
    MAX(f.created_at) as latest_intraday_forecast
FROM ml_forecasts_intraday f
WHERE f.created_at > NOW() - INTERVAL '1 day'
GROUP BY horizon;
```

### Checklist
- [ ] Daily forecast filters `WHERE timeframe IN ('d1', 'w1')`
- [ ] Intraday forecast filters `WHERE timeframe IN ('m15', 'h1')`
- [ ] Results stored in separate tables (`ml_forecasts` vs `ml_forecasts_intraday`)
- [ ] Daily forecast job runs AFTER 02:00 UTC (after daily data refresh)
- [ ] Intraday forecast job runs DURING market hours ONLY
- [ ] Features for daily use only d1/w1 bars
- [ ] Features for intraday use only m15/h1 bars
- [ ] Database confirms separate timeframe data

---

## RISK #5: Confidence Calibration Leakage (MEDIUM PRIORITY)

### System Context
Your system has:
- `confidence_calibrator.py`: Calibrate confidence scores
- `uncertainty_quantifier.py`: Quantify uncertainty
- `conformal_interval.py`: Conformal prediction intervals

**Vulnerability**: If calibration done on training data → confidence scores overfit

### Files to Check
```
ml/src/monitoring/confidence_calibrator.py
ml/src/models/uncertainty_quantifier.py
ml/src/models/conformal_interval.py
```

### Verification Steps

#### Step 1: Find calibration function
```bash
grep -n "def.*calibrat\|def.*fit" ml/src/monitoring/confidence_calibrator.py | head -10
```

#### Step 2: Check what data is used for calibration
```bash
grep -A20 "def.*calibrat" ml/src/monitoring/confidence_calibrator.py | grep -E "(X_|y_|data|fit)"
```

**Expected**:
```python
def calibrate(self, X_val, y_val):  # Validation set
    self.calibrator.fit(X_val, y_val)
    return self
```

**Red Flag**:
```python
def calibrate(self, X_train, y_train):  # Training set!
    self.calibrator.fit(X_train, y_train)
    return self
```

#### Step 3: Search for training data usage
```bash
grep -n "X_train.*calibrat\|y_train.*calibrat\|train.*calibrat" ml/src/monitoring/confidence_calibrator.py
```

**Expected**: No results (training data should NOT be used)
**Red Flag**: If you find these patterns

#### Step 4: Check for validation/test set usage
```bash
grep -n "X_val\|X_test\|validation\|holdout" ml/src/monitoring/confidence_calibrator.py
```

**Expected**: Should see reference to validation or test set

#### Step 5: Verify separation in training pipeline
```bash
grep -n "calibrator\|confidence" ml/src/training/ensemble_training_job.py | head -20
```

Should see separation like:
```python
# Train model
model.fit(X_train, y_train)

# Evaluate on validation set
val_preds = model.predict(X_val)

# Calibrate on validation predictions
calibrator.fit(val_preds, y_val)  # NOT on training preds!

# Evaluate on test set
test_preds = model.predict(X_test)
calibration_score = calibrator.measure_confidence(test_preds)
```

### Checklist
- [ ] Find `calibrate()` function in confidence_calibrator.py
- [ ] Verify it takes validation/test set, NOT training set
- [ ] Confirm separate holdout set exists
- [ ] Check training pipeline doesn't calibrate on training data
- [ ] Verify walk-forward respects embargo before calibration
- [ ] No patterns like `fit(X_train, y_train)` for calibration

---

## RISK #6: Purging Implementation (MEDIUM PRIORITY)

### System Context
Your system has:
- `walk_forward_cv.py`: Basic walk-forward (may have single path)
- `purged_walk_forward_cv.py`: Advanced with purging + embargo

**Vulnerability**: Without purging, overlapping features/labels between train/test cause leakage

### Files to Check
```
ml/src/evaluation/walk_forward_cv.py
ml/src/evaluation/purged_walk_forward_cv.py
ml/src/training/ensemble_training_job.py  (how CV is called)
```

### Verification Steps

#### Step 1: Find purging logic
```bash
grep -n "def.*purge\|embargo\|remove_overlap\|embargo_days" ml/src/evaluation/purged_walk_forward_cv.py | head -10
```

**Expected**: Should see functions or logic for purging

**Red Flag**: If you see NOTHING - purging not implemented

#### Step 2: Check embargo period
```bash
grep -n "embargo.*=\|embargo.*day\|embargo.*bar" ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**: Should see something like:
```python
embargo_days = 5  # or 10
```

**Red Flag**:
- `embargo_days = 0` (no embargo)
- `embargo_days = 1` (too small)
- No embargo at all

#### Step 3: Verify overlapping observations are removed
```bash
grep -n "remove.*overlap\|purge.*obs\|exclude.*train\|training.*dates" ml/src/evaluation/purged_walk_forward_cv.py | head -10
```

**Expected**: Should see logic to remove training observations that overlap test period

```python
# SAFE - Remove overlapping observations
train_indices = train_indices[train_indices < (test_indices[0] - embargo_days)]
```

#### Step 4: Check for multiple paths (not single sequence)
```bash
grep -n "for.*fold\|for.*path\|range.*fold\|num_fold\|enumerate.*fold" ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**: Should see loop generating multiple paths
**Red Flag**: If it's just `train_test_split()` without loop

#### Step 5: Verify assertions for safety
```bash
grep -n "assert.*<\|assert.*train\|assert.*embargo" ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**:
```python
assert train_dates.max() < test_dates.min() - embargo_days
```

#### Step 6: Compare file sizes (purged should be longer)
```bash
wc -l ml/src/evaluation/walk_forward_cv.py
wc -l ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**: `purged_walk_forward_cv.py` should be significantly longer (more logic)

### Database Verification
```sql
-- Check if multiple paths tested in results
SELECT 
    horizon,
    COUNT(DISTINCT fold_id) as num_folds,
    COUNT(DISTINCT COALESCE(path_id, 1)) as num_paths
FROM forecast_evaluations
WHERE evaluation_date > NOW() - INTERVAL '30 days'
GROUP BY horizon;

-- Expected: num_paths >= 5 (multiple paths)
-- If num_paths = 1 for all: Only single path (risky)

-- Check if embargo visible in results
SELECT 
    MAX(training_data_max_date) as latest_train_date,
    MIN(test_data_min_date) as earliest_test_date,
    (MIN(test_data_min_date) - MAX(training_data_max_date)) as embargo_days
FROM forecast_evaluations
WHERE evaluation_date > NOW() - INTERVAL '7 days'
GROUP BY fold_id;

-- Expected: embargo_days >= 5 for all folds
```

### Checklist
- [ ] `purged_walk_forward_cv.py` exists and contains purging logic
- [ ] Embargo period defined (5-10 days minimum)
- [ ] Multiple paths generated (not just one sequence)
- [ ] Overlapping observations removed
- [ ] Assertions verify `train_max < (test_min - embargo)`
- [ ] Results show training data ends 5+ days before test data starts

---

## RISK #7: Single Path vs. Multiple Path Testing (LOW PRIORITY)

### System Context
- **Single path**: Train on Bull 2025 → Test on Bull 2026 → Works! But what about crashes?
- **Multiple paths**: Test across Bull/Sideways/Bear regimes → Realistic performance
- **Vulnerability**: Single path can appear profitable while failing in untested regimes

### Files to Check
```
ml/src/evaluation/walk_forward_cv.py
ml/src/evaluation/purged_walk_forward_cv.py
ml/src/training/ensemble_training_job.py
```

### Verification Steps

#### Step 1: Count folds/paths
```bash
grep -n "n_splits\|num_splits\|n_folds\|num_folds\|num_paths" ml/src/evaluation/walk_forward_cv.py ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**:
```python
n_splits = 10  # or similar
```

**Red Flag**:
```python
n_splits = 1  # Only one path!
```

#### Step 2: Check for CPCV (Combinatorial Purged CV)
```bash
grep -n "CPCV\|combinatorial\|multiple.*path\|num_combination" ml/src/evaluation/purged_walk_forward_cv.py
```

**Expected**: Should see logic for creating multiple non-overlapping paths

#### Step 3: Verify results aggregation
```bash
grep -n "mean\|std\|min\|max" ml/src/evaluation/purged_walk_forward_cv.py | grep -i "accur\|performance\|metric"
```

**Expected**:
```python
results['accuracy_mean'] = accuracy_scores.mean()
results['accuracy_std'] = accuracy_scores.std()
results['accuracy_min'] = accuracy_scores.min()
results['accuracy_max'] = accuracy_scores.max()
```

#### Step 4: Check stored metrics
```bash
grep -n "accuracy\|performance\|metric" ml/src/scripts/evaluation_job.py | head -20
```

Should store multiple metrics:
- `accuracy_mean`
- `accuracy_std`
- `accuracy_min`
- `accuracy_max`
- Possibly `accuracy_by_regime` if tracking market regimes

#### Step 5: Check if regimes are tested
```bash
grep -n "regime\|bull\|bear\|sideways\|volatile" ml/src/evaluation/purged_walk_forward_cv.py
grep -n "regime\|market_condition" ml/src/scripts/forecast_job.py ml/src/scripts/evaluation_job.py
```

**Expected**: Should see references to market regimes

### Database Verification
```sql
-- Check if multiple paths tested
SELECT 
    horizon,
    COUNT(DISTINCT fold_id) as num_folds,
    COUNT(DISTINCT COALESCE(path_id, 1)) as num_paths,
    COUNT(*) as total_evaluations
FROM forecast_evaluations
WHERE evaluation_date > NOW() - INTERVAL '30 days'
GROUP BY horizon;

-- Expected: num_paths >= 5, total_evaluations >> num_folds
-- If num_paths = 1: Single path (risky)

-- Check if accuracy varies significantly
SELECT 
    horizon,
    AVG(accuracy) as mean_accuracy,
    STDDEV(accuracy) as std_accuracy,
    MIN(accuracy) as min_accuracy,
    MAX(accuracy) as max_accuracy
FROM forecast_evaluations
WHERE evaluation_date > NOW() - INTERVAL '30 days'
GROUP BY horizon;

-- Expected: std_accuracy >= 5% (varies by path/regime)
-- If std_accuracy < 2%: Too consistent (possible overfitting)

-- Check if regime-specific results exist
SELECT DISTINCT 
    market_regime,
    COUNT(*) as num_evaluations,
    AVG(accuracy) as avg_accuracy
FROM forecast_evaluations
WHERE evaluation_date > NOW() - INTERVAL '30 days'
GROUP BY market_regime;

-- Expected: Multiple regimes (Bull, Bear, Sideways, Volatile)
-- Results should vary significantly by regime
```

### Checklist
- [ ] `n_splits` or `num_paths` >= 5 (minimum)
- [ ] Results aggregated across paths (mean, std, min, max)
- [ ] Performance varies by fold (not identical)
- [ ] CPCV or equivalent implemented (multiple paths)
- [ ] Regime-specific results tracked
- [ ] Single-path and multi-path accuracy differs by 5-15%
- [ ] Database confirms multiple paths tested

---

## Summary Checklist

### Critical (Must Pass)
- [ ] **RISK #1**: Training data explicitly excludes forecast period
- [ ] **RISK #2**: Weights updated 1 day BEFORE being used in forecast
- [ ] **RISK #3**: Features calculated per-window, not globally
- [ ] **RISK #4**: Daily forecasts use ONLY d1/w1 data

### Important (Should Pass)
- [ ] **RISK #5**: Confidence calibration uses validation set, NOT training set
- [ ] **RISK #6**: Purging removes overlapping observations, embargo >= 5 days
- [ ] **RISK #7**: Multiple paths tested, results vary by regime

### Success Criteria
If all checks pass → Your system has **robust walk-forward validation** with minimal data leakage risk.

If any critical check fails → **Stop live trading** and fix immediately.

---

## Next Steps

1. **Run verification steps above** for each RISK
2. **Document findings** in a verification report
3. **If failures found**: Fix highest priority first (RISK #1, #2, #3)
4. **Retest after fixes**
5. **Create regression tests** to prevent future leakage

---

**Version**: 1.0  
**Last Updated**: January 24, 2026
