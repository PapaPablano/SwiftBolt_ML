# SwiftBolt ML - Regime Testing Pre-Flight Checklist
**Before running regime tests, verify these critical items**

---

## ✅ PRE-FLIGHT CHECKLIST

### 1. Data Infrastructure ✓
- [ ] Supabase connection working (`SupabaseDatabase()` instantiates)
- [ ] Can fetch at least 500 bars per stock
- [ ] Data covers 2022-present (need crash, recovery, bull periods). **Backfill if needed:** `cd ml && ./scripts/backfill_regime_ohlc.sh` (Alpaca d1 → 2022-01-01 to 2024-02-01)
- [ ] All OHLCV columns present (no missing `close`, `volume`, etc.)

**Test Command:**
```bash
cd /Users/ericpeterson/SwiftBolt_ML
python pipeline_audit.py --section 1   # Data infrastructure only
```

---

### 2. Data Cleaning ✓
- [ ] `DataCleaner.clean_all()` runs without errors
- [ ] Removes duplicates properly
- [ ] Handles NaN values (forward fill or drop)
- [ ] Outlier detection not too aggressive (<10% flagged)
- [ ] No zero/negative prices remain after cleaning

**Test Command:**
```bash
python pipeline_audit.py --section 2   # Data cleaning only
```

**Common Issues & Fixes:**

**Issue: "Column 'ts' not found"**
```python
# Fix: Ensure timestamp column is standardized
if 'timestamp' in df.columns and 'ts' not in df.columns:
    df['ts'] = df['timestamp']
```

**Issue: "Too many NaN values after cleaning"**
```python
# Fix: Check minimum data requirements
if len(df) < 250:
    logger.warning("Need 250+ bars for robust indicators")
    # Fetch more data or skip this stock
```

**Issue: "Price spikes after cleaning"**
```python
# Fix: Add split adjustment check
returns = df['close'].pct_change()
if (returns.abs() > 0.5).any():
    logger.warning("Possible stock split - verify data")
```

---

### 3. Feature Engineering ✓
- [ ] Indicators calculating correctly (not all NaN)
- [ ] At least 30-50 features generated per bar
- [ ] No feature leakage (future data in past rows)
- [ ] NaN/Inf values handled before model training

**Test Command:**
```bash
python pipeline_audit.py --section 3   # Feature engineering only
```

**Common Issues & Fixes:**

**Issue: "All indicators are NaN"**
```python
# Cause: Insufficient data (only 10-50 bars)
# Fix: Fetch 250+ bars minimum
df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=500)
```

**Issue: "prepare_training_data_binary returns empty X"**
```python
# Cause: Not enough valid features after indicator calculation
# Fix: Check indicator generation BEFORE feature prep
print(f"Columns after indicators: {len(df.columns)}")
print(f"Indicator columns: {[c for c in df.columns if any(x in c for x in ['sma', 'rsi', 'macd'])]}")
```

**Issue: "Features have Inf values"**
```python
# Fix: Clean features before training
X = X.replace([np.inf, -np.inf], np.nan)
X = X.fillna(0)  # Or use X.dropna()
```

---

### 4. Model Training ✓
- [ ] XGBoostForecaster instantiates
- [ ] `prepare_training_data_binary()` method exists
- [ ] `train()` completes without errors
- [ ] `predict_proba()` returns valid predictions
- [ ] Accuracy between 40-65% (if outside, check for issues)

**Test Command:**
```bash
python pipeline_audit.py --section 5   # End-to-end training pipeline
```

**Common Issues & Fixes:**

**Issue: "AttributeError: 'XGBoostForecaster' object has no attribute 'prepare_training_data_binary'"**
```python
# Fix: Check method name in your forecaster class
# Should be ONE of:
#   - prepare_training_data_binary(df, horizon_days, threshold_pct)
#   - prepare_binary_features(df, horizon, threshold)
#   - create_features(df, target_horizon, target_threshold)
```

**Issue: "ValueError: Input contains NaN"**
```python
# Fix: Clean features before training
def prepare_features_safe(df, horizon, threshold):
    X, y = forecaster.prepare_training_data_binary(df, horizon, threshold)
    
    # Remove NaN and Inf
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Drop columns with >50% NaN
    valid_cols = X.columns[X.isna().mean() < 0.5]
    X = X[valid_cols]
    
    # Fill remaining NaN with 0
    X = X.fillna(0)
    
    return X, y
```

