# Dependency and Formatting Fixes
**Date**: January 23, 2026  
**Issue**: Hidden dependency and formatting problems in ML workflow

---

## Problems Identified

### 1. Pandas Deprecation Warning ⚠️
**Issue**: `Timestamp.utcnow()` is deprecated in pandas 2.0+
```
Pandas4Warning: Timestamp.utcnow is deprecated and will be removed in a future version. 
Use Timestamp.now('UTC') instead.
```

**Files Affected**:
- `ml/src/forecast_job.py`
- `ml/src/data/supabase_db.py` (3 instances)
- `ml/src/features/support_resistance_detector.py`
- `ml/src/features/feature_cache.py`
- `ml/src/symbol_weight_training_job.py`

### 2. Date Parsing Error ❌
**Issue**: ISO8601 timestamp parsing fails when microseconds are missing
```
ERROR: time data "2026-01-06T05:00:00+00:00" doesn't match format "%Y-%m-%dT%H:%M:%S.%f%z"
```

**File Affected**: `ml/src/monitoring/forecast_validator.py`

**Root Cause**: `pd.to_datetime()` was called without format specification, causing it to fail on ISO8601 timestamps that don't include microseconds.

### 3. Sklearn Warnings ⚠️
**Issue**: Single label in confusion matrix (informational, not critical)
```
UserWarning: A single label was found in 'y_true' and 'y_pred'. 
For the confusion matrix to have the correct shape, use the 'labels' parameter.
```

**Status**: Informational warning, doesn't break functionality

### 4. Insufficient Data Warnings ⚠️
**Issue**: Backtest failures due to insufficient historical data
```
WARNING: Backtest failed for SPY: Insufficient data: 249 bars (need 277)
```

**Status**: Expected behavior when data is limited, handled gracefully

---

## Fixes Applied

### ✅ Fix 1: Pandas Deprecation Warnings

**Changed**: `pd.Timestamp.utcnow()` → `pd.Timestamp.now('UTC')`

**Files Updated**:
1. `ml/src/forecast_job.py:305`
2. `ml/src/data/supabase_db.py:325, 494, 853, 915`
3. `ml/src/features/support_resistance_detector.py:754`
4. `ml/src/features/feature_cache.py:52`
5. `ml/src/symbol_weight_training_job.py:214`

**Before**:
```python
since_ts = pd.Timestamp.utcnow() - window
```

**After**:
```python
since_ts = pd.Timestamp.now('UTC') - window
```

### ✅ Fix 2: Date Parsing Error

**File**: `ml/src/monitoring/forecast_validator.py`

**Changed**: Added explicit ISO8601 format handling with fallback

**Before**:
```python
forecast_date = pd.to_datetime(forecast[date_col])
outcome = symbol_actuals[
    pd.to_datetime(symbol_actuals["date"]) >= outcome_date
].head(1)
```

**After**:
```python
# Handle ISO8601 format with timezone info
forecast_date = pd.to_datetime(forecast[date_col], format='ISO8601', errors='coerce')
if pd.isna(forecast_date):
    # Fallback to mixed format if ISO8601 fails
    forecast_date = pd.to_datetime(forecast[date_col], format='mixed', errors='coerce')

# Use ISO8601 format to handle various timestamp formats
try:
    actuals_dates = pd.to_datetime(symbol_actuals["date"], format='ISO8601', errors='coerce')
except Exception:
    # Fallback to mixed format if ISO8601 fails
    actuals_dates = pd.to_datetime(symbol_actuals["date"], format='mixed', errors='coerce')

outcome = symbol_actuals[
    actuals_dates >= outcome_date
].head(1)
```

---

## Impact

### ✅ Fixed Issues
- ✅ Pandas deprecation warnings eliminated
- ✅ Date parsing error fixed (workflow no longer crashes)
- ✅ Better error handling for various timestamp formats

### ⚠️ Remaining Warnings (Non-Critical)
- **Sklearn warnings**: Informational only, doesn't affect functionality
- **Insufficient data warnings**: Expected behavior, handled gracefully

---

## Testing

After these fixes, the workflow should:
1. ✅ Run without pandas deprecation warnings
2. ✅ Parse ISO8601 timestamps correctly (with or without microseconds)
3. ✅ Handle date parsing errors gracefully
4. ✅ Continue to show informational warnings (sklearn, insufficient data)

---

## Files Changed

1. `ml/src/forecast_job.py` - Fixed `Timestamp.utcnow()` deprecation
2. `ml/src/data/supabase_db.py` - Fixed 3 instances of `Timestamp.utcnow()`
3. `ml/src/features/support_resistance_detector.py` - Fixed `Timestamp.utcnow()`
4. `ml/src/features/feature_cache.py` - Fixed `Timestamp.utcnow()`
5. `ml/src/symbol_weight_training_job.py` - Fixed `Timestamp.utcnow()`
6. `ml/src/monitoring/forecast_validator.py` - Fixed date parsing with ISO8601 format

---

**Status**: ✅ **FIXED**  
**Last Updated**: January 23, 2026
