# Support & Resistance Integration Plan for Forecasting

## Overview

This document outlines the plan for integrating Support & Resistance (S/R) levels into the ML forecasting system to improve price level recommendations and prediction accuracy.

## Current Implementation Status

### ✅ Completed

1. **SupportResistanceDetector Class** (`ml/src/features/support_resistance_detector.py`)
   - 5 detection methods implemented:
     - **ZigZag**: Filters noise, identifies significant swings (⭐⭐⭐⭐⭐)
     - **Local Extrema**: Mathematical peaks/troughs using scipy (⭐⭐⭐⭐)
     - **K-Means Clustering**: Statistical price zones (⭐⭐⭐⭐)
     - **Pivot Points**: Classical standard levels (⭐⭐⭐⭐)
     - **Fibonacci Retracement**: Natural retracement levels (⭐⭐⭐)
   - Feature engineering helpers (`add_sr_features`)
   - Level strength calculation

2. **Unit Tests** (`ml/src/tests/test_support_resistance.py`)
   - 29 tests covering all methods
   - Edge cases and validation

3. **API Endpoint** (`backend/supabase/functions/support-resistance/index.ts`)
   - GET `/support-resistance?symbol=AAPL`
   - Returns pivot points, Fibonacci, ZigZag swings, nearest levels

4. **Dashboard Visualization** (`ml/src/dashboard/forecast_dashboard.py`)
   - New "Support & Resistance" view
   - Price chart with S/R levels
   - Distance gauges and S/R ratio analysis
   - Method comparison radar chart

---

## Phase 1: Feature Integration (Recommended First Step)

### Objective
Add S/R features to the existing feature engineering pipeline.

### Implementation Steps

```python
# In ml/src/features/technical_indicators.py

from src.features.support_resistance_detector import SupportResistanceDetector

def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    # ... existing code ...
    
    # Add S/R features
    sr_detector = SupportResistanceDetector()
    df = sr_detector.add_sr_features(df)
    
    return df
```

### New Features Added
| Feature | Description | Use Case |
|---------|-------------|----------|
| `distance_to_support_pct` | % distance to nearest support | Downside risk |
| `distance_to_resistance_pct` | % distance to nearest resistance | Upside potential |
| `sr_ratio` | Resistance dist / Support dist | Risk/reward bias |
| `pivot_pp` | Current pivot point level | Reference level |
| `price_vs_pivot_pct` | Price position vs pivot | Trend context |
| `fib_nearest` | Nearest Fibonacci level | Target level |
| `distance_to_fib_pct` | % distance to nearest Fib | Retracement context |

### Expected Impact
- **Accuracy improvement**: 2-5% on price target predictions
- **Better risk assessment**: Quantified downside/upside distances
- **Improved entry/exit signals**: S/R proximity awareness

---

## Phase 2: Price Target Enhancement

### Objective
Use S/R levels to constrain and improve price target predictions.

### Implementation Approach

```python
# In ml/src/models/enhanced_forecaster.py

def _generate_forecast_points(self, ...):
    # Get S/R levels
    sr = SupportResistanceDetector()
    levels = sr.find_all_levels(df)
    
    # Constrain predictions to realistic levels
    if label == "bullish":
        # Cap upside at nearest resistance
        max_target = levels["nearest_resistance"] or forecast_value * 1.1
        forecast_value = min(forecast_value, max_target)
    elif label == "bearish":
        # Floor downside at nearest support
        min_target = levels["nearest_support"] or forecast_value * 0.9
        forecast_value = max(forecast_value, min_target)
    
    return points
```

### Benefits
- More realistic price targets
- Targets aligned with market structure
- Reduced overestimation in predictions

---

## Phase 3: Signal Confirmation

### Objective
Use S/R proximity to confirm or filter trading signals.

### Implementation Logic

```python
def get_sr_signal_modifier(df, label, confidence):
    """Modify signal confidence based on S/R proximity."""
    sr = SupportResistanceDetector()
    levels = sr.find_all_levels(df)
    
    support_dist = levels["support_distance_pct"] or 100
    resistance_dist = levels["resistance_distance_pct"] or 100
    
    if label == "bullish":
        # Bullish near support = stronger signal
        if support_dist < 2:
            confidence *= 1.15  # Boost confidence
        # Bullish near resistance = weaker signal
        elif resistance_dist < 2:
            confidence *= 0.85  # Reduce confidence
            
    elif label == "bearish":
        # Bearish near resistance = stronger signal
        if resistance_dist < 2:
            confidence *= 1.15
        # Bearish near support = weaker signal
        elif support_dist < 2:
            confidence *= 0.85
    
    return min(confidence, 0.95)  # Cap at 95%
```

### Signal Rules
| Scenario | Action |
|----------|--------|
| Bullish + Near Support | ✅ Strong buy signal |
| Bullish + Near Resistance | ⚠️ Caution, potential reversal |
| Bearish + Near Resistance | ✅ Strong sell signal |
| Bearish + Near Support | ⚠️ Caution, potential bounce |

---

## Phase 4: Multi-Timeframe S/R

### Objective
Combine S/R levels from multiple timeframes for stronger signals.

### Implementation

