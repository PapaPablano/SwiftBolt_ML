# Forecast Evaluation Architecture Review
**Date**: January 23, 2026  
**Based on**: ML Forecast Evaluation Best Practices  
**Status**: ⚠️ **Issues Identified - Fixes Recommended**

---

## 🔍 Analysis Based on Best Practices

After consulting industry best practices for ML forecast evaluation systems, here are the key findings:

---

## ✅ What We're Doing Right

1. **Three-Table Architecture** ✅
   - `ml_forecasts`: Immutable forecast storage
   - `forecast_evaluations`: Evaluation results
   - `live_predictions`: Derived accuracy scores
   - This separation is correct

2. **Rolling Window Evaluation** ✅
   - `evaluation_job` evaluates forecasts after they mature
   - Uses proper time windows (1D, 1W, 1M)

3. **Direction + Price Error Tracking** ✅
   - Tracks both `direction_correct` and `price_error_pct`
   - Useful for different use cases

---

## ⚠️ Issues Identified

### 1. **Missing MAPE/SMAPE in forecast_evaluations**

**Problem**: We calculate `price_error_pct` but not MAPE (Mean Absolute Percentage Error) or SMAPE (Symmetric MAPE), which are industry-standard metrics.

**Current**:
```python
price_error_pct = price_error / start_price  # This is not MAPE
```

**Should be**:
```python
mape = abs((actual - forecast) / actual) * 100  # MAPE
smape = 200 * abs(actual - forecast) / (abs(actual) + abs(forecast))  # SMAPE
```

**Impact**: `live_predictions` uses direction accuracy instead of price accuracy, which is less informative.

---

### 2. **live_predictions Should Be Derived, Not Manually Populated**

**Best Practice**: `live_predictions` should be a **materialized view or computed on-demand** from `forecast_evaluations`, not manually populated.

**Current**: Manual script `populate_live_predictions.py` runs periodically.

**Recommended**: 
- Create a Supabase function that computes live predictions on-demand
- Or use a materialized view (if supported)
- Or compute in `ValidationService` directly from `forecast_evaluations`

**Why**: 
- Single source of truth (`forecast_evaluations`)
- Always up-to-date
- No sync issues

---

### 3. **No Time-Decay Weighting**

**Problem**: All evaluations in the window are weighted equally. Recent evaluations should be weighted more heavily.

**Current**:
```python
accuracy = stats["correct"] / stats["total"]  # Equal weighting
```

**Should be**:
```python
# Exponential decay: recent = higher weight
weights = [exp(-decay_rate * days_ago) for days_ago in evaluation_ages]
weighted_accuracy = sum(correct * weight) / sum(total * weight)
```

---

### 4. **Missing Baseline Comparison**

**Best Practice**: Compare model accuracy against baseline models (Naive, ARIMA, ETS).

**Current**: No baseline comparison in `live_predictions`.

**Should have**:
- Baseline accuracy stored in `live_predictions`
- Comparison: `model_accuracy vs baseline_accuracy`
- Degradation detection when model < baseline

---

### 5. **Using Direction Accuracy Instead of Price Accuracy**

**Problem**: `live_predictions.accuracy_score` uses direction accuracy (correct/total), but for price forecasting, MAPE is more appropriate.

**Current**:
```python
accuracy = stats["correct"] / stats["total"]  # Direction accuracy
```

**Should be**:
```python
# Convert price_error_pct to accuracy score
# Lower error = higher accuracy
mape_scores = [1 - min(e["price_error_pct"], 1.0) for e in evaluations]
accuracy = sum(mape_scores) / len(mape_scores)
```

Or use inverse MAPE:
```python
mape = mean([abs((actual - forecast) / actual) for ...])
accuracy = 1 / (1 + mape)  # Inverse MAPE as accuracy score
```

---

## 🔧 Recommended Fixes

### Fix 1: Add MAPE to forecast_evaluations

**File**: `ml/src/evaluation_job.py`

**Change**:
```python
# Calculate MAPE
mape = abs((realized_price - predicted_value) / realized_price) * 100 if realized_price != 0 else 0

# Add to evaluation dict
evaluation = {
    ...
    "mape": mape,
    "price_error_pct": price_error_pct,  # Keep existing
    ...
}
```

**Migration**: Add `mape` column to `forecast_evaluations` table.

---

### Fix 2: Make live_predictions Computed On-Demand

**Option A: Supabase Function** (Recommended)

Create a function that computes live predictions:
```sql
CREATE OR REPLACE FUNCTION get_live_predictions(
    p_symbol_id UUID,
    p_timeframe TEXT,
    p_days_back INT DEFAULT 30
)
RETURNS TABLE (
    symbol_id UUID,
    timeframe TEXT,
    signal TEXT,
    accuracy_score NUMERIC,
    sample_size INT,
    last_updated TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_symbol_id,
        p_timeframe,
        -- Get most recent signal
        (SELECT predicted_label FROM forecast_evaluations 
         WHERE symbol_id = p_symbol_id 
         ORDER BY evaluation_date DESC LIMIT 1)::TEXT,
        -- Calculate weighted MAPE accuracy
        AVG(1.0 / (1.0 + mape)) as accuracy_score,
        COUNT(*) as sample_size,
        MAX(evaluation_date) as last_updated
    FROM forecast_evaluations
    WHERE symbol_id = p_symbol_id
    AND evaluation_date >= NOW() - (p_days_back || ' days')::INTERVAL;
END;
$$ LANGUAGE plpgsql;
```

