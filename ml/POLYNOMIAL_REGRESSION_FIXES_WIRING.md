# Polynomial Regression Fixes: Wiring & Architecture

**Status**: ✅ All fixes properly wired into web charts, APIs, and ML pipeline
**Date**: 2026-01-28

---

## Executive Summary

Your polynomial regression fixes have been applied to the **primary production implementation** used across all systems:

| Component | Implementation | Status | Details |
|-----------|---|---|---|
| **Web API** | `PolynomialSRIndicator` | ✅ Already correct | Separate coefficients per curve |
| **ML Features** | `SRPolynomialRegressor` | ✅ Fixed | Separate normalization params added |
| **Chart Viz** | `SRPolynomialRegressor` | ✅ Fixed | Uses corrected version |
| **Tests** | Comprehensive suite | ✅ 19/19 pass | All fixes validated |

---

## Architecture Map

### 1. Web/API Layer → Web Charts

```
Frontend (Web UI)
    ↓
API Endpoint: /support-resistance (support_resistance.py:39)
    ↓
SupportResistanceDetector.find_all_levels()
    ↓
PolynomialSRIndicator.calculate()  ← Uses RegressionCoefficients class
    ↓
Returns: {
  "indicators": {
    "polynomial": {
      "current_support": float,
      "current_resistance": float,
      "support_slope": float,
      "resistance_slope": float,
      "forecast_support": [float],
      "forecast_resistance": [float]
    }
  }
}
    ↓
Frontend receives and renders chart
```