**Issue: "Accuracy stuck at 50% for all tests"**
```python
# Causes:
# 1. Model not learning (check feature quality)
# 2. Target too balanced (50/50 split)
# 3. Threshold too small (try 0.02 instead of 0.01)
# 4. Insufficient data (need 200+ bars)

# Fix: Add diagnostics
print(f"Target distribution: {y.value_counts()}")
print(f"Feature correlation with target: {X.corrwith(y).abs().sort_values(ascending=False)[:5]}")
```

**Issue: "Accuracy too high (>70%)"**
```python
# CRITICAL: Check for data leakage!
# Causes:
# 1. Using future data in features
# 2. Not using time-based split
# 3. Target leakage (close price in features)

# Fix: Verify split and features
print(f"Train dates: {df_train['ts'].min()} to {df_train['ts'].max()}")
print(f"Test dates: {df_test['ts'].min()} to {df_test['ts'].max()}")
# Test dates should be AFTER train dates (no overlap)
```

---

### 5. Regime Coverage ✓
- [ ] Data available for crash_2022 (Mar-Oct 2022)
- [ ] Data available for recovery_2023 (Nov 2022-Dec 2023)
- [ ] Data available for bull_2024 (Jan-Dec 2024)
- [ ] Each regime has 50+ bars minimum

**Test Command:**
```bash
python test_regimes_fixed.py --test-data
```

**Common Issues & Fixes:**

**Issue: "Regime has 0 bars"**
```python
# Cause: Data doesn't cover that time period
# Fix: Either fetch older data or skip that regime
regime_results = evaluate_stock_in_regime(...)
if regime_results is None:
    logger.warning(f"Skipping {symbol} in {regime_name} - no data")
    continue
```

**Issue: "Regime has <30 samples after feature prep"**
```python
# Cause: Short regime period + feature lookback windows
# Fix: Use shorter horizons for short regimes
if len(df_regime) < 100:
    horizon = 3  # Reduce from 5 or 10
    threshold = 0.01  # Make target easier to hit
```

---

## 🔧 COMMON ERROR PATTERNS & FIXES

### Error: "KeyError: 'close'"
```python
# Fix: Standardize column names
df = df.rename(columns={
    'Close': 'close',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Volume': 'volume'
})
```

### Error: "TypeError: cannot do label indexing on <class 'pandas.core.indexes.datetimes.DatetimeIndex'> with these indexers"
```python
# Fix: Reset index before splitting
df = df.reset_index(drop=True)
X = X.reset_index(drop=True)
y = y.reset_index(drop=True)
```

### Error: "ValueError: zero-size array to reduction operation"
```python
# Cause: Empty dataframe after filtering
# Fix: Add length checks
if len(df_regime) == 0:
    logger.warning("No data for regime")
    return None

if len(X) == 0:
    logger.warning("No features generated")
    return None
```

### Error: "MemoryError: Unable to allocate array"
```python
# Cause: Creating too many features or loading too much data
# Fix: Limit feature creation
X = X.iloc[:, :100]  # Use only first 100 features
# Or use feature selection
from sklearn.feature_selection import SelectKBest, f_classif
selector = SelectKBest(f_classif, k=50)
X_selected = selector.fit_transform(X, y)
```

---

## 🚀 QUICK START SEQUENCE

**Step 1: Run Full Audit (5 minutes)**
```bash
cd /Users/ericpeterson/SwiftBolt_ML
python pipeline_audit.py > audit_results.txt
```

Review `audit_results.txt` - must have 0 critical issues to proceed.

**Step 2: Test Data Availability (2 minutes)**
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
python test_regimes_fixed.py --test-data   # or run from root: python test_regimes_fixed.py --test-data
```

Verify all stocks have data for all regimes.

**Step 3: Quick Test Single Stock (3 minutes)**
```bash
python test_regimes_fixed.py --quick-test AAPL --regime crash_2022
```

Should complete without errors and show ~50-55% accuracy.

**Step 4: Run Full Regime Tests (20-30 minutes)**
```bash
# From project root (either works):
chmod +x run_regime_tests.sh
./run_regime_tests.sh              # Interactive: quick test → prompts → full run
./run_regime_tests.sh --full       # Non-interactive: full run only (20-30 min, no prompts)
./run_regime_tests.sh --quick      # Quick test AAPL only, then exit

# Or run Python directly (from root or from ml/):
python test_regimes_fixed.py       # Full regime tests
```

---

## 🎬 FINAL COMMANDS (copy-paste)

```bash
# 1. Understand why accuracy is low (optional)
python diagnose_accuracy.py

# 2. Quick test one stock
python test_regimes_fixed.py --quick-test AAPL --regime crash_2022

