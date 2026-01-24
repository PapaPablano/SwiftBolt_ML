# Forecast Evaluation System - Critical Fixes
**Date**: January 23, 2026  
**Priority**: High  
**Status**: 🔧 **Fixes Required**

---

## 🎯 Executive Summary

After reviewing our forecast evaluation system against industry best practices, we've identified **5 critical issues** that need to be addressed:

1. **Missing MAPE metrics** - We track `price_error_pct` but not MAPE (industry standard)
2. **Manual live_predictions population** - Should be computed on-demand
3. **Wrong accuracy metric** - Using direction accuracy instead of price accuracy
4. **No time-decay weighting** - Recent evaluations should be weighted more
5. **Missing baseline comparison** - No comparison against naive/ARIMA baselines

---

## 🔴 Critical Issue #1: Missing MAPE in forecast_evaluations

### Problem
We calculate `price_error_pct` but not MAPE (Mean Absolute Percentage Error), which is the industry standard for forecast accuracy.

### Current Code
```python
# ml/src/evaluation_job.py
price_error = abs(predicted_value - realized_price)
price_error_pct = price_error / start_price  # This is NOT MAPE
```

### Fix Required

**1. Add MAPE column to database:**
```sql
-- Migration: Add MAPE to forecast_evaluations
ALTER TABLE forecast_evaluations 
ADD COLUMN IF NOT EXISTS mape NUMERIC;

CREATE INDEX IF NOT EXISTS idx_forecast_eval_mape 
ON forecast_evaluations(mape);
```

**2. Calculate MAPE in evaluation_job.py:**
```python
# Calculate MAPE (Mean Absolute Percentage Error)
if realized_price != 0:
    mape = abs((realized_price - predicted_value) / realized_price) * 100
else:
    mape = 0  # Handle division by zero

evaluation = {
    ...
    "mape": mape,
    "price_error_pct": price_error_pct,  # Keep existing
    ...
}
```

**Impact**: Enables proper price accuracy tracking (not just direction).

---

## 🔴 Critical Issue #2: live_predictions Should Be Computed, Not Manual

### Problem
We manually populate `live_predictions` via a script. Best practice: compute on-demand from `forecast_evaluations` (single source of truth).

### Current Approach
```python
# ml/src/scripts/populate_live_predictions.py
# Manually reads evaluations and writes to live_predictions
```

### Fix Required

**Option A: Supabase Function (Recommended)**

Create a function that computes live predictions on-demand:

```sql
-- Function to get live predictions (computed from evaluations)
CREATE OR REPLACE FUNCTION get_live_predictions(
    p_symbol_id UUID DEFAULT NULL,
    p_timeframe TEXT DEFAULT NULL,
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
    WITH horizon_to_tf AS (
        SELECT '1D'::TEXT as horizon, 'd1'::TEXT as tf
        UNION SELECT '1W', 'w1'
        UNION SELECT '15m', 'm15'
        UNION SELECT '1h', 'h1'
        UNION SELECT '4h', 'h4'
    ),
    evaluations AS (
        SELECT 
            fe.symbol_id,
            htf.tf as timeframe,
            fe.predicted_label,
            fe.mape,
            fe.direction_correct,
            fe.evaluation_date,
            -- Time-decay weight (recent = higher weight)
            EXP(-0.1 * EXTRACT(EPOCH FROM (NOW() - fe.evaluation_date)) / 86400) as weight
        FROM forecast_evaluations fe
        JOIN horizon_to_tf htf ON htf.horizon = fe.horizon
        WHERE fe.evaluation_date >= NOW() - (p_days_back || ' days')::INTERVAL
        AND (p_symbol_id IS NULL OR fe.symbol_id = p_symbol_id)
        AND (p_timeframe IS NULL OR htf.tf = p_timeframe)
    ),
    aggregated AS (
        SELECT
            symbol_id,
            timeframe,
            -- Most recent signal
            (SELECT predicted_label FROM evaluations e2 
             WHERE e2.symbol_id = e.symbol_id 
             AND e2.timeframe = e.timeframe
             ORDER BY evaluation_date DESC LIMIT 1) as signal,
            -- MAPE-based accuracy (lower MAPE = higher accuracy)
            CASE 
                WHEN AVG(mape) > 0 THEN 1.0 / (1.0 + AVG(mape) / 100.0)
                ELSE AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END)
            END as accuracy_score,
            COUNT(*) as sample_size,
            MAX(evaluation_date) as last_updated
        FROM evaluations e
        GROUP BY symbol_id, timeframe
        HAVING COUNT(*) >= 3  -- Minimum sample size
    )
    SELECT * FROM aggregated;
END;
$$ LANGUAGE plpgsql;
```

**Option B: Compute in ValidationService**

Modify `ValidationService._get_live_score()` to compute directly from `forecast_evaluations`:

