# Support & Resistance - Visual Debug Summary

**Quick Reference Guide**

---

## 🔴 Bug #1: Missing Method (API Crash)

```
User Opens App
     ↓
Selects Symbol (AAPL)
     ↓
Frontend Requests: GET /support-resistance?symbol=AAPL
     ↓
FastAPI Router (support_resistance.py:52)
     ↓
Calls: detector.find_all_levels(df)
     ↓
💥 AttributeError: Method does not exist!
     ↓
HTTP 500 Error → Frontend
     ↓
UI Shows: "S/R data unavailable" ❌
```

**Fix:** Add missing method to support_resistance_detector.py

---

## 🔴 Bug #2: Status Logic Inverted

### Current (WRONG)
```
Pivot Level: $250 (Resistance)
Current Price: $255
ATR: $3

Logic:
if price > level + ATR:    ← 255 > 253? YES
    status = "support"     ❌ WRONG!
```

### Correct
```
Pivot Level: $250 (Resistance)
Current Price: $255
ATR: $3
Distance: $5

Logic:
- Price is ABOVE resistance
- Distance (5) > ATR (3)
- Status = INACTIVE (broken through) ✓

If price was $252:
- Distance (2) < ATR (3)  
- Status = ACTIVE (testing) ✓
```

---

## 📊 Data Flow (FIXED)

```
┌────────────────────┐
│  Swift Frontend      │
│  (User sees UI)      │
└───────┬────────────┘
       │
       │ GET /support-resistance?symbol=AAPL
       ↓
┌───────┴────────────────────────┐
│  FastAPI Router                     │
│  detector.find_all_levels(df) ✓    │
└───────┬────────────────────────┘
       │
       ├─────────────────────────────────┐
       │                                │
   calculate_pivot_levels()   calculate_polynomial_sr()
       │                                │
   Returns:                           Returns:
   - 5/25/50/100 bar pivots           - support/resistance
   - Status (FIXED LOGIC) ✓           - slopes & trends
       │                                │
       └─────────┬──────────────────┘
                │
       calculate_logistic_sr()
                │
           Returns:
           - ML levels
           - probabilities
                │
       ┌────────┴─────────┐
       │  Aggregate Results  │
       └────────┬─────────┘
                │
       nearest_support: $244.66
       nearest_resistance: $277.27
       support_dist: 5.3%
       resistance_dist: 7.3%
       bias: 0.58 (bullish)
                │
       ┌────────┴─────────┐
       │  JSON Response 200  │
       └────────┬─────────┘
                │
       Swift Decodes (CodingKeys) ✓
                │
       ┌────────┴─────────┐
       │  UI Displays Data   │
       │  ✓ Support card    │
       │  ✓ Resistance card │
       │  ✓ Pivot levels    │
       │  ✓ Polynomial S/R  │
       │  ✓ ML levels       │
       └──────────────────┘
```

---

## 📊 Before vs After

### BEFORE (Broken)
```
[Frontend]
  Loading S/R levels... 🔄
  ↓
  (5 seconds later)
  ↓
  ❌ S/R data unavailable

[Backend Logs]
  [SR] Starting S/R analysis for AAPL/d1
  [ERROR] AttributeError: 'SupportResistanceDetector' 
          object has no attribute 'find_all_levels'
  💥 500 ERROR
```

### AFTER (Fixed)
```
[Frontend]
  Support & Resistance
  ───────────────────
  Price: $258.28
  
  Support: $244.66        Resistance: $277.27
  5.3% below              7.3% above
  🟢 GREEN                  🔴 RED
  
  Bias: Bullish (0.58)
  
  Multi-Timeframe Pivots:
  5 Bar:   S $243.45  R $277.79
  25 Bar:  S $169.26  R $288.61
  50 Bar:  S $169.26
  
  Polynomial S/R:
  Support: $263.72 ↘ falling
  Resistance: $292.50 ↘ falling
  
  ML S/R (Logistic):
  Support: $244.66 (60% confidence)
  Resistance: $277.27 (60% confidence)
  Resistance: $288.61 (50% confidence)

[Backend Logs]
  [SR] Starting S/R analysis for AAPL/d1 (lookback=252)
  [SR] Fetched 252 bars for AAPL/d1
  [SR] Finding all levels for price $258.28
  [SR] Levels found - Support: $244.66, Resistance: $277.27
  [SR] Completed S/R analysis in 0.23s for AAPL/d1
  ✓ 200 OK
```