# 3. If that works, run full tests (20-30 min)
./run_regime_tests.sh --full
# or: cd ml && python test_regimes_fixed.py
```

**What you'll see:** Crash regime (defensive PG/KO) ~58-62%; recovery (growth NVDA) ~60-65%; bull (all) ~48-52%. Defensive stocks excel in crashes; growth in recovery; bull is harder (normal).

---

## 📊 EXPECTED RESULTS

### Healthy Results:
- **Crash periods (2022)**: Defensive stocks 55-62%, Growth 52-58%
- **Recovery (2023)**: Growth stocks 58-65%, Defensive 48-52%
- **Bull (2024)**: All stocks 48-55% (harder to predict)
- **Training time**: 10-30 seconds per stock/regime
- **No errors or warnings during execution**

### Problematic Results:
- **All accuracies 50%**: Model not learning, check features
- **All accuracies <45%**: Check target threshold (may be too hard)
- **All accuracies >65%**: Data leakage - CHECK IMMEDIATELY
- **Many "Insufficient data" warnings**: Fetch more historical data
- **"Evaluation failed" errors**: Check data cleaning pipeline

---

## 🔍 DIAGNOSTIC COMMANDS

**Check Supabase Connection:**
```python
from src.data.supabase_db import SupabaseDatabase
db = SupabaseDatabase()
df = db.fetch_ohlc_bars('AAPL', 'd1', limit=10)
print(f"Fetched {len(df)} bars")
```

**Check Data Cleaning:**
```python
from src.data.data_cleaner import DataCleaner
df_clean = DataCleaner.clean_all(df, verbose=True)
print(f"Before: {len(df)} bars, After: {len(df_clean)} bars")
```

**Check Feature Generation:**
```python
from src.models.xgboost_forecaster import XGBoostForecaster
model = XGBoostForecaster()
X, y = model.prepare_training_data_binary(df, horizon_days=5, threshold_pct=0.015)
print(f"Features: {X.shape}, Target: {y.shape}")
print(f"Feature names: {X.columns[:10].tolist()}")
```

**Check Model Training:**
```python
split = int(len(X) * 0.8)
model.train(X[:split], y[:split])
preds = model.predict_proba(X[split:])
acc = (preds[:, 1].round() == y[split:].values).mean()
print(f"Accuracy: {acc:.1%}")
```

---

## 📝 NEXT STEPS AFTER SUCCESSFUL AUDIT

1. ✅ Run `pipeline_audit.py` → Fix all critical issues
2. ✅ Run `test_regimes_fixed.py --test-data` → Verify coverage
3. ✅ Run `test_regimes_fixed.py --quick-test AAPL` → Validate one stock
4. ✅ Run `test_regimes_fixed.py` → Full regime analysis
5. ✅ Analyze `regime_test_results.csv` → Find best stock/regime combos
6. ✅ Build regime-aware portfolio strategy

---

## 🆘 EMERGENCY FIXES

**If Everything Fails:**

```bash
# 1. Reset to clean state
cd /Users/ericpeterson/SwiftBolt_ML
git status  # Check for uncommitted changes

# 2. Verify Python environment
python --version  # Should be 3.8+
pip list | grep -E "(pandas|numpy|xgboost|scikit)"

# 3. Re-install critical packages
pip install --upgrade pandas numpy xgboost scikit-learn ta-lib

# 4. Test minimal example
python -c "
from src.data.supabase_db import SupabaseDatabase
db = SupabaseDatabase()
df = db.fetch_ohlc_bars('AAPL', 'd1', limit=100)
print(f'Success: {len(df)} bars')
"
```

**If Supabase Times Out:**
```python
# Add retry logic
import time
for attempt in range(3):
    try:
        df = db.fetch_ohlc_bars(symbol, 'd1', limit=500)
        break
    except:
        if attempt < 2:
            time.sleep(2)
        else:
            raise
```

---

## 📞 WHEN TO ASK FOR HELP

Ask for help if you see:
- ❌ "Cannot import SupabaseDatabase" → Environment issue
- ❌ Pipeline audit shows >5 critical issues → Structural problem
- ❌ All regime tests fail with same error → Core bug
- ❌ Accuracies consistently >70% → Data leakage (serious)
- ❌ Training takes >5 minutes per stock → Performance issue

Do NOT ask for help if:
- ⚠️  A few stocks have "Insufficient data" → Normal, skip them
- ⚠️  Some indicators are NaN → Expected with limited data
- ⚠️  Accuracy is 48-52% → Normal for hard problems
- ⚠️  One stock fails while others work → Stock-specific issue

---

**Run the audit now and share results!** 🚀
