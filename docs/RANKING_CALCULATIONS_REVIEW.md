# Options Ranking Calculations - Full Review

## 📊 Current State Summary

### Weight Configuration Issues
- **Backend**: Uses 30/35/35 (entry mode) - Hardcoded in TypeScript
- **Frontend**: Shows 40/35/25 (default mode) - UI mismatch
- **Python**: Has 3 modes but only entry mode is used
- **Decision**: Standardize on 40/35/25 (default mode) everywhere

---

## 📐 Detailed Calculation Formulas

### 1. VALUE SCORE (will be 35% of composite)

**Location**: `ml/src/models/options_momentum_ranker.py` lines 696-726

**Formula**:
```python
# IV Rank Component (60% of value score)
iv_rank = (IV_current - IV_52week_low) / (IV_52week_high - IV_52week_low) × 100
iv_rank_score = 100 - iv_rank  # Invert: lower IV = better for buyers

# Spread Component (40% of value score)
spread_pct = (ask - bid) / mid_price × 100
spread_penalty = min(spread_pct × 2, 50)  # Max penalty 50 points
spread_score = 100 - spread_penalty

# Combined Value Score (0-100)
value_score = iv_rank_score × 0.60 + spread_score × 0.40
```

**Examples**:
- **Tight spread, low IV**: spread=1%, IV rank=20% → value_score = (80×0.6) + (98×0.4) = **87.2**
- **Wide spread, high IV**: spread=10%, IV rank=80% → value_score = (20×0.6) + (80×0.4) = **44.0**

**Question**: Should we penalize wide spreads more aggressively?
- Current: 10% spread → 20-point penalty
- Alternative: 10% spread → 30-point penalty (×3 multiplier)

---

### 2. MOMENTUM SCORE (will be 40% of composite)

**Location**: `ml/src/models/options_momentum_ranker.py` lines 850-891

**Formula**:
```python
# Price Momentum Component (50% of momentum score)
# Based on 5-day return
if return_5d >= 10%:
    price_mom_score = 100
elif return_5d >= 5%:
    price_mom_score = 75 + (return_5d - 5) × 5
elif return_5d >= 0%:
    price_mom_score = 50 + return_5d × 5
else:  # Negative returns
    price_mom_score = max(0, 50 + return_5d × 5)

# Volume/OI Ratio Component (30% of momentum score)
vol_oi_ratio = volume / open_interest
vol_oi_score = min(vol_oi_ratio / 0.20 × 100, 100)

# OI Growth Component (20% of momentum score)
oi_growth_5d = (OI_current - OI_5d_ago) / OI_5d_ago × 100
oi_growth_score = clip(oi_growth + 50, 0, 100)

# Combined Raw Momentum (before liquidity adjustment)
raw_momentum = (
    price_mom_score × 0.50 +
    vol_oi_score × 0.30 +
    oi_growth_score × 0.20
)

# Liquidity Confidence Dampening
# Geometric mean of volume, OI, and price confidence factors
volume_conf = clip(0.1 + 0.9 × volume / 100, 0.1, 1.0)
oi_conf = clip(0.1 + 0.9 × OI / 500, 0.1, 1.0)
price_conf = clip(0.1 + 0.9 × price / $5, 0.1, 1.0)
liquidity_confidence = (volume_conf × oi_conf × price_conf)^(1/3)

# Final Momentum Score (pulls toward 50 for illiquid options)
momentum_score = 50 + (raw_momentum - 50) × liquidity_confidence
```

**Examples**:
- **Hot momentum, liquid**: +8% price, vol/OI=0.25, +20% OI growth, Vol=150/OI=600/$4 → **momentum ≈ 85**
- **Weak momentum, illiquid**: +1% price, vol/OI=0.05, -5% OI growth, Vol=5/OI=20/$0.50 → **momentum ≈ 45**

**Question**: Is the liquidity dampening too aggressive for low-priced options?
- Current: $0.50 option gets ~40% confidence → scores pulled toward 50
- Impact: A $0.50 option with 90 raw momentum becomes ~66 final momentum

---

### 3. GREEKS SCORE (will be 25% of composite)

**Location**: `ml/src/models/options_momentum_ranker.py` lines 1160-1291

**Formula**:
```python
# Delta Score (50% of Greeks score)
# Target: 0.55 for calls, -0.55 for puts
delta_score = 100 - 100 × |delta - target|

# Trend Alignment Multiplier
if trend == "bullish" and side == "call": multiplier = 1.0
elif trend == "bearish" and side == "put": multiplier = 1.0
elif trend == "neutral": multiplier = 0.90
else: multiplier = 0.70  # Counter-trend penalty

delta_score_adjusted = delta_score × multiplier

# Gamma Score (35% of Greeks score)
gamma_score = min(gamma / 0.04 × 100, 100)

# Vega Score (10% of Greeks score)
vega_score = min(vega / 0.30 × 100, 100)

# Theta Penalty (subtracted from total)
theta_pct = |theta| / mid_price × 100  # Daily decay %
theta_penalty = min(theta_pct × 10, 40)  # Capped at 40 points

# Combined Greeks Score
greeks_score = clip(
    delta_score × 0.50 +
    gamma_score × 0.35 +
    vega_score × 0.10 -
    theta_penalty,
    0, 100
)
```

