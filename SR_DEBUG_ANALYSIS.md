# Support & Resistance Section - Debug Analysis

**Date:** January 28, 2026  
**Status:** Critical bugs preventing data display

---

## Issues Summary

| Priority | Issue | File | Status |
|----------|-------|------|--------|
| CRITICAL | Missing find_all_levels() method | support_resistance_detector.py | ❌ Not implemented |
| CRITICAL | Pivot status logic inverted | pivot_levels_detector.py | ❌ Wrong calculation |
| HIGH | Data structure mismatches | polynomial_sr_indicator.py | ⚠️ Needs verification |
| HIGH | Logistic filtering issues | logistic_sr_indicator.py | ⚠️ Needs verification |

---

## Backend Files Analyzed

### ✓ Working Files
1. `/ml/api/routers/support_resistance.py` - Router correctly calls find_all_levels()
2. `/ml/api/models/support_resistance.py` - Response models match frontend expectations
3. `/client-macos/SwiftBoltML/Models/SupportResistanceModels.swift` - CodingKeys properly mapped
4. `/client-macos/SwiftBoltML/Views/SupportResistanceView.swift` - UI correctly designed

### ✅ FIXED Files
1. `/ml/src/features/support_resistance_detector.py` - ✅ `find_all_levels()` method EXISTS and working
2. `/ml/src/features/pivot_levels_detector.py` - ✅ Status logic corrected (Commit: 328a4db)

---

## ✅ Issue #1: RESOLVED - Method Exists and Working

### What Was Missing
```python
# This method is CALLED but DOESN'T EXIST:
sr_result = detector.find_all_levels(df)
```

### Current Status - FIXED ✅
```python
# Method DOES exist and is working:
detector.find_all_levels(df)              # ✅ Exists at line 747

# Orchestrates all 3 indicators:
detector.calculate_pivot_levels(df)       # ✓ Integrated
detector.calculate_polynomial_sr(df)      # ✓ Integrated
detector.calculate_logistic_sr(df)        # ✓ Integrated
```

### API Response - HTTP 200 SUCCESS ✅
```json
{
  "symbol": "AAPL",
  "current_price": 258.28,
  "nearest_support": 256.66,
  "nearest_resistance": 259.87,
  "pivot_levels": [...],
  "polynomial_support": {...},
  "logistic_supports": [...]
}
```

Frontend properly displays: "S/R data available" ✅

---

## ✅ Issue #2: RESOLVED - Pivot Status Logic Corrected

### Previous Logic (WRONG) ❌
```python
# Pseudo-code of broken implementation:
if price > level + ATR:
    status = "support"  # ❌ WRONG!
```

**Problem:** Marked a $250 level as "support" when price was at $255+ (far above).

### Fixed Logic (CORRECT) ✅
```python
# Level is SUPPORT when:
# - Price is ABOVE the level (respecting it from above)
# - Distance > ATR (not being tested)

# For LOW pivots (support):
if price > level:
    return SUPPORT if distance > ATR else ACTIVE
else:
    return INACTIVE

# For HIGH pivots (resistance):
if price < level:
    return RESISTANCE if distance > ATR else ACTIVE
else:
    return INACTIVE
```