```python
def get_multi_timeframe_sr(symbol, timeframes=["1h", "1d", "1w"]):
    """Get S/R levels from multiple timeframes."""
    all_levels = {}
    
    for tf in timeframes:
        df = fetch_ohlc_data(symbol, timeframe=tf)
        sr = SupportResistanceDetector()
        levels = sr.find_all_levels(df)
        all_levels[tf] = levels
    
    # Find confluence zones (levels that appear in multiple timeframes)
    confluence_supports = find_confluence(
        [all_levels[tf]["all_supports"] for tf in timeframes],
        tolerance_pct=1.0
    )
    
    return {
        "confluence_supports": confluence_supports,
        "confluence_resistances": confluence_resistances,
        "strength_score": len(confluence_supports) + len(confluence_resistances)
    }
```

### Confluence Scoring
- Level appears in 1 timeframe: Weak (score: 1)
- Level appears in 2 timeframes: Moderate (score: 2)
- Level appears in 3+ timeframes: Strong (score: 3)

---

## Phase 5: Dynamic S/R Tracking

### Objective
Track S/R level breaks and use them as signals.

### Implementation

```python
def detect_sr_breakout(df, lookback=20):
    """Detect support/resistance breakouts."""
    sr = SupportResistanceDetector()
    
    # Get historical S/R levels
    historical_levels = sr.find_all_levels(df.iloc[:-1])
    current_price = df["close"].iloc[-1]
    prev_price = df["close"].iloc[-2]
    
    # Check for breakouts
    resistance = historical_levels["nearest_resistance"]
    support = historical_levels["nearest_support"]
    
    breakout_signal = None
    
    if resistance and prev_price < resistance <= current_price:
        breakout_signal = {
            "type": "resistance_break",
            "level": resistance,
            "signal": "bullish",
            "strength": calculate_breakout_strength(df, resistance)
        }
    elif support and prev_price > support >= current_price:
        breakout_signal = {
            "type": "support_break",
            "level": support,
            "signal": "bearish",
            "strength": calculate_breakout_strength(df, support)
        }
    
    return breakout_signal
```

---

## Database Schema Updates (Future)

### New Table: `sr_levels`

```sql
CREATE TABLE sr_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    timeframe VARCHAR(10),
    
    -- Pivot Points
    pivot_pp DECIMAL(12,4),
    pivot_r1 DECIMAL(12,4),
    pivot_r2 DECIMAL(12,4),
    pivot_r3 DECIMAL(12,4),
    pivot_s1 DECIMAL(12,4),
    pivot_s2 DECIMAL(12,4),
    pivot_s3 DECIMAL(12,4),
    
    -- Fibonacci
    fib_trend VARCHAR(10),
    fib_0 DECIMAL(12,4),
    fib_236 DECIMAL(12,4),
    fib_382 DECIMAL(12,4),
    fib_500 DECIMAL(12,4),
    fib_618 DECIMAL(12,4),
    fib_786 DECIMAL(12,4),
    fib_100 DECIMAL(12,4),
    
    -- Computed
    nearest_support DECIMAL(12,4),
    nearest_resistance DECIMAL(12,4),
    support_distance_pct DECIMAL(6,2),
    resistance_distance_pct DECIMAL(6,2),
    
    UNIQUE(symbol_id, timeframe, DATE(computed_at))
);
```

---

## Implementation Priority

| Phase | Effort | Impact | Priority |
|-------|--------|--------|----------|
| Phase 1: Feature Integration | Low | Medium | 🔴 High |
| Phase 2: Price Target Enhancement | Medium | High | 🔴 High |
| Phase 3: Signal Confirmation | Medium | Medium | 🟡 Medium |
| Phase 4: Multi-Timeframe | High | High | 🟡 Medium |
| Phase 5: Dynamic Tracking | High | Medium | 🟢 Low |

---

## Quick Start Integration

### Minimal Integration (5 minutes)

```python
# In your forecaster
from src.features.support_resistance_detector import SupportResistanceDetector

# Add to feature preparation
sr = SupportResistanceDetector()
df = sr.add_sr_features(df)

# Use in predictions
levels = sr.find_all_levels(df)
print(f"Support: {levels['nearest_support']}")
print(f"Resistance: {levels['nearest_resistance']}")
```

### Full Integration (30 minutes)

1. Add S/R features to `technical_indicators.py`
2. Update `ENHANCED_FEATURES` list in `enhanced_forecaster.py`
3. Add S/R signal modifier to confidence calculation
4. Update forecast point generation with S/R constraints

---

## Testing Checklist

- [ ] Unit tests pass for SupportResistanceDetector
- [ ] S/R features correctly added to DataFrame
- [ ] API endpoint returns valid data
- [ ] Dashboard displays S/R levels correctly
- [ ] Forecaster uses S/R features in predictions
- [ ] Price targets respect S/R boundaries
- [ ] Signal confidence modified by S/R proximity

---

## Metrics to Track

1. **Prediction Accuracy**: % of predictions within S/R bounds
2. **Target Hit Rate**: % of price targets reached
3. **S/R Respect Rate**: % of times price respects S/R levels
4. **Breakout Accuracy**: % of breakout signals that follow through

---

## References

- ZigZag Indicator: [LuxAlgo Guide](https://www.luxalgo.com/blog/zig-zag-indicator-filtering-noise-to-highlight-significant-price-swings/)
- Pivot Points: [Strike Money](https://www.strike.money/technical-analysis/pivot-points)
- K-Means S/R: [AlphaRithms](https://www.alpharithms.com/calculating-support-resistance-in-python-using-k-means-clustering-101517/)
- Fibonacci: [OmniCalculator](https://www.omnicalculator.com/finance/fibonacci-retracement)