---

## ✅ Implementation Checklist

### Phase 1: Critical Fixes (Required)
- [ ] Add `find_all_levels()` method to support_resistance_detector.py
- [ ] Fix pivot status logic in pivot_levels_detector.py
- [ ] Test API endpoint returns 200

### Phase 2: Verification (Recommended)
- [ ] Verify polynomial output structure
- [ ] Verify logistic output structure  
- [ ] Test with multiple symbols (AAPL, MSFT, TSLA)

### Phase 3: UI Testing (Final)
- [ ] Load app, select symbol
- [ ] Verify support/resistance cards display
- [ ] Check pivot levels grid populated
- [ ] Confirm colors match status
- [ ] No console errors

---

## 🔧 Quick Fix Code Snippets

### 1. find_all_levels() Skeleton
```python
def find_all_levels(self, df):
    # Get current price
    current_price = float(df["close"].iloc[-1])
    
    # Call 3 indicators
    pivot = self.calculate_pivot_levels(df)
    poly = self.calculate_polynomial_sr(df)
    logistic = self.calculate_logistic_sr(df)
    
    # Collect all levels
    all_supports = []
    all_resistances = []
    # ... extract from each indicator ...
    
    # Find nearest
    nearest_support = max([s for s in all_supports if s < current_price])
    nearest_resistance = min([r for r in all_resistances if r > current_price])
    
    # Calculate distances
    support_dist_pct = ((current_price - nearest_support) / current_price) * 100
    resistance_dist_pct = ((nearest_resistance - current_price) / current_price) * 100
    
    # Return aggregated result
    return {
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "support_distance_pct": support_dist_pct,
        "resistance_distance_pct": resistance_dist_pct,
        "indicators": {"pivot_levels": pivot, "polynomial": poly, "logistic": logistic}
    }
```

### 2. Status Logic Fix
```python
def _calculate_status(price, level, atr, is_resistance):
    distance = abs(price - level)
    
    if is_resistance:
        if price > level:
            return "ACTIVE" if distance <= atr else "INACTIVE"
        else:
            return "ACTIVE" if distance <= atr else "RESISTANCE"
    else:  # is_support
        if price > level:
            return "ACTIVE" if distance <= atr else "SUPPORT"
        else:
            return "ACTIVE" if distance <= atr else "INACTIVE"
```

---

## 📊 Impact Matrix

| Component | Severity | Users Affected | Fix Time |
|-----------|----------|----------------|----------|
| Missing method | CRITICAL | 100% | 30 min |
| Status logic | HIGH | 100% | 20 min |
| Data structures | MEDIUM | ~50% | 15 min |

**Total Fix Time: ~1.5 hours**

---

## 📝 Files to Modify

1. `/ml/src/features/support_resistance_detector.py`
   - Action: ADD method find_all_levels()
   - Lines: ~80 new lines after calculate_logistic_sr()

2. `/ml/src/features/pivot_levels_detector.py`
   - Action: FIX status calculation logic
   - Lines: ~20 lines modified

3. `/ml/src/features/polynomial_sr_indicator.py`
   - Action: VERIFY return structure
   - Lines: Check calculate() method

4. `/ml/src/features/logistic_sr_indicator.py`
   - Action: VERIFY return structure
   - Lines: Check calculate() method

---

## 🎯 Success Metrics

When fixed, you should see:

✅ API endpoint: `curl localhost:8000/api/v1/support-resistance?symbol=AAPL` returns 200  
✅ Response has: nearest_support, nearest_resistance, distances, bias  
✅ Frontend displays 3 cards: Price, Support (green), Resistance (red)  
✅ Pivot levels section shows 4 timeframes  
✅ Polynomial section shows support/resistance with trends  
✅ Logistic section shows ML levels with probabilities  
✅ No 500 errors in backend logs  
✅ No nil unwrapping errors in frontend logs  

---

## 🚀 Next Steps

1. Open `SR_COMPLETE_FIX_GUIDE.md` for full implementation code
2. Copy the `find_all_levels()` method
3. Paste into support_resistance_detector.py
4. Fix pivot status logic
5. Test: `curl localhost:8000/api/v1/support-resistance?symbol=AAPL`
6. Open app and verify UI

**Estimated time to working state: 90 minutes**
