# Bollinger Band Chart Metrics: Quantitative Reference Framework

This document consolidates the Bollinger Band interpretation framework implemented in SwiftBolt ML, including six core metrics, calculation workflow, regime behavior, and ML feature engineering guidance.

## Implementation Location

- **Calculation**: `ml/src/features/technical_indicators_corrected.py` → `TechnicalIndicatorsCorrect.calculate_bollinger_bands()`
- **Scoring**: `ml/src/strategies/multi_indicator_signals.py` → `_score_bollinger()`; `ml/src/models/composite_signal_calculator.py` → `score_bb_width()`
- **Features**: `bb_upper`, `bb_middle`, `bb_lower`, `bb_width`, `bb_pct_b`, `bb_std`, `bb_band_position`, `bb_width_pct`, `bb_expansion_ratio`, `bb_squeeze`

---

## The Six Core Metrics

### 1. %B (Percent B) — `bb_pct_b`

**Formula**: `%B = (Price − Lower Band) / (Upper Band − Lower Band)`

Normalizes price to a 0–1 scale:
- `%B = 0`: Price at lower band
- `%B = 1`: Price at upper band  
- `%B = 0.5`: Price at middle band (SMA)
- Values outside 0–1: Price beyond bands

**Interpretation** (Bollinger framework):
- `%B > 0.80`: Uptrend signal (combine with MFI > 80 for confirmation)
- `%B < 0.20`: Downtrend signal (combine with MFI < 20)
- For ML: Use historical percentile ranking for cross-asset comparison

---

### 2. BandWidth (BBW) — `bb_width`

**Formula**: `BandWidth = ((Upper − Lower) / Middle) × 100`

Volatility as percentage, comparable across price levels and assets.

**Thresholds**:
| BandWidth | Regime | Interpretation |
|-----------|--------|----------------|
| < 2% | Extreme squeeze | Statistical precursor to breakouts |
| 2–5% | Tight consolidation | Early compression phase |
| 10–20% | Normal range | Standard market conditions |
| 20–40% | Active expansion | Trending periods with momentum |
| > 40% | Extreme volatility | Crisis moves, exhaustion |

**Mathematical note**: BandWidth = 4 × coefficient of variation for default (20, 2) parameters.

---

### 3. Standard Deviation (σ) — `bb_std`

**Formula**: `σ = √Σ(Close − SMA)² / N`

Uses **population** standard deviation (divisor N), not sample (N−1), per Bollinger.

Bands are at ±2σ from SMA (~95% of moves under normal distribution). Financial returns have fat tails, so breaches occur more often than theory predicts. Use raw σ as an ML feature rather than band touches alone.

---

### 4. Band Position Ratio — `bb_band_position`

**Formula**: `(Price − SMA) / σ`

Standard deviations from the middle band. Typical range ≈ −3 to +3. Values outside ±2 indicate breach of the 2σ bands.

**ML benefit**: Volatility-normalized; comparable across assets with different price and volatility levels.

---

### 5. Expansion Ratio — `bb_expansion_ratio`

**Formula**: `Current BandWidth / Avg BandWidth(50)`

Measures volatility regime changes:
- `> 1.2`: Volatility expanding
- `< 0.8`: Volatility contracting
- `Expansion Ratio < 0.7` for 5+ periods: Often precedes larger moves in the next 5–15 days

Track the slope of this series as well as its level.

---

### 6. TTM Squeeze — `bb_squeeze`

**Definition**: `Squeeze = TRUE` when Bollinger Upper < Keltner Upper AND Bollinger Lower > Keltner Lower

Uses Keltner Channels (EMA center, ATR bands) vs. Bollinger (SMA, std bands).

**Empirical**: When the squeeze ends (Bollinger moves outside Keltner), the breakout follows through with ~70–75% probability for at least 1.5× the pre-breakout range. More reliable than Bollinger-only because ATR reflects gaps and limit moves.

---

## Calculation Workflow

1. SMA(20) = Middle band  
2. σ = population std of closes vs SMA  
3. Upper = SMA + 2σ; Lower = SMA − 2σ  
4. BandWidth = (Upper − Lower) / Middle × 100  
5. %B = (Price − Lower) / (Upper − Lower)  
6. Band Position = (Price − SMA) / σ  
7. Expansion Ratio = BandWidth / SMA(BandWidth, 50)  
8. TTM Squeeze = BB inside Keltner envelope  

---

## Metric Behavior Across Regimes

### Trending Markets

- **%B**: Stays 0.6–1.0+ (uptrend) or 0–0.4 (downtrend)  
- **Band Position**: Positive (+1 to +3) in uptrends  
- **BandWidth**: Expands with momentum  
- **Middle band**: Acts as dynamic support; “band walk” = price hugging upper band with higher lows  

### Range-Bound Markets

- **%B**: Cycles roughly 0.2–0.8  
- **Band Position**: Centered −0.5 to +0.5  
- **BandWidth**: Contracted (often 10–20%)  
- Mean reversion works: sell when %B > 0.80, buy when %B < 0.20  

### Pre-Breakout Squeeze

- **BandWidth**: < 5%  
- **%B**: Near 0.5  
- **Band Position**: Near 0  
- **Expansion Ratio**: Declining  
- Longer squeezes (15–25 bars) tend to precede larger moves  

---

## ML Feature Engineering

Normalized features improve cross-asset and cross-timeframe performance:

1. **BandWidth Percentile**  
   Percentile rank of current BandWidth in a 6-month window (0–100).  
   < 20: compression; > 80: expansion.

2. **Z-Score of Band Position**  
   `(Current Band Position − 50-period mean) / Std of Band Position`  
   Produces values roughly in [−2, 2], like RSI/Stochastic.

3. **Squeeze Duration**  
   Consecutive bars with BandWidth below the 30th percentile.  
   Longer duration correlates with stronger subsequent breakouts.

4. **Expansion/Contraction Rate**  
   `(Current BandWidth − BandWidth 5 bars ago) / 5`  
   Captures the speed of volatility change.

5. **Cross-Timeframe %B**  
   %B on daily and 4h. When both > 0.80 or both < 0.20, signal strength often increases by 3–5×.

---

## Code Usage

```python
from src.features.technical_indicators_corrected import TechnicalIndicatorsCorrect

df = TechnicalIndicatorsCorrect.calculate_bollinger_bands(
    df,
    period=20,
    std_dev=2.0,
    use_population_std=True,   # Bollinger standard
    include_ttm_squeeze=True,  # Requires high, low columns
)

# Access metrics
pct_b = df["bb_pct_b"].iloc[-1]           # %B
bandwidth = df["bb_width"].iloc[-1]       # BandWidth %
expansion = df["bb_expansion_ratio"].iloc[-1]
in_squeeze = df["bb_squeeze"].iloc[-1]
```

---

## References

- Bollinger, John — *Bollinger on Bollinger Bands*
- Framework thresholds and regime descriptions from quantitative trading research
- TTM Squeeze methodology (TradingView / John Carter)