**Examples**:
- **Sweet spot call**: Δ=0.55, Γ=0.04, V=0.30, Θ=-0.02/$2 → **greeks = 100×0.5 + 100×0.35 + 100×0.1 - 10 = 85**
- **Deep ITM call**: Δ=0.90, Γ=0.01, V=0.10, Θ=-0.10/$3 → **greeks = 65×0.5 + 25×0.35 + 33×0.1 - 33 = 9**

**Questions**:
1. Is 0.55 delta the right target? (Some prefer 0.60 or even 0.70)
2. Should theta penalty be capped at 40? (Currently max penalty is 40 pts)
3. Is counter-trend multiplier (0.70) too harsh?

---

## 🎯 COMPOSITE RANK FORMULA

### Current (Entry Mode - 30/35/35):
```python
composite_rank = (
    momentum_score × 0.30 +
    value_score × 0.35 +
    greeks_score × 0.35
)
```

### Proposed (Default Mode - 40/35/25):
```python
composite_rank = (
    momentum_score × 0.40 +
    value_score × 0.35 +
    greeks_score × 0.25
)
```

**Rationale for 40/35/25**:
- **Momentum (40%)**: Most important for catching runners and trends
- **Value (35%)**: Critical for entry quality (IV and spread)
- **Greeks (25%)**: Supporting role for risk assessment

**Impact of Change**:
- High momentum contracts: Rank increases by ~5-10 points
- High Greeks contracts: Rank decreases by ~5-10 points
- Value-focused contracts: Minimal change

---

## 🧪 Test Cases for Validation

### Test Case 1: Perfect "Strong Buy"
```
Inputs:
- IV Rank: 20% (low IV = good)
- Spread: 1.5% (tight)
- 5d Return: +8%
- Vol/OI: 0.25 (hot)
- OI Growth: +15%
- Delta: 0.55 (calls)
- Gamma: 0.04
- Vega: 0.30
- Theta: -$0.02 on $2.00 (1% daily decay)
- Liquidity: High (Vol=150, OI=500, Price=$2)

Expected Scores:
- Value: ~87 (80×0.6 + 97×0.4)
- Momentum: ~88 (with full liquidity)
- Greeks: ~85 (100×0.5 + 100×0.35 + 100×0.1 - 10)
- Composite (40/35/25): 88×0.4 + 87×0.35 + 85×0.25 = 86.9
```

### Test Case 2: Illiquid "Discount"
```
Inputs:
- IV Rank: 15% (very low IV)
- Spread: 8% (wide - illiquid)
- 5d Return: +3%
- Vol/OI: 0.10 (low activity)
- OI Growth: 0%
- Delta: 0.50
- Gamma: 0.02
- Vega: 0.20
- Theta: -$0.05 on $0.50 (10% daily decay!)
- Liquidity: Low (Vol=10, OI=50, Price=$0.50)

Expected Scores:
- Value: ~76 (85×0.6 + 84×0.4)  # Good IV, wide spread
- Momentum: ~52 (dampened by low liquidity)
- Greeks: ~40 (95×0.5 + 50×0.35 + 67×0.1 - 40 theta penalty)
- Composite (40/35/25): 52×0.4 + 76×0.35 + 40×0.25 = 57.4
```

### Test Case 3: Counter-Trend "Avoid"
```
Inputs:
- IV Rank: 75% (high IV = expensive)
- Spread: 4% (fair)
- 5d Return: -2%
- Vol/OI: 0.15
- OI Growth: -10%
- Delta: 0.60 (calls, but bearish trend)
- Gamma: 0.03
- Vega: 0.25
- Theta: -$0.03 on $3.00 (1% decay)
- Liquidity: Medium (Vol=75, OI=250, Price=$3)
- Trend: Bearish

Expected Scores:
- Value: ~42 (25×0.6 + 92×0.4)  # High IV hurts
- Momentum: ~44 (weak price action, dampened)
- Greeks: ~49 (95×0.5×0.7 + 75×0.35 + 83×0.1 - 10)  # Counter-trend penalty
- Composite (40/35/25): 44×0.4 + 42×0.35 + 49×0.25 = 44.7
```

---

## 🔧 Proposed Refinements (Optional)