```python
async def _get_live_score(self, symbol: str) -> float:
    # Read directly from forecast_evaluations
    result = (
        self.db.client.table("forecast_evaluations")
        .select("mape, direction_correct, evaluation_date")
        .eq("symbol_id", symbol_id)
        .gte("evaluation_date", (datetime.now() - timedelta(days=30)).isoformat())
        .order("evaluation_date", desc=True)
        .limit(50)
        .execute()
    )
    
    # Calculate MAPE-based accuracy with time decay
    # ... (implementation)
```

**Impact**: Single source of truth, always up-to-date, no sync issues.

---

## 🔴 Critical Issue #3: Using Direction Accuracy Instead of Price Accuracy

### Problem
`live_predictions.accuracy_score` uses direction accuracy (correct/total), but for price forecasting, MAPE-based accuracy is more appropriate.

### Current Code
```python
# ml/src/scripts/populate_live_predictions.py
accuracy = stats["correct"] / stats["total"]  # Direction accuracy
```

### Fix Required

**Use MAPE-based accuracy:**

```python
# Calculate MAPE-based accuracy
mape_scores = []
for eval_data in evaluations:
    if eval_data.get("symbol") == symbol and eval_data.get("horizon") == horizon:
        mape = eval_data.get("mape", 0) / 100  # Convert % to decimal
        if mape > 0:
            # Convert MAPE to accuracy: lower MAPE = higher accuracy
            accuracy_from_mape = 1.0 / (1.0 + mape)
        else:
            # Fallback to direction accuracy if MAPE not available
            accuracy_from_mape = 1.0 if eval_data.get("direction_correct") else 0.0
        mape_scores.append(accuracy_from_mape)

if mape_scores:
    accuracy = sum(mape_scores) / len(mape_scores)
else:
    # Fallback to direction accuracy
    accuracy = stats["correct"] / stats["total"]
```

**Impact**: More accurate representation of forecast quality.

---

## ⚠️ Medium Priority: Time-Decay Weighting

### Problem
All evaluations are weighted equally. Recent evaluations should be weighted more heavily.

### Fix Required

```python
import math
from datetime import datetime

decay_rate = 0.1  # Adjust based on desired decay speed

for eval_data in evaluations:
    days_ago = (datetime.now() - pd.to_datetime(eval_data["evaluation_date"])).days
    weight = math.exp(-decay_rate * days_ago)
    
    if eval_data.get("direction_correct"):
        weighted_correct += weight
    total_weight += weight

accuracy = weighted_correct / total_weight
```

**Impact**: Recent performance weighted more heavily.

---

## ⚠️ Medium Priority: Baseline Comparison

### Problem
No comparison against baseline models (Naive, ARIMA, ETS).

### Fix Required

**1. Create baseline table:**
```sql
CREATE TABLE IF NOT EXISTS baseline_forecast_accuracy (
    symbol_id UUID REFERENCES symbols(id),
    timeframe TEXT,
    baseline_type TEXT,  -- 'naive', 'arima', 'ets'
    accuracy_score NUMERIC,
    sample_size INT,
    last_updated TIMESTAMPTZ,
    PRIMARY KEY (symbol_id, timeframe, baseline_type)
);
```

**2. Update live_predictions to include baseline:**
```python
# Fetch baseline
baseline_result = (
    db.client.table("baseline_forecast_accuracy")
    .select("accuracy_score")
    .eq("symbol_id", symbol_id)
    .eq("timeframe", timeframe)
    .eq("baseline_type", "naive")
    .execute()
)

baseline_accuracy = baseline_result.data[0]["accuracy_score"] if baseline_result.data else 0.5

prediction_data = {
    ...
    "accuracy_score": accuracy,
    "baseline_accuracy": baseline_accuracy,
    "vs_baseline": accuracy - baseline_accuracy,
    ...
}
```

**Impact**: Can detect when model underperforms baseline.

---

## 📋 Implementation Plan

### Phase 1: Critical Fixes (Do First)
1. ✅ Add MAPE column to `forecast_evaluations`
2. ✅ Calculate MAPE in `evaluation_job.py`
3. ✅ Create `get_live_predictions()` Supabase function
4. ✅ Update `ValidationService` to use function or compute on-demand
5. ✅ Use MAPE-based accuracy in `populate_live_predictions.py` (if keeping manual)

### Phase 2: Medium Priority
6. ⚠️ Add time-decay weighting
7. ⚠️ Add baseline comparison table and logic

### Phase 3: Low Priority
8. ℹ️ Add SMAPE as alternative metric
9. ℹ️ Add confidence intervals for accuracy scores

---

## ✅ Summary

**Current Issues**:
- ❌ Missing MAPE metrics
- ❌ Manual live_predictions population
- ❌ Using direction accuracy instead of price accuracy
- ⚠️ No time-decay weighting
- ⚠️ No baseline comparison

**Recommended Fixes**:
1. Add MAPE to evaluations (migration + code)
2. Make live_predictions computed (Supabase function)
3. Use MAPE-based accuracy scores
4. Add time-decay weighting
5. Add baseline comparison

**Impact**: Industry-standard, more accurate forecast evaluation system.

---

**Status**: 🔧 **Fixes Required**  
**Priority**: High  
**Last Updated**: January 23, 2026
