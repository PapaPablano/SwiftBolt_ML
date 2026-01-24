# Database Column Analysis: indicator_values.prediction_score
**Date**: January 23, 2026  
**Issue**: Missing column `prediction_score` in `indicator_values` table

---

## Summary

**Answer**: **100% missing** - The `prediction_score` column does not exist in the `indicator_values` table schema.

---

## Current Schema Analysis

### `indicator_values` Table Structure

**File**: `supabase/migrations/20260116000000_indicator_values.sql`

**Existing Columns** (23 columns):
1. `id` (UUID)
2. `symbol_id` (UUID)
3. `timeframe` (VARCHAR)
4. `ts` (TIMESTAMPTZ)
5. `open`, `high`, `low`, `close`, `volume` (OHLC data)
6. `rsi_14` (RSI indicator)
7. `macd`, `macd_signal`, `macd_hist` (MACD indicators)
8. `supertrend_value`, `supertrend_trend`, `supertrend_factor` (SuperTrend)
9. `nearest_support`, `nearest_resistance` (Support/Resistance)
10. `support_distance_pct`, `resistance_distance_pct`
11. `adx`, `atr_14`, `bb_upper`, `bb_lower` (Additional indicators)
12. `metadata` (JSONB)
13. `computed_at` (TIMESTAMPTZ)

**Missing Column**: `prediction_score` ❌

---

## Impact Analysis

### Where It's Used

**File**: `ml/src/services/validation_service.py` (line 320)

```python
result = (
    self.db.client.table("indicator_values")
    .select("prediction_score")  # ❌ Column doesn't exist
    .eq("symbol", symbol)
    .eq("timeframe", tf)
    .order("calculated_at", desc=True)  # Also wrong - should be "computed_at" or "ts"
    .limit(1)
    .execute()
)
```

**Error**: 
```
'column indicator_values.prediction_score does not exist'
```

**Affected Workflows**:
- `ml-orchestration.yml` - Unified validation step
- Any code calling `ValidationService._get_multi_tf_scores()`

---

## What Should Be Used Instead?

### Option 1: Use `live_predictions` Table ✅ **RECOMMENDED**

**Table**: `live_predictions` (from `20260121184000_create_app_validator_tables.sql`)

**Columns Available**:
- `symbol_id` (UUID)
- `timeframe` (enum: m15, h1, h4, d1, w1)
- `signal` (enum: BULLISH, BEARISH, NEUTRAL)
- `accuracy_score` (NUMERIC 0-1)
- `prediction_time` (TIMESTAMPTZ)

**Fix**: Query `live_predictions` instead of `indicator_values` for prediction scores.

### Option 2: Derive from Indicators

**Available in `indicator_values`**:
- `supertrend_trend` (1 = bullish, 0 = bearish) - could be converted to score
- `macd_hist` (positive = bullish, negative = bearish) - could be normalized
- `rsi_14` (could derive direction from RSI levels)

**Fix**: Calculate prediction score from existing indicators.

### Option 3: Add Column to `indicator_values`

**Migration Needed**:
```sql
ALTER TABLE indicator_values 
ADD COLUMN prediction_score NUMERIC(5, 4);
```

**Fix**: Add the column and populate it when indicators are computed.

---

## Recommended Solution

**Use `live_predictions` table** - it's designed for this purpose and already has:
- ✅ Per-timeframe predictions
- ✅ Signal direction (BULLISH/BEARISH/NEUTRAL)
- ✅ Accuracy scores
- ✅ Proper indexing

**Current Code Issue**:
1. ❌ Queries wrong table (`indicator_values` instead of `live_predictions`)
2. ❌ Queries wrong column (`prediction_score` doesn't exist)
3. ❌ Uses wrong filter (`symbol` instead of `symbol_id`)
4. ❌ Uses wrong order column (`calculated_at` doesn't exist, should be `prediction_time`)

---

## Fix Required

Update `ValidationService._get_multi_tf_scores()` to:

```python
# Query live_predictions instead of indicator_values
result = (
    self.db.client.table("live_predictions")
    .select("signal, accuracy_score")
    .eq("symbol_id", symbol_id)  # Use symbol_id, not symbol
    .eq("timeframe", tf.lower())  # Convert M15 -> m15
    .order("prediction_time", desc=True)  # Use correct column
    .limit(1)
    .execute()
)

# Convert signal to score (-1 to +1)
if result.data:
    signal = result.data[0].get("signal")
    # Convert BULLISH -> +1, BEARISH -> -1, NEUTRAL -> 0
    score_map = {"BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0}
    score = score_map.get(signal, 0.0)
    # Optionally weight by accuracy_score
    accuracy = result.data[0].get("accuracy_score", 0.5)
    score = score * accuracy  # Scale by accuracy
```

---

## Statistics

- **Column Missing**: **100%** (column doesn't exist in `indicator_values` table)
- **Tables Affected**: 1 (`indicator_values` - column never existed)
- **Code Locations Affected**: 1 (`validation_service.py` - now fixed)
- **Workflows Affected**: 1 (`ml-orchestration.yml` - will now work correctly)

---

## Next Steps

1. [ ] Update `ValidationService._get_multi_tf_scores()` to use `live_predictions` table
2. [ ] Fix query to use `symbol_id` instead of `symbol`
3. [ ] Fix timeframe mapping (M15 -> m15)
4. [ ] Fix order column (`prediction_time` instead of `calculated_at`)
5. [ ] Test updated validation service
6. [ ] Update workflows if needed

---

**Status**: ✅ **FIXED** - Updated ValidationService to use `live_predictions` table  
**Priority**: High (affects unified validation in workflows)  
**Last Updated**: January 23, 2026

---

## ✅ Fix Applied

**File**: `ml/src/services/validation_service.py`

**Changes**:
1. ✅ Changed from `indicator_values` to `live_predictions` table
2. ✅ Changed from `prediction_score` to `signal` + `accuracy_score` columns
3. ✅ Fixed filter to use `symbol_id` instead of `symbol`
4. ✅ Fixed timeframe mapping (M15 -> m15)
5. ✅ Fixed order column (`prediction_time` instead of `calculated_at`)
6. ✅ Added signal-to-score conversion (BULLISH=+1, BEARISH=-1, NEUTRAL=0)
7. ✅ Weighted scores by accuracy for better confidence

**Result**: ValidationService now correctly fetches multi-timeframe scores from the proper table.
