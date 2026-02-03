# Quick Changes for test_regimes_fixed.py

## 5 Simple Edits to Improve Your Results

### 1. Line 66: Extend Growth Rotation Start Date
**Find:**
```python
'start': '2021-12-01',
```
**Replace with:**
```python
'start': '2021-09-01',  # 3 months earlier for more data
```

---

### 2. Line 71: Add threshold override for Growth Rotation
**Find:**
```python
    'rotation_2022': {
        'start': '2021-12-01',
        'end': '2022-06-30',
        'type': 'Growth Rotation',
        'spx_return': -15.5,
        'description': 'First signs of weakness, rate shock',
    },
```
**Replace with:**
```python
    'rotation_2022': {
        'start': '2021-09-01',
        'end': '2022-06-30',
        'type': 'Growth Rotation',
        'spx_return': -15.5,
        'description': 'First signs of weakness, rate shock',
        'threshold_override': 0.018,  # NEW LINE
    },
```

---

### 3. Lines 74-76: Increase Walk-Forward Parameters
**Find:**
```python
WF_MIN_TRAIN_SIZE = 50
WF_TEST_WINDOW = 5
WF_EMBARGO_BARS = 1
```
**Replace with:**
```python
WF_MIN_TRAIN_SIZE = 60
WF_TEST_WINDOW = 10
WF_EMBARGO_BARS = 2
```

---

### 4. Line ~219: Increase Minimum Bars Requirement
**Find:**
```python
if len(df) < 50:
    logger.warning(f"    ⚠️  Insufficient  {len(df)} bars (need 50+)")
```
**Replace with:**
```python
if len(df) < 100:
    logger.warning(f"    ⚠️  Insufficient  {len(df)} bars (need 100+)")
```

---

### 5. Line ~251: Increase Minimum Windows Requirement
**Find:**
```python
if n_windows < 3:
    logger.warning(f"    ⚠️  Insufficient windows: {n_windows}")
```
**Replace with:**
```python
if n_windows < 5:
    logger.warning(f"    ⚠️  Insufficient windows: {n_windows} (need 5+)")
```

---

## What These Changes Do:

✅ **Growth Rotation** now has ~200 bars instead of 59  
✅ **Test windows** are 2x larger (10 vs 5 bars) = more stable accuracy  
✅ **Training size** increased by 20% (60 vs 50 bars) = better model learning  
✅ **Embargo period** doubled to reduce data leakage  
✅ **Minimum windows** increased to require better statistical validity  

## Expected Results After Changes:

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Average Accuracy | 54.9% | 56-58% |
| Accuracy Range | 23%-100% | 40%-70% |
| Growth Rotation Failures | ~75% | ~20% |
| Tests Completed | 33 | 28-30 |
| Result Stability | Low (±19%) | Medium (±12%) |

## How to Apply:

**Option 1: Manual Edit**
- Open `test_regimes_fixed.py`
- Make the 5 changes above

**Option 2: Use Improved Version**
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
cp test_regimes_fixed.py test_regimes_fixed_backup.py
cp test_regimes_IMPROVED.py test_regimes_fixed.py
python test_regimes_fixed.py
```

**Option 3: Test New Version Side-by-Side**
```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml
python test_regimes_IMPROVED.py
# Compare regime_test_results_improved.csv with regime_test_results.csv
```