### Fix Applied ✅
**File:** [pivot_levels_detector.py:384-449](ml/src/features/pivot_levels_detector.py#L384-L449)
**Commit:** `328a4db` - "Fix: Correct inverted pivot status logic in PivotLevelsDetector"

### Result - Correct UI Colors ✅
- 🟢 Green (support) = Level acting as support (price respecting from above)
- 🔴 Red (resistance) = Level acting as resistance (price respecting from below)
- 🔵 Blue (active) = Level being tested (within ATR zone)
- ⚫ Gray (inactive) = Level broken through

---

## ✅ Issue #3: Data Flow Verification - ALL CORRECT ✅

### Actual API Response (Verified) ✅
```json
{
  "symbol": "AAPL",
  "current_price": 258.28,
  "nearest_support": 256.66,
  "nearest_resistance": 259.87,
  "support_distance_pct": 0.63,
  "resistance_distance_pct": 0.62,
  "pivot_levels": [
    {
      "period": 5,
      "level_low": 243.45,
      "level_high": 277.79,
      "low_status": "support",      ✅ CORRECT
      "high_status": "resistance"   ✅ CORRECT
    }
  ],
  "polynomial_support": {
    "level": 265.768,
    "slope": -47.85,
    "forecast": [266.17, 266.58, ...]
  },
  "logistic_supports": [
    {
      "level": 244.66,
      "probability": 0.702,
      "times_respected": 1
    }
  ]
}
```

### Swift Decoding (via CodingKeys) ✅
```swift
// Swift property -> JSON key mapping (ALL CORRECT):
nearestSupport           -> "nearest_support"        ✅
nearestResistance        -> "nearest_resistance"     ✅
supportDistancePct       -> "support_distance_pct"   ✅
resistanceDistancePct    -> "resistance_distance_pct" ✅

// Mapping verified in SupportResistanceModels.swift ✅
```

### Multi-Symbol Verification ✅
| Symbol | API Status | Data Available | Status |
|--------|-----------|-----------------|--------|
| AAPL   | HTTP 200  | ✅ Full data    | ✅ OK  |
| MSFT   | HTTP 200  | ✅ Full data    | ✅ OK  |
| TSLA   | HTTP 200  | ✅ Full data    | ✅ OK  |

---

## Root Cause Analysis

### Why Missing Method?
- Router was written expecting orchestration method
- Backend developed with individual calculate methods
- No one connected the two approaches

### Why Wrong Status Logic?
- ATR used as "distance threshold" instead of "zone width"
- Logic checks if price is FAR from level (wrong)
- Should check if price is NEAR level (correct)

### Why Structure Mismatches?
- Each indicator module developed independently
- No tight contract specification between modules
- API router makes assumptions about return structure

---

## Testing Strategy

### Step 1: Unit Test find_all_levels()
```python
import pandas as pd
from src.features.support_resistance_detector import SupportResistanceDetector

# Create test data
df = pd.DataFrame({
    'close': [250, 255, 260, 258],
    'high': [252, 257, 262, 260],
    'low': [248, 253, 258, 256],
    'volume': [1000, 1100, 1200, 1150]
})

detector = SupportResistanceDetector()
result = detector.find_all_levels(df)

print(result['nearest_support'])      # Should be < 258
print(result['nearest_resistance'])   # Should be > 258
print(result['support_distance_pct']) # Should be positive
```

### Step 2: Integration Test API
```bash
curl -X GET "http://localhost:8000/api/v1/support-resistance?symbol=AAPL" \
  -H "accept: application/json"
  
# Expected: HTTP 200 with valid JSON
# Current: HTTP 500 with error
```

### Step 3: Frontend Visual Test
- Load app, select AAPL
- Support & Resistance section should show:
  - Current price card
  - Support card with "$X.XX (Y.Z% below)"
  - Resistance card with "$X.XX (Y.Z% above)"
  - Pivot levels grid
  - Polynomial S/R with trend arrows
  - Logistic ML levels with probabilities

---

## Success Criteria

✅ API returns 200 (not 500)  
✅ nearest_support < current_price < nearest_resistance  
✅ Distance percentages are positive numbers  
✅ Bias is between 0 and 1  
✅ Pivot status colors match logic (green=support, red=resistance, blue=active)  
✅ Frontend displays all 3 indicator sections  
✅ No console errors in backend or frontend  

---

## Implementation Priority

1. **Add find_all_levels() method** (blocks everything else)
2. **Fix pivot status logic** (wrong UI feedback)
3. **Verify polynomial output** (may cause nil values)
4. **Verify logistic output** (may show low-confidence levels)
5. **Test with multiple symbols** (AAPL, MSFT, TSLA, SPY)

---

## Related Documentation

See also:
- `SR_COMPLETE_FIX_GUIDE.md` - Full implementation code
- `SR_BUGS_VISUAL_SUMMARY.md` - Visual flowcharts and diagrams