**Option B: Compute in ValidationService**

Modify `ValidationService._get_live_score()` to compute directly from `forecast_evaluations` instead of reading `live_predictions`.

---

### Fix 3: Add Time-Decay Weighting

**File**: `ml/src/scripts/populate_live_predictions.py` (if keeping manual approach)

**Change**:
```python
import math
from datetime import datetime

# Exponential decay: recent = higher weight
decay_rate = 0.1  # Adjust based on desired decay speed

for eval_data in evaluations:
    days_ago = (datetime.now() - pd.to_datetime(eval_data["evaluation_date"])).days
    weight = math.exp(-decay_rate * days_ago)
    
    symbol_horizon_stats[key]["weighted_correct"] += (1 if correct else 0) * weight
    symbol_horizon_stats[key]["total_weight"] += weight

# Calculate weighted accuracy
accuracy = stats["weighted_correct"] / stats["total_weight"]
```

---

### Fix 4: Use MAPE-Based Accuracy Instead of Direction

**File**: `ml/src/scripts/populate_live_predictions.py`

**Change**:
```python
# Instead of direction accuracy
# accuracy = stats["correct"] / stats["total"]

# Use MAPE-based accuracy
mape_scores = []
for eval_data in evaluations:
    if eval_data.get("symbol") == symbol and eval_data.get("horizon") == horizon:
        mape = eval_data.get("mape", 0) / 100  # Convert % to decimal
        # Convert MAPE to accuracy: lower MAPE = higher accuracy
        accuracy_from_mape = 1.0 / (1.0 + mape)
        mape_scores.append(accuracy_from_mape)

if mape_scores:
    accuracy = sum(mape_scores) / len(mape_scores)
else:
    # Fallback to direction accuracy if MAPE not available
    accuracy = stats["correct"] / stats["total"]
```

---

### Fix 5: Add Baseline Comparison

**New Table**: `baseline_forecast_accuracy`

```sql
CREATE TABLE baseline_forecast_accuracy (
    symbol_id UUID REFERENCES symbols(id),
    timeframe TEXT,
    baseline_type TEXT,  -- 'naive', 'arima', 'ets'
    accuracy_score NUMERIC,
    sample_size INT,
    last_updated TIMESTAMPTZ,
    PRIMARY KEY (symbol_id, timeframe, baseline_type)
);
```

**Update live_predictions** to include baseline:
```python
# Fetch baseline
baseline = get_baseline_accuracy(symbol_id, timeframe)

prediction_data = {
    ...
    "accuracy_score": accuracy,
    "baseline_accuracy": baseline,
    "vs_baseline": accuracy - baseline,  # Positive = better than baseline
    ...
}
```

---

## 📊 Recommended Architecture

### Data Flow (Improved)

```
1. FORECAST GENERATION
   └─> ml_forecasts (immutable)

2. EVALUATION (after forecast matures)
   └─> forecast_evaluations
       ├─> direction_correct
       ├─> price_error_pct
       └─> mape (NEW)

3. LIVE ACCURACY (computed on-demand)
   └─> get_live_predictions() function
       ├─> Reads from forecast_evaluations
       ├─> Applies time-decay weighting
       ├─> Calculates MAPE-based accuracy
       └─> Returns current accuracy per symbol/timeframe

4. VALIDATION SERVICE
   └─> Calls get_live_predictions()
   └─> Uses real accuracy scores
```

---

## 🎯 Priority Fixes

### High Priority
1. ✅ Add MAPE to `forecast_evaluations` (migration + code)
2. ✅ Make `live_predictions` computed on-demand (Supabase function)
3. ✅ Use MAPE-based accuracy instead of direction accuracy

### Medium Priority
4. ⚠️ Add time-decay weighting
5. ⚠️ Add baseline comparison

### Low Priority
6. ℹ️ Add SMAPE as alternative metric
7. ℹ️ Add confidence intervals for accuracy scores

---

## ✅ Summary

**Current State**: 
- ✅ Architecture is sound (three-table separation)
- ⚠️ Missing MAPE metrics
- ⚠️ Manual population instead of computed
- ⚠️ Using direction accuracy instead of price accuracy

**Recommended Changes**:
1. Add MAPE to evaluations
2. Make live_predictions computed (function or on-demand)
3. Use MAPE-based accuracy scores
4. Add time-decay weighting
5. Add baseline comparison

**Impact**: More accurate, industry-standard forecast evaluation system.

---

**Status**: ⚠️ **Issues Identified - Fixes Recommended**  
**Last Updated**: January 23, 2026