**File**: [ml/api/routers/support_resistance.py:39](/ml/api/routers/support_resistance.py)
**Polynomial Component**: [ml/src/features/polynomial_sr_indicator.py:225](/ml/src/features/polynomial_sr_indicator.py#L225)

**Status**: ✅ **ALREADY CORRECT**
- Uses `RegressionCoefficients` class (line 64)
- Each coefficient stores its own `x_min` and `x_max` (lines 68-69)
- No shared state between support and resistance
- Slope scaling: `compute_slope()` method already returns correct per-bar values

---

### 2. ML Feature Pipeline

```
Feature Engineering (technical_indicators.py:203)
    ↓
SRPolynomialRegressor.add_polynomial_features()
    ↓
Fits curves and extracts features:
  - poly_support: Current support level
  - poly_resistance: Current resistance level
  - support_slope: Trend direction (price/bar)
  - resistance_slope: Trend direction (price/bar)
    ↓
Features added to DataFrame for ML model training
```

**File**: [ml/src/features/technical_indicators.py:203](/ml/src/features/technical_indicators.py#L203)
**Polynomial Component**: [ml/src/features/sr_polynomial.py:23](/ml/src/features/sr_polynomial.py#L23)

**Status**: ✅ **JUST FIXED**
- Now has separate `_support_x_min/max` and `_resistance_x_min/max` (lines 57-60)
- `predict_level()` uses curve type to select correct normalization (line 153)
- `compute_slope()` scales slopes to bar space (line 218)

---

### 3. Chart Visualization Pipeline

```
Visualization Code
    ↓
polynomial_sr_chart.py (line 863)
    ↓
Imports: from src.features.sr_polynomial import SRPolynomialRegressor
    ↓
FluxChartVisualizer.plot_polynomial_sr()
    ↓
Generates TradingView-style chart with:
  - Candlesticks
  - Polynomial curves (smooth)
  - Pivot markers
  - Signal indicators
  - Volume panel
```

**File**: [ml/src/visualization/polynomial_sr_chart.py:863](/ml/src/visualization/polynomial_sr_chart.py#L863)
**Polynomial Component**: [ml/src/features/sr_polynomial.py:23](/ml/src/features/sr_polynomial.py#L23)

**Status**: ✅ **USES FIXED VERSION**
- Directly imports `SRPolynomialRegressor` from fixed file
- Gets all corrections (separate normalization, slope scaling)

---

## Two Polynomial Implementations

You have **two separate polynomial regression implementations**, each serving different purposes:

### Implementation 1: `PolynomialSRIndicator` (polynomial_sr_indicator.py)

**Purpose**: Real-time S/R calculation for web API
**Used By**:
- `SupportResistanceDetector.calculate_polynomial_sr()` (line 130)
- Web API endpoint `/support-resistance` (support_resistance.py)

**Architecture**:
```python
class RegressionCoefficients:
    """Each coefficient has its own x_min/x_max"""
    values: List[float]
    x_min: float  ← Separate per coefficient
    x_max: float  ← Separate per coefficient

    def predict(self, x: float):
        """Uses self.x_min/x_max for normalization"""
        x_norm = self.normalize_x(x)  # Uses own range
        ...
```

**Status**: ✅ **Already Correct**
- Support and resistance each get their own `RegressionCoefficients` object
- Each object has its own `x_min` and `x_max`
- No shared state means independent normalization automatically

---

### Implementation 2: `SRPolynomialRegressor` (sr_polynomial.py)

**Purpose**: Polynomial S/R for ML features and chart visualization
**Used By**:
- `technical_indicators.add_sr_features()` (line 203)
- `polynomial_sr_chart.py` (line 863)
- Example scripts for testing

**Architecture (Before Fix)**:
```python
class SRPolynomialRegressor:
    """Had shared normalization params"""
    self._x_min: float = 0      ← SHARED between curves!
    self._x_max: float = 1      ← SHARED between curves!
```

**Architecture (After Fix)**:
```python
class SRPolynomialRegressor:
    """Now has separate params"""
    self._support_x_min: float = 0.0   ← Support only
    self._support_x_max: float = 1.0   ← Support only
    self._resistance_x_min: float = 0.0 ← Resistance only
    self._resistance_x_max: float = 1.0 ← Resistance only
```

**Status**: ✅ **Just Fixed**
- All three issues resolved (separate normalization, curve-type awareness, slope scaling)
- All 19 tests pass
- Ready for production use

---

## Code Flow: End-to-End

### Scenario: User opens chart in web UI

1. **Frontend** makes request to `/support-resistance?symbol=AAPL&timeframe=d1`
2. **API Router** (support_resistance.py:39) calls:
   ```python
   detector = SupportResistanceDetector()
   sr_result = detector.find_all_levels(df)  # Line 81
   ```
3. **Detector** (support_resistance_detector.py:130) calls:
   ```python
   poly_result = self.polynomial_indicator.calculate(df)
   ```
4. **PolynomialSRIndicator** (polynomial_sr_indicator.py:247) returns:
   ```python
   {
       "current_support": 169.25,      # Computed with separate normalization ✅
       "current_resistance": 172.40,   # Computed with separate normalization ✅
       "support_slope": 0.0234,        # Per-bar slope ✅
       "resistance_slope": -0.0156     # Per-bar slope ✅
   }
   ```
5. **API Response** includes these values in `PolynomialLevel` objects
6. **Frontend** receives and renders on chart

**All data is correct because**: `PolynomialSRIndicator` already uses separate coefficient objects ✅

---

### Scenario: User generates analysis chart with visualization

1. **Visualization Code** imports:
   ```python
   from src.features.sr_polynomial import SRPolynomialRegressor  # Fixed version
   ```
2. **Creates regressor**:
   ```python
   regressor = SRPolynomialRegressor(degree=2, min_points=4)
   ```
3. **Fits curves** with fixed implementation:
   ```python
   regressor.fit_support_curve(pivots)   # Uses _support_x_min/max ✅
   regressor.fit_resistance_curve(pivots) # Uses _resistance_x_min/max ✅
   ```
4. **Predicts levels** with curve type awareness:
   ```python
   sup = regressor.predict_level(coeffs, index, curve_type="support")    # Correct normalization ✅
   res = regressor.predict_level(coeffs, index, curve_type="resistance") # Correct normalization ✅
   ```
5. **Computes slopes** with scaling:
   ```python
   sup_slope = regressor.compute_slope(coeffs, curve_type="support")    # Scaled to bar space ✅
   res_slope = regressor.compute_slope(coeffs, curve_type="resistance") # Scaled to bar space ✅
   ```
6. **Renders chart** with correct S/R levels and slopes

**All data is correct because**: We fixed the three issues ✅

---

## Verification Checklist

### ✅ Separate Normalization
- [x] `SRPolynomialRegressor` has separate `_support_x_min/max` and `_resistance_x_min/max`
- [x] `PolynomialSRIndicator` uses separate coefficient objects per curve
- [x] Test: `test_support_and_resistance_independent` passes

### ✅ Curve-Type Awareness
- [x] `predict_level()` accepts `curve_type` parameter
- [x] `compute_slope()` accepts `curve_type` parameter
- [x] Predictions use correct normalization per curve type
- [x] Test: `test_different_ranges_different_predictions` passes

### ✅ Slope Scaling
- [x] Slopes computed as `slope_norm / x_range`
- [x] Returns per-bar slope (price/bar), not normalized space values
- [x] Test: `test_slope_magnitude_matches_real_slope` passes

### ✅ Web Integration
- [x] API endpoint receives correct polynomial levels
- [x] API endpoint receives correct slopes in per-bar units
- [x] Frontend can render using correct values

### ✅ ML Integration
- [x] `technical_indicators.py` uses fixed `SRPolynomialRegressor`
- [x] Features include correct support/resistance distances
- [x] Features include correct slope directions

### ✅ Visualization Integration
- [x] `polynomial_sr_chart.py` imports fixed `SRPolynomialRegressor`
- [x] Charts display using correct polynomial curves
- [x] Charts include correct slope values

---

## Files Modified & Status

| File | Change | Status |
|------|--------|--------|
| `ml/src/features/sr_polynomial.py` | Fixed separate normalization + slope scaling | ✅ Production Ready |
| `ml/src/tests/test_sr_polynomial_fixes.py` | Comprehensive test suite (19 tests) | ✅ All Pass |
| `ml/src/features/polynomial_sr_indicator.py` | No changes needed (already correct) | ✅ Already Good |
| `ml/api/routers/support_resistance.py` | No changes needed | ✅ Uses correct PolynomialSRIndicator |
| `ml/src/features/technical_indicators.py` | No changes needed | ✅ Now uses fixed SRPolynomialRegressor |
| `ml/src/visualization/polynomial_sr_chart.py` | No changes needed | ✅ Now uses fixed SRPolynomialRegressor |

---

## Running Tests

```bash
cd ~/SwiftBolt_ML/ml

# Run all polynomial regression fix tests
python -m pytest src/tests/test_sr_polynomial_fixes.py -v

# Run specific test category
python -m pytest src/tests/test_sr_polynomial_fixes.py::TestSlopeScaling -v

# Run all tests with coverage
python -m pytest src/tests/test_sr_polynomial_fixes.py --cov=src/features/sr_polynomial
```

**Result**: All 19 tests pass ✅

---

## Key Guarantees

After these fixes:

1. **Data Point Translation**: Matches TradingView's Flux Charts design exactly
   - Support and resistance pivots are translated independently
   - Each curve uses its own bar-index coordinate system
   - Predictions at any bar reflect correct S/R levels

2. **Slope Values**: Are true per-bar changes (price/bar)
   - NOT normalized space artifacts
   - Can be directly interpreted as: "Support is rising 0.05 dollars per bar"
   - Consistent with Swift design specification

3. **Web API**: Serves correct S/R data to frontend
   - Through `PolynomialSRIndicator` (already correct)
   - All calculations use proper normalization

4. **ML Pipeline**: Uses correct features for model training
   - Through `SRPolynomialRegressor` (now fixed)
   - Features accurately represent S/R dynamics

5. **Chart Visualization**: Renders correct technical analysis
   - Through `SRPolynomialRegressor` (now fixed)
   - Charts match TradingView aesthetic and accuracy

---

## Summary

✅ **All systems are now properly wired to use the fixed polynomial regression implementation**

- **Web API**: Uses `PolynomialSRIndicator` (already correct)
- **ML Pipeline**: Uses fixed `SRPolynomialRegressor`
- **Chart Visualization**: Uses fixed `SRPolynomialRegressor`
- **Tests**: All 19 tests pass, validating all fixes

The fixes ensure that support and resistance curves are translated and scaled **exactly as designed**, matching the TradingView specification and your Swift implementation.
