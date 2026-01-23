# Score Capping Fix - 2026-01-23

## Issue
Component scores in the options ranking system were not being capped at 100 before applying weights, which caused:
- **Component domination**: Value Score at 255/100 × 35% = 89.3, overwhelming other components
- **Weight distortion**: Carefully chosen weights (40%, 35%, 25%) lost their intended proportional effect
- **Interpretability loss**: Scores >100 confused the "perfect score" meaning

## Research Finding
According to best practices for weighted scoring systems (researched via Perplexity):
> "Raw scores should typically be capped or clipped to the expected scale range (e.g., 0-100) before normalization and weighting to preserve intended scale boundaries and prevent outliers from distorting the system."

## Fixes Applied

### 1. Added Score Capping to Component Calculations

**File**: `ml/src/models/options_momentum_ranker.py`

#### a. Value Score (line ~709-711)
```python
# Before:
df["value_score"] = (
    df["iv_rank_score"] * self.IV_RANK_WEIGHT + df["spread_score"] * self.SPREAD_WEIGHT
)

# After:
df["value_score"] = (
    df["iv_rank_score"] * self.IV_RANK_WEIGHT + df["spread_score"] * self.SPREAD_WEIGHT
).clip(0, 100)
```

#### b. Momentum Score (line ~969)
```python
# Before:
df["momentum_score"] = 50 + (raw_momentum - 50) * liq_conf

# After:
df["momentum_score"] = (50 + (raw_momentum - 50) * liq_conf).clip(0, 100)
```

#### c. Catalyst Score (line ~1313)
```python
# Before:
return catalyst_score

# After:
return catalyst_score.clip(0, 100)
```

#### d. Underlying Metrics Integration (line ~1118-1121)
```python
# Before:
df["momentum_score"] = (
    df["momentum_score"] * (1 - underlying_weight)
    + underlying_score * underlying_weight
)

# After:
df["momentum_score"] = (
    df["momentum_score"] * (1 - underlying_weight)
    + underlying_score * underlying_weight
).clip(0, 100)
```

#### e. IV Staleness Penalty (line ~421)
```python
# Before:
df["value_score"] *= (1 - staleness_penalty)

# After:
df["value_score"] = (df["value_score"] * (1 - staleness_penalty)).clip(0, 100)
```

#### f. Temporal Smoothing (line ~499)
```python
# Before:
current.at[idx, "momentum_score"] = smoothed

# After:
current.at[idx, "momentum_score"] = np.clip(smoothed, 0, 100)
```

### 2. Already Capped (No Changes Needed)
These component scores already had proper capping:
- ✅ `entry_value_score` (line 1588): `.clip(0, 100)`
- ✅ `greeks_score` (line 1352): `.clip(0, 100)`
- ✅ `profit_protection_score` (line 1693): `.clip(0, 100)`
- ✅ `deterioration_score` (line 1739): `.clip(0, 100)`
- ✅ `time_urgency_score` (line 1781): `.clip(0, 100)`

### 3. Updated Documentation
Added "SCORE CAPPING" section to the module docstring explaining:
- Why capping is necessary
- When it's applied (before weighting)
- What it prevents (domination, distortion, interpretability loss)

## Impact

### Before Fix:
```
Value Score: 255/100 × 35% = 89.3
Momentum Score: 47/100 × 40% = 18.8
Greeks Score: 0/100 × 25% = 0.0
-----------------------------------------
Composite Rank: 108.1 → clipped to 100
```
❌ Value Score dominates even though Momentum has higher weight!

### After Fix:
```
Value Score: 100/100 × 35% = 35.0
Momentum Score: 47/100 × 40% = 18.8
Greeks Score: 0/100 × 25% = 0.0
-----------------------------------------
Composite Rank: 53.8
```
✅ Weights now properly reflect their intended importance!

## Next Steps

### 1. ✅ Code Changes Applied
All score capping logic has been added to the ranking system.

### 2. ⏳ Regenerate Rankings Data
The existing data in the database was generated WITHOUT score capping and needs to be regenerated.

**To trigger a data refresh:**
```bash
# Option A: Via Supabase edge function (recommended)
curl -X POST https://<project-ref>.supabase.co/functions/v1/trigger-ranking-job \
  -H "Authorization: Bearer <anon-key>" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'

# Option B: Run Python job directly
cd ml
python -m src.options_ranking_job --symbol AAPL --mode monitor
```

### 3. Verify in UI
After regenerating the data:
1. Open the macOS app
2. Navigate to Options → ML Ranker
3. Select a contract with previously high value scores
4. Check Contract Workbench → Why Ranked tab
5. Verify:
   - Value Score ≤ 100
   - Momentum Score ≤ 100
   - Greeks Score ≤ 100
   - Composite Rank accurately reflects weighted combination

## Testing Checklist
- [ ] Trigger ranking job for AAPL
- [ ] Verify all component scores ≤ 100 in database
- [ ] Check UI displays corrected scores
- [ ] Verify composite ranks are more balanced
- [ ] Test all three ranking modes (ENTRY, EXIT, MONITOR)
- [ ] Confirm weights now properly control component importance

## Mathematical Guarantee
With score capping in place:
```
Max Composite = (100 × 0.40) + (100 × 0.35) + (100 × 0.25) = 100 ✓
```
No single component can exceed its weighted contribution to the final score.
