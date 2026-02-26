# SwiftBolt ML: Support & Resistance - Complete Debug & Fix Guide

**Status:** Critical bugs identified - API endpoint crashing due to missing method

**Date:** January 28, 2026

---

## 🔴 CRITICAL BUG #1: Missing `find_all_levels()` Method

### Problem
- **File:** `/ml/src/features/support_resistance_detector.py`
- **Status:** ❌ METHOD DOES NOT EXIST but IS BEING CALLED
- **Impact:** API returns 500 error on every request

The API router (`/ml/api/routers/support_resistance.py` line 52) calls:
```python
sr_result = detector.find_all_levels(df)
```

But this method is **NOT DEFINED** in the SupportResistanceDetector class.

### Solution Code

**Add this method to SupportResistanceDetector class in support_resistance_detector.py:**

```python
def find_all_levels(self, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate all S/R levels from 3 indicators and aggregate results.
    
    Returns:
        Dict with nearest support/resistance, distances, bias, and all levels
    """
    try:
        current_price = float(df["close"].iloc[-1])
        logger.info(f"[SR] Finding all levels for price ${current_price:.2f}")
        
        # Calculate each indicator
        pivot_result = self.calculate_pivot_levels(df)
        poly_result = self.calculate_polynomial_sr(df)
        logistic_result = self.calculate_logistic_sr(df)
        
        # Aggregate all support and resistance levels
        all_supports = []
        all_resistances = []
        
        # Extract from Pivot Levels
        for level in pivot_result.get("pivot_levels", []):
            if level.get("level_low"):
                all_supports.append(float(level["level_low"]))
            if level.get("level_high"):
                all_resistances.append(float(level["level_high"]))
        
        # Extract from Polynomial
        if poly_result.get("support"):
            all_supports.append(float(poly_result["support"]))
        if poly_result.get("resistance"):
            all_resistances.append(float(poly_result["resistance"]))
        
        # Extract from Logistic
        for level_data in logistic_result.get("support_levels", []):
            if level_data.get("level"):
                all_supports.append(float(level_data["level"]))
        for level_data in logistic_result.get("resistance_levels", []):
            if level_data.get("level"):
                all_resistances.append(float(level_data["level"]))
        
        # Find nearest support (highest level below price)
        valid_supports = [s for s in all_supports if s < current_price]
        nearest_support = max(valid_supports) if valid_supports else None
        
        # Find nearest resistance (lowest level above price)
        valid_resistances = [r for r in all_resistances if r > current_price]
        nearest_resistance = min(valid_resistances) if valid_resistances else None
        
        # Calculate distances as percentages
        support_distance_pct = None
        if nearest_support:
            support_distance_pct = round(((current_price - nearest_support) / current_price) * 100, 2)
        
        resistance_distance_pct = None
        if nearest_resistance:
            resistance_distance_pct = round(((nearest_resistance - current_price) / current_price) * 100, 2)
        
        # Calculate bias (0-1, higher = more bullish)
        bias = None
        if support_distance_pct and resistance_distance_pct:
            bias = round(resistance_distance_pct / (support_distance_pct + resistance_distance_pct), 2)
        
        return {
            "current_price": round(current_price, 2),
            "nearest_support": round(nearest_support, 2) if nearest_support else None,
            "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
            "support_distance_pct": support_distance_pct,
            "resistance_distance_pct": resistance_distance_pct,
            "bias": bias,
            "all_supports": sorted(list(set(all_supports))),
            "all_resistances": sorted(list(set(all_resistances))),
            "indicators": {
                "pivot_levels": pivot_result,
                "polynomial": poly_result,
                "logistic": logistic_result,
            }
        }
        
    except Exception as e:
        logger.error(f"[SR] Error in find_all_levels: {str(e)}", exc_info=True)
        return {
            "current_price": float(df["close"].iloc[-1]) if not df.empty else 0,
            "nearest_support": None,
            "nearest_resistance": None,
            "support_distance_pct": None,
            "resistance_distance_pct": None,
            "bias": None,
            "all_supports": [],
            "all_resistances": [],
            "indicators": {}
        }
```

**Insert this method AFTER `calculate_logistic_sr()` method (around line 180)**

---

## 🔴 CRITICAL BUG #2: Pivot Status Logic Inverted

### Problem
Status calculation is backwards - marks level as "support" when price is FAR ABOVE it.

Should be: "support" when price is NEAR or RESPECTING the level.

### Solution

Find the pivot status calculation in `pivot_levels_detector.py` and fix:

```python
def _calculate_pivot_status(
    current_price: float,
    pivot_level: float,
    atr: float,
    is_high: bool  # True = resistance, False = support
) -> PivotStatus:
    """Determine status based on price position relative to level."""
    atr_zone = atr
    distance = abs(current_price - pivot_level)
    price_above = current_price > pivot_level
    
    if is_high:  # This is RESISTANCE
        if price_above:
            return PivotStatus.ACTIVE if distance <= atr_zone else PivotStatus.INACTIVE
        else:
            return PivotStatus.ACTIVE if distance <= atr_zone else PivotStatus.RESISTANCE
    else:  # This is SUPPORT
        if price_above:
            return PivotStatus.ACTIVE if distance <= atr_zone else PivotStatus.SUPPORT
        else:
            return PivotStatus.ACTIVE if distance <= atr_zone else PivotStatus.INACTIVE
```

Key: ACTIVE = testing (within ATR), SUPPORT/RESISTANCE = respecting (outside ATR)

---

## 🟡 Issue #3: Verify Output Structures

### Polynomial must return:
```python
{
    "support": float,
    "support_slope": float,
    "support_trend": "rising"|"falling"|"flat",
    "forecast_support": [floats],
    "resistance": float,
    "resistance_slope": float,
    "resistance_trend": "rising"|"falling"|"flat",
    "forecast_resistance": [floats]
}
```

### Logistic must return:
```python
{
    "support_levels": [{"level": float, "probability": float, "times_respected": int}],
    "resistance_levels": [{"level": float, "probability": float, "times_respected": int}],
    "signals": [strings]
}
```

---

## ✅ Testing Checklist

1. Test endpoint: `curl "http://localhost:8000/api/v1/support-resistance?symbol=AAPL"`
2. Should return 200 (not 500)
3. Verify: nearest_support < current_price < nearest_resistance
4. Check UI displays support/resistance cards with distances
5. Pivot levels show with correct colors

---

## Timeline: ~1.5 hours
- Add find_all_levels(): 30 min
- Fix pivot status: 20 min  
- Verify structures: 15 min
- Test: 15 min