### Refinement 1: Spread Penalty Curve
**Current**: Linear penalty, 2× multiplier, capped at 50
```python
spread_penalty = min(spread_pct × 2, 50)
```

**Alternative**: Exponential penalty for very wide spreads
```python
if spread_pct <= 2%: penalty = spread_pct × 2
elif spread_pct <= 5%: penalty = 4 + (spread_pct - 2) × 4
elif spread_pct <= 10%: penalty = 16 + (spread_pct - 5) × 5
else: penalty = min(41 + (spread_pct - 10) × 2, 50)

Examples:
- 1% spread → 2 penalty (no change)
- 3% spread → 8 penalty (vs 6 current)
- 5% spread → 16 penalty (vs 10 current)
- 10% spread → 41 penalty (vs 20 current)
```

### Refinement 2: Delta Target Adjustment
**Current**: Fixed 0.55 target

**Alternative**: Dynamic target based on DTE
```python
if DTE > 45: target = 0.50  # Longer-term, lower delta
elif DTE > 21: target = 0.55  # Current sweet spot
elif DTE > 7: target = 0.60  # Near-term, higher delta
else: target = 0.65  # Very short-term, deeper ITM
```

### Refinement 3: Theta Penalty Cap
**Current**: Capped at 40 points

**Alternative**: Dynamic cap based on DTE
```python
if DTE > 45: cap = 25  # Less sensitive to theta for long-term
elif DTE > 21: cap = 40  # Current
else: cap = 50  # More sensitive near expiration
```

### Refinement 4: Liquidity Confidence Thresholds
**Current**: Volume=100, OI=500, Price=$5

**Alternative**: Lower thresholds for small-cap stocks
```python
# Adjust based on underlying price
if underlying_price < $20:
    volume_threshold = 50
    oi_threshold = 250
    price_threshold = $2.50
else:
    volume_threshold = 100
    oi_threshold = 500
    price_threshold = $5.00
```

---

## ✅ Validation Plan

### Step 1: Unit Tests
Create tests for each component:
- `test_value_score_calculation()`
- `test_momentum_score_calculation()`
- `test_greeks_score_calculation()`
- `test_composite_rank_calculation()`

### Step 2: Weight Synchronization Tests
- `test_python_typescript_weights_match()`
- `test_frontend_displays_correct_weights()`
- `test_contribution_calculations_match_weights()`

### Step 3: End-to-End Test
Run ranking on sample data and verify:
- All scores are 0-100
- Composite rank matches weighted sum
- No NaN or Inf values
- Liquidity dampening works correctly

### Step 4: Regression Test
Compare rankings before/after weight change:
- Document top 20 contracts before and after
- Verify expected rank changes (momentum ↑, greeks ↓)
- Ensure no contracts flip dramatically

---

## 📋 Implementation Checklist

### Phase 1: Standardize Weights (40/35/25)
- [ ] Update Python: Change entry mode to use 40/35/25
- [ ] Update TypeScript: Change constants to 40/35/25
- [ ] Update Frontend: Verify UI shows 40/35/25
- [ ] Update Documentation: All references to weights

### Phase 2: Add Validation Tests
- [ ] Create `test_ranking_calculations.py`
- [ ] Add unit tests for each score component
- [ ] Add weight synchronization tests
- [ ] Add end-to-end validation test

### Phase 3: Optional Refinements
- [ ] Decide on spread penalty curve
- [ ] Decide on delta target adjustment
- [ ] Decide on theta penalty cap
- [ ] Decide on liquidity thresholds

### Phase 4: Deploy & Monitor
- [ ] Run on test symbol (AAPL)
- [ ] Compare rankings before/after
- [ ] Deploy to production
- [ ] Monitor for anomalies

---

## 🤔 Questions for You

1. **Spread Penalty**: Keep current (2× linear) or switch to exponential curve?
   
2. **Delta Target**: Keep fixed 0.55 or make dynamic based on DTE?

3. **Theta Penalty**: Keep fixed 40-point cap or make dynamic based on DTE?

4. **Liquidity Thresholds**: Keep current ($100 vol, $500 OI, $5) or adjust for small-cap stocks?

5. **Test Cases**: Do the 3 test cases above look correct to you?

6. **Any other concerns** with the formulas before we standardize?

---

## 💡 Recommended Approach

**Minimal Changes** (Low Risk):
1. ✅ Standardize weights to 40/35/25 everywhere
2. ✅ Add validation tests
3. ✅ Document calculations
4. ⏸️ Keep all other formulas as-is for now

**With Refinements** (Medium Risk):
1. ✅ Standardize weights
2. ✅ Add validation tests  
3. ✅ Implement exponential spread penalty
4. ✅ Make theta cap dynamic (25/40/50 based on DTE)
5. ⏸️ Monitor performance before further changes

**Your choice**: Which approach do you prefer?
