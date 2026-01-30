# Technical Indicators: Refined Bull / Bear / Neutral Thresholds

**SwiftBolt ML - Comprehensive Technical Analysis Classification Guide**

Last Updated: January 29, 2026

---

## Overview

This document defines the precise thresholds and logic for categorizing technical indicators as **Bullish**, **Bearish**, or **Neutral** in the SwiftBolt ML platform. Each indicator includes context-aware interpretations to handle different market conditions (trending vs ranging, high vs low volatility).

---

## 1. Momentum Indicators

### RSI (Relative Strength Index) — 14 period

**Key Insight:** RSI interpretation depends on market context (trending vs ranging)

#### Trending Market Classification
| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Strong Bullish** | > 70 (sustained) | Strong uptrend momentum |
| **Bullish** | 60-70 | Healthy upward momentum |
| **Neutral** | 40-60 | No clear directional bias |
| **Bearish** | 30-40 | Downward momentum building |
| **Strong Bearish** | < 30 (sustained) | Strong downtrend momentum |

#### Ranging Market Classification (Reversal Signals)
| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Bullish Reversal** | < 30 | Oversold - potential bounce |
| **Neutral** | 30-70 | Normal range |
| **Bearish Reversal** | > 70 | Overbought - potential pullback |

**App Logic:**
```python
def classify_rsi(rsi_value, market_regime):
    if market_regime == "trending":
        if rsi_value > 70:
            return "Strong Bullish"
        elif rsi_value > 60:
            return "Bullish"
        elif rsi_value > 40:
            return "Neutral"
        elif rsi_value > 30:
            return "Bearish"
        else:
            return "Strong Bearish"
    else:  # ranging market
        if rsi_value < 30:
            return "Bullish" # Oversold reversal
        elif rsi_value > 70:
            return "Bearish" # Overbought reversal
        else:
            return "Neutral"
```

**Code References:**
- Display: `TechnicalIndicatorsModels.swift`
- ML signals: `multi_indicator_signals.py`
- Explainer: `forecast_explainer.py`

---

### MACD (Moving Average Convergence Divergence)

| Component | Strong Bullish | Bullish | Neutral | Bearish | Strong Bearish |
|-----------|----------------|---------|---------|---------|----------------|
| **MACD Histogram** | > 0 & increasing | > 0 | ≈ 0 | < 0 | < 0 & decreasing |
| **MACD Line vs Signal** | MACD >> Signal | MACD > Signal | MACD ≈ Signal | MACD < Signal | MACD << Signal |

**Crossover Signals:**
| Event | Signal |
|-------|--------|
| MACD crosses above Signal (from below zero) | **Strong Bullish** |
| MACD crosses above Signal (above zero) | **Bullish** |
| MACD crosses below Signal (above zero) | **Bearish** |
| MACD crosses below Signal (from above zero) | **Strong Bearish** |

**App Logic:**
```python
def classify_macd(macd, signal, histogram, prev_histogram):
    histogram_increasing = histogram > prev_histogram

    if histogram > 0:
        return "Strong Bullish" if histogram_increasing else "Bullish"
    elif histogram < 0:
        return "Strong Bearish" if not histogram_increasing else "Bearish"
    else:
        return "Neutral"
```

---

### MFI (Money Flow Index) — 14 period

**Similar to RSI but volume-weighted**

| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Bullish Reversal** | < 20 | Oversold with volume confirmation |
| **Bullish** | 20-30 | Potential buying opportunity |
| **Neutral** | 30-70 | Normal money flow |
| **Bearish** | 70-80 | Potential selling opportunity |
| **Bearish Reversal** | > 80 | Overbought with volume confirmation |

**App Logic:**
```python
def classify_mfi(mfi_value):
    if mfi_value < 20:
        return "Strong Bullish" # Extreme oversold
    elif mfi_value < 30:
        return "Bullish"
    elif mfi_value <= 70:
        return "Neutral"
    elif mfi_value <= 80:
        return "Bearish"
    else:
        return "Strong Bearish" # Extreme overbought
```

---

### Stochastic Oscillator

**Best used for reversal signals, especially with crossovers**

| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Oversold Zone** | < 20 | Potential bullish reversal |
| **Neutral** | 20-80 | No extreme condition |
| **Overbought Zone** | > 80 | Potential bearish reversal |

**Crossover Logic:**
| Event | Signal |
|-------|--------|
| %K crosses above %D from < 20 | **Strong Bullish** |
| %K crosses above %D (20-80) | **Bullish** |
| %K crosses below %D from > 80 | **Strong Bearish** |
| %K crosses below %D (20-80) | **Bearish** |

**Trend Confirmation:**
- Sustained readings 60-80 = **Bullish trend**
- Sustained readings 20-40 = **Bearish trend**

**App Logic:**
```python
def classify_stochastic(k, d, prev_k, prev_d):
    # Check for crossovers
    bullish_cross = k > d and prev_k <= prev_d
    bearish_cross = k < d and prev_k >= prev_d

    if k < 20:
        return "Strong Bullish" if bullish_cross else "Bullish"
    elif k > 80:
        return "Strong Bearish" if bearish_cross else "Bearish"
    elif 20 <= k <= 80:
        if bullish_cross:
            return "Bullish"
        elif bearish_cross:
            return "Bearish"
        else:
            return "Neutral"
```

---

### Williams %R

| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Oversold** | < -80 | Potential bullish bounce |
| **Bullish Zone** | -80 to -50 | Bullish momentum |
| **Neutral** | -50 to -20 | No clear bias |
| **Bearish Zone** | -20 to 0 | Bearish momentum |
| **Overbought** | > -20 | Potential bearish pullback |

**Momentum Context:**
- Sustained -20 to -40 = **Bullish trend**
- Sustained -60 to -80 = **Bearish trend**

**App Logic:**
```python
def classify_williams_r(wr_value):
    if wr_value < -80:
        return "Bullish" # Oversold
    elif wr_value < -50:
        return "Bullish" # Bullish zone
    elif wr_value < -20:
        return "Neutral"
    else:
        return "Bearish" # Overbought zone
```

---

### CCI (Commodity Channel Index)

| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Strong Oversold** | < -200 | Extreme oversold |
| **Oversold** | -200 to -100 | Potential bullish reversal |
| **Neutral** | -100 to +100 | Normal range |
| **Overbought** | +100 to +200 | Potential bearish reversal |
| **Strong Overbought** | > +200 | Extreme overbought |

**Trending Logic:**
- CCI consistently > +100 = **Strong uptrend**
- CCI consistently < -100 = **Strong downtrend**

**App Logic:**
```python
def classify_cci(cci_value):
    if cci_value < -200:
        return "Strong Bullish"
    elif cci_value < -100:
        return "Bullish"
    elif -100 <= cci_value <= 100:
        return "Neutral"
    elif cci_value <= 200:
        return "Bearish"
    else:
        return "Strong Bearish"
```

---

### KDJ Indicator

**Similar to Stochastic but more sensitive**

| Signal Type | Threshold | Interpretation |
|-------------|-----------|----------------|
| **Oversold** | J < 0 | Strong bullish reversal potential |
| **Bullish** | 0 < J < 20 | Bullish momentum building |
| **Neutral** | 20 < J < 80 | No extreme condition |
| **Bearish** | 80 < J < 100 | Bearish momentum building |
| **Overbought** | J > 100 | Strong bearish reversal potential |

**Crossover Signals:**
- K crosses above D = **Bullish**
- K crosses below D = **Bearish**
- J crosses above both K & D = **Strong Bullish**
- J crosses below both K & D = **Strong Bearish**

#### KDJ Divergence (J − D)

J minus D can be **positive or negative**. Used as a crossover/divergence signal.

| Signal Type     | Threshold | Interpretation   |
|-----------------|-----------|------------------|
| **Strong Bullish** | J − D > 30 | Strong bullish divergence |
| **Bullish**     | J − D > 15 | Bullish divergence |
| **Neutral**     | −15 ≤ J − D ≤ 15 | No clear divergence |
| **Bearish**     | J − D < −15 | Bearish divergence |
| **Strong Bearish** | J − D < −30 | Strong bearish divergence |

---

### Returns (1d, 5d, 20d)

**Price change percentages - directional momentum**

| Timeframe | Strong Bullish | Bullish | Neutral | Bearish | Strong Bearish |
|-----------|----------------|---------|---------|---------|----------------|
| **1-Day** | > +3% | +1% to +3% | -1% to +1% | -3% to -1% | < -3% |
| **5-Day** | > +5% | +2% to +5% | -2% to +2% | -5% to -2% | < -5% |
| **20-Day** | > +10% | +5% to +10% | -5% to +5% | -10% to -5% | < -10% |

---

## 2. Volatility Indicators

### ADX (Average Directional Index) — 14 period

**Critical: ADX measures trend STRENGTH, not direction. Use with +DI/-DI for direction.**

#### Trend Strength Classification
| ADX Value | Threshold | Trend Strength |
|-----------|-----------|----------------|
| **No trend** | < 20 | Choppy, range-bound |
| **Weak trend** | 20-25 | Trend emerging |
| **Moderate trend** | 25-40 | Clear trend established |
| **Strong trend** | 40-50 | Powerful trend |
| **Very strong** | > 50 | Extreme trend |

#### Combined Signal (ADX + Directional Indicators)
| Condition | Signal |
|-----------|--------|
| ADX > 25 AND +DI > -DI | **Bullish Trend** |
| ADX > 40 AND +DI > -DI | **Strong Bullish Trend** |
| ADX > 25 AND -DI > +DI | **Bearish Trend** |
| ADX > 40 AND -DI > +DI | **Strong Bearish Trend** |
| ADX < 20 | **Neutral** (range-bound) |
| ADX 20-25 | **Neutral** (weak trend forming) |

**App Logic:**
```python
def classify_adx(adx, plus_di, minus_di):
    if adx < 20:
        return "Neutral" # No clear trend
    elif adx < 25:
        return "Neutral" # Weak trend forming
    else:
        # Trend is established, check direction
        di_spread = plus_di - minus_di

        if adx > 40:
            # Strong trend
            if di_spread > 5:
                return "Strong Bullish"
            elif di_spread < -5:
                return "Strong Bearish"
            else:
                return "Neutral"
        else:
            # Moderate trend (25-40)
            if di_spread > 0:
                return "Bullish"
            elif di_spread < 0:
                return "Bearish"
            else:
                return "Neutral"
```

---

### ATR (Average True Range) — 14 period

**ATR measures volatility magnitude, not direction**

| Classification | Use Case |
|----------------|----------|
| **High ATR** | Large stop-losses needed; strong trend or panic |
| **Low ATR** | Tight stop-losses; consolidation, breakout pending |
| **Rising ATR** | Volatility increasing - trend gaining momentum |
| **Falling ATR** | Volatility decreasing - trend exhausting |

**Context-Based Signals:**
- Rising ATR + Price rising = **Bullish trend strengthening**
- Rising ATR + Price falling = **Bearish trend strengthening**
- Falling ATR = **Neutral** (consolidation, wait for breakout)

**App Logic:**
```python
def classify_atr_context(atr, prev_atr, price_change):
    atr_rising = atr > prev_atr

    if atr_rising:
        if price_change > 0:
            return "Bullish" # Volatility + upward price = bullish
        elif price_change < 0:
            return "Bearish" # Volatility + downward price = bearish
        else:
            return "Neutral"
    else:
        return "Neutral" # Low volatility = consolidation
```

---

### Bollinger Bands (20, 2)

**Price position relative to bands + bandwidth dynamics**

#### Price Position
| Condition | Signal | Interpretation |
|-----------|--------|----------------|
| Price > Upper Band | **Caution** | Overbought - watch for rejection OR breakout |
| Price touching Upper + volume spike | **Strong Bullish** | Breakout confirmation |
| Price in upper half (Middle to Upper) | **Bullish** | Uptrend zone |
| Price at Middle Band (SMA) | **Neutral** | Equilibrium, decision point |
| Price in lower half (Lower to Middle) | **Bearish** | Downtrend zone |
| Price < Lower Band | **Caution** | Oversold - watch for bounce OR breakdown |
| Price touching Lower + volume spike | **Strong Bearish** | Breakdown confirmation |

#### Bandwidth (Volatility)
| Condition | Signal |
|-----------|--------|
| Bandwidth expanding | **Volatility increasing** - trend starting |
| Bandwidth contracting | **Consolidation** - breakout pending |
| Bandwidth extremely narrow | **Volatility squeeze** - big move imminent |

**App Logic:**
```python
def classify_bollinger(price, upper, middle, lower, volume_ratio):
    price_position = (price - lower) / (upper - lower) # 0 to 1

    if price > upper:
        if volume_ratio > 1.5:
            return "Strong Bullish" # Breakout with volume
        else:
            return "Bearish" # Overbought, likely rejection
    elif price_position > 0.7: # Upper 30%
        return "Bullish"
    elif price_position > 0.3: # Middle 40%
        return "Neutral"
    elif price < lower:
        if volume_ratio > 1.5:
            return "Strong Bearish" # Breakdown with volume
        else:
            return "Bullish" # Oversold, likely bounce
    else: # Lower 30%
        return "Bearish"
```

---

### SuperTrend

**Clear binary trend indicator**

| Condition | Signal | Interpretation |
|-----------|--------|----------------|
| Price > SuperTrend (trend = 1) | **Bullish** | Uptrend confirmed |
| Price >> SuperTrend (>3% above) | **Strong Bullish** | Strong uptrend |
| Price < SuperTrend (trend = 0) | **Bearish** | Downtrend confirmed |
| Price << SuperTrend (>3% below) | **Strong Bearish** | Strong downtrend |

**Signal Strength:** 0.0 – 1.0 (continuous confidence measure)

**App Logic:**
```python
def classify_supertrend(price, supertrend, trend):
    distance_pct = (price - supertrend) / supertrend

    if trend == 1: # Bullish regime
        if distance_pct > 0.03:
            return "Strong Bullish"
        else:
            return "Bullish"
    else: # trend == 0, Bearish regime
        if distance_pct < -0.03:
            return "Strong Bearish"
        else:
            return "Bearish"
```

---

### Volatility Regime (20-day)

**Statistical classification of volatility environment**

| Regime | Threshold | Interpretation |
|--------|-----------|----------------|
| **Low Volatility** | < 15th percentile | Range-bound, breakout watch |
| **Normal Volatility** | 15th-85th percentile | Standard conditions |
| **High Volatility** | > 85th percentile | Trending or panic, widen stops |

**Context Signals:**
- Moving from Low → High volatility = **Breakout likely**
- High volatility sustained = **Strong trend in progress**
- Moving from High → Low volatility = **Consolidation phase**

---

## 3. Volume Indicators

### Volume Ratio

**Critical: Volume interpretation MUST consider price direction**

| Condition | Threshold | Interpretation | Signal |
|-----------|-----------|----------------|--------|
| High volume + Price up | > 1.5 + green candle | Strong buying pressure | **Bullish** |
| Very high volume + Price up | > 2.0 + green candle | Extreme buying | **Strong Bullish** |
| High volume + Price down | > 1.5 + red candle | Strong selling pressure | **Bearish** |
| Very high volume + Price down | > 2.0 + red candle | Extreme selling | **Strong Bearish** |
| Low volume + Price up | < 0.5 + green candle | Weak buying (unsustainable) | **Weak Bullish** |
| Low volume + Price down | < 0.5 + red candle | Weak selling (limited) | **Weak Bearish** |
| Average volume | 0.5–1.5 | Normal activity | **Neutral** |

**App Logic:**
```python
def classify_volume_ratio(volume_ratio, price_change):
    if volume_ratio > 2.0:
        # Very high volume
        if price_change > 0:
            return "Strong Bullish"
        elif price_change < 0:
            return "Strong Bearish"
        else:
            return "Neutral" # High vol, no direction = uncertainty
    elif volume_ratio > 1.5:
        # High volume
        if price_change > 0:
            return "Bullish"
        elif price_change < 0:
            return "Bearish"
        else:
            return "Neutral"
    elif volume_ratio < 0.5:
        # Low volume - weak signal
        return "Neutral"
    else:
        # Average volume
        return "Neutral"
```

---

### OBV (On-Balance Volume)

**Cumulative volume-based momentum indicator**

#### Trend Confirmation
| Condition | Signal |
|-----------|--------|
| OBV rising + Price rising | **Bullish** - uptrend confirmed |
| OBV falling + Price falling | **Bearish** - downtrend confirmed |
| OBV flat + Price moving | **Neutral** - no conviction |

#### Divergence Signals (Powerful)
| Condition | Signal |
|-----------|--------|
| OBV rising + Price falling | **Bullish Divergence** - potential reversal up |
| OBV falling + Price rising | **Bearish Divergence** - potential reversal down |

**App Logic:**
```python
def classify_obv(obv, prev_obv, price_change, prev_price_change):
    obv_slope = obv - prev_obv
    obv_rising = obv_slope > 0
    price_rising = price_change > 0

    # Check for divergence
    if obv_rising and not price_rising:
        return "Bullish" # Bullish divergence
    elif not obv_rising and price_rising:
        return "Bearish" # Bearish divergence
    elif obv_rising and price_rising:
        return "Bullish" # Confirmed uptrend
    elif not obv_rising and not price_rising:
        return "Bearish" # Confirmed downtrend
    else:
        return "Neutral"
```

---

## 4. Trend Indicators

### Price vs SMA (Simple Moving Average)

**Distance from moving average indicates trend strength**

| Distance from SMA | Threshold | Signal |
|-------------------|-----------|--------|
| **Well above** | > +5% | **Strong Bullish** |
| **Above** | +2% to +5% | **Bullish** |
| **Near** | -2% to +2% | **Neutral** |
| **Below** | -5% to -2% | **Bearish** |
| **Well below** | < -5% | **Strong Bearish** |

**Common SMAs:**
- 20 SMA - Short-term trend
- 50 SMA - Medium-term trend
- 200 SMA - Long-term trend

**App Logic:**
```python
def classify_price_vs_sma(price, sma):
    distance_pct = (price - sma) / sma

    if distance_pct > 0.05:
        return "Strong Bullish"
    elif distance_pct > 0.02:
        return "Bullish"
    elif distance_pct < -0.05:
        return "Strong Bearish"
    elif distance_pct < -0.02:
        return "Bearish"
    else:
        return "Neutral"
```

---

### Moving Average Crossovers

**Crossover events signal trend changes**

#### Common MA Pairs
- **Golden Cross:** 50 SMA crosses above 200 SMA = **Strong Bullish**
- **Death Cross:** 50 SMA crosses below 200 SMA = **Strong Bearish**
- **Short-term:** 9 EMA / 21 EMA crossovers = **Bullish/Bearish**

#### Price Position Signals
| Condition | Signal |
|-----------|--------|
| Fast MA > Slow MA (bullish cross) | **Bullish** |
| Fast MA < Slow MA (bearish cross) | **Bearish** |
| Price > both MAs | **Strong Bullish** |
| Price < both MAs | **Strong Bearish** |
| Price between MAs | **Neutral** (transition zone) |

**App Logic:**
```python
def classify_ma_cross(price, fast_ma, slow_ma, prev_fast_ma, prev_slow_ma):
    bullish_cross = fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma
    bearish_cross = fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma

    if bullish_cross:
        return "Bullish"
    elif bearish_cross:
        return "Bearish"
    elif price > fast_ma and fast_ma > slow_ma:
        return "Strong Bullish"
    elif price < fast_ma and fast_ma < slow_ma:
        return "Strong Bearish"
    elif fast_ma > slow_ma:
        return "Bullish"
    elif fast_ma < slow_ma:
        return "Bearish"
    else:
        return "Neutral"
```

---

## 5. Support & Resistance

### Polynomial S/R Bias

**Distance to support vs resistance indicates directional bias**

| Condition | Signal |
|-----------|--------|
| Support closer to price than resistance | **Bullish** - floor nearby |
| Resistance closer to price than support | **Bearish** - ceiling nearby |
| Equidistant or unclear | **Neutral** |

**Slope Analysis:**
| Slope | Interpretation |
|-------|----------------|
| Positive slope | Rising support/resistance = **Bullish structure** |
| Negative slope | Falling support/resistance = **Bearish structure** |
| Flat | Horizontal S/R = **Range-bound** |

**App Logic:**
```python
def classify_sr_bias(price, support, resistance, support_slope, resistance_slope):
    distance_to_support = abs(price - support)
    distance_to_resistance = abs(price - resistance)

    # Determine proximity bias
    if distance_to_support < distance_to_resistance * 0.8:
        bias = "Bullish" # Near support
    elif distance_to_resistance < distance_to_support * 0.8:
        bias = "Bearish" # Near resistance
    else:
        bias = "Neutral"

    # Adjust for slope
    if support_slope > 0 and resistance_slope > 0:
        # Rising structure
        if bias == "Bearish":
            return "Neutral" # Upgrade
        else:
            return bias
    elif support_slope < 0 and resistance_slope < 0:
        # Falling structure
        if bias == "Bullish":
            return "Neutral" # Downgrade
        else:
            return bias
    else:
        return bias
```

---

### Logistic Regression S/R

**Probability-based support/resistance level detection**

| Condition | Interpretation | Signal Context |
|-----------|----------------|----------------|
| **High resistance probability** (> 0.7) | Price near **ceiling** | **Bearish** - rejection likely |
| **High support probability** (> 0.7) | Price near **floor** | **Bullish** - bounce likely |
| **Moderate probability** (0.3–0.7) | **Neutral zone** | No strong S/R level |
| **Low probability** (< 0.3) | **Open space** | Price free to move |

#### Breakout/Breakdown Logic
| Event | Signal |
|-------|--------|
| Price breaks above resistance (>0.7) with volume | **Strong Bullish** |
| Price breaks below support (>0.7) with volume | **Strong Bearish** |
| Price respects resistance (>0.7) | **Bearish** |
| Price respects support (>0.7) | **Bullish** |

**App Logic:**
```python
def classify_logistic_sr(price, prev_price, resistance_prob, support_prob, volume_ratio):
    price_rising = price > prev_price

    # Check for breakout/breakdown
    if resistance_prob > 0.7:
        if price_rising and volume_ratio > 1.5:
            return "Strong Bullish" # Breakout with volume
        else:
            return "Bearish" # Approaching resistance
    elif support_prob > 0.7:
        if not price_rising and volume_ratio > 1.5:
            return "Strong Bearish" # Breakdown with volume
        else:
            return "Bullish" # Approaching support
    elif resistance_prob < 0.3 and support_prob < 0.3:
        return "Neutral" # Open space
    else:
        return "Neutral" # Moderate probability zone
```

---

### Pivot Levels

**Classical support/resistance reference points**

| Level | Use Case |
|-------|----------|
| **Pivot Point (PP)** | Primary support/resistance |
| **R1, R2, R3** | Resistance levels above PP |
| **S1, S2, S3** | Support levels below PP |

**Trading Logic:**
- Price above PP = **Bullish bias**
- Price below PP = **Bearish bias**
- Price between S1/R1 = **Neutral**
- Approaching R2/R3 = **Overbought**
- Approaching S2/S3 = **Oversold**

---

## 6. ML / Forecast Indicators

### Forecast Returns (Daily)

**Predicted price movement for next trading day**

| Forecast | Threshold | Signal |
|----------|-----------|--------|
| **Strong Bullish** | > +5% | High conviction upside |
| **Bullish** | +2% to +5% | Moderate upside expected |
| **Neutral** | -2% to +2% | No clear direction |
| **Bearish** | -5% to -2% | Moderate downside expected |
| **Strong Bearish** | < -5% | High conviction downside |

**Confidence Weighting:**
- High model confidence (> 0.8) = **Trust forecast strongly**
- Medium confidence (0.5-0.8) = **Moderate weight**
- Low confidence (< 0.5) = **Discount forecast**

---

### Forecast Returns (Intraday)

**Predicted price movement for next 1-4 hours**

| Forecast | Threshold | Signal |
|----------|-----------|--------|
| **Strong Bullish** | > +1.5% | High conviction upside |
| **Bullish** | +0.5% to +1.5% | Moderate upside expected |
| **Neutral** | -0.5% to +0.5% | No clear direction |
| **Bearish** | -1.5% to -0.5% | Moderate downside expected |
| **Strong Bearish** | < -1.5% | High conviction downside |

**Note:** Intraday thresholds are proportionally smaller due to shorter timeframe.

---

## 7. Composite / AI Indicators

### SuperTrend AI (Adaptive)

**Machine learning enhanced SuperTrend with dynamic parameters**

| Condition | Signal |
|-----------|--------|
| Trend = 1 (bullish regime) | **Bullish** |
| Trend = 0 (bearish regime) | **Bearish** |

**Additional Metrics:**
- **Adaptive Factor:** 1.0 – 5.0 (multiplier sensitivity)
- **Performance Index:** 0.0 – 1.0 (historical accuracy)

**App Logic:**
```python
def classify_supertrend_ai(trend, performance_index):
    if trend == 1:
        if performance_index > 0.7:
            return "Strong Bullish" # High confidence
        else:
            return "Bullish"
    else: # trend == 0
        if performance_index > 0.7:
            return "Strong Bearish" # High confidence
        else:
            return "Bearish"
```

---

### Multi-Timeframe Consensus

**Aggregate signal across multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)**

| Consensus | Interpretation | Signal |
|-----------|----------------|--------|
| **Strong Bullish** | 80%+ timeframes bullish | **Strong Bullish** |
| **Bullish** | 60-80% timeframes bullish | **Bullish** |
| **Neutral** | Mixed signals (40-60% either way) | **Neutral** |
| **Bearish** | 60-80% timeframes bearish | **Bearish** |
| **Strong Bearish** | 80%+ timeframes bearish | **Strong Bearish** |

**Timeframe Weighting:**
- Longer timeframes (4h, 1d) = **Higher weight** (trend)
- Shorter timeframes (1m, 5m) = **Lower weight** (noise)

**App Logic:**
```python
def classify_mtf_consensus(signals_by_timeframe):
    # Weighted scoring
    weights = {
        '1m': 0.5, '5m': 0.75, '15m': 1.0,
        '1h': 1.5, '4h': 2.0, '1d': 2.5
    }

    bullish_score = 0
    bearish_score = 0
    total_weight = 0

    for tf, signal in signals_by_timeframe.items():
        weight = weights[tf]
        total_weight += weight

        if signal in ["Bullish", "Strong Bullish"]:
            bullish_score += weight
        elif signal in ["Bearish", "Strong Bearish"]:
            bearish_score += weight

    bullish_pct = bullish_score / total_weight
    bearish_pct = bearish_score / total_weight

    if bullish_pct > 0.8:
        return "Strong Bullish"
    elif bullish_pct > 0.6:
        return "Bullish"
    elif bearish_pct > 0.8:
        return "Strong Bearish"
    elif bearish_pct > 0.6:
        return "Bearish"
    else:
        return "Neutral"
```

---

## 8. Consolidated Quick Reference

### Master Indicator Classification Table

| Indicator | Strong Bullish | Bullish | Neutral | Bearish | Strong Bearish |
|-----------|----------------|---------|---------|---------|----------------|
| **RSI (Trending)** | >70 | 60-70 | 40-60 | 30-40 | <30 |
| **RSI (Ranging)** | — | <30 (oversold) | 30-70 | >70 (overbought) | — |
| **MACD Histogram** | >0 & ↑ | >0 | ≈0 | <0 | <0 & ↓ |
| **MFI** | — | <30 | 30-70 | >70 | — |
| **Stochastic** | Cross ↑ from <20 | <20 or cross ↑ | 20-80 | >80 or cross ↓ | Cross ↓ from >80 |
| **Williams %R** | — | <-80 | -80 to -20 | >-20 | — |
| **CCI** | <-200 | -200 to -100 | -100 to +100 | +100 to +200 | >+200 |
| **ADX + DI** | ADX>40, +DI>-DI | ADX 25-40, +DI>-DI | ADX<20 | ADX 25-40, -DI>+DI | ADX>40, -DI>+DI |
| **SuperTrend** | Price >>ST | Price > ST | — | Price < ST | Price << ST |
| **Bollinger Bands** | At upper + vol | Upper half | Middle | Lower half | At lower + vol |
| **Volume + Price** | >2.0 + up | 1.5-2.0 + up | 0.5-1.5 | 1.5-2.0 + down | >2.0 + down |
| **OBV** | Rising + price up | Rising or diverge ↑ | Flat | Falling or diverge ↓ | Falling + price down |
| **Price vs SMA** | >+5% | +2% to +5% | ±2% | -5% to -2% | <-5% |
| **MA Cross** | Price > both | Fast > Slow | Between MAs | Fast < Slow | Price < both |
| **Forecast (Daily)** | >+5% | +2% to +5% | ±2% | -5% to -2% | <-5% |
| **Forecast (Intraday)** | >+1.5% | +0.5% to +1.5% | ±0.5% | -1.5% to -0.5% | <-1.5% |

---

## 9. Implementation Guidelines

### Signal Confidence Scoring System

**Combine multiple indicators for weighted composite signals:**

```python
def calculate_composite_signal(indicators):
    """
    Calculate weighted composite signal from multiple indicators

    Weights based on indicator reliability and market context
    """

    # Define weights (adjust based on backtesting)
    weights = {
        'rsi': 1.0,
        'macd': 1.2,
        'adx': 1.5,  # High weight for trend confirmation
        'supertrend': 1.3,
        'volume_ratio': 1.1,
        'price_vs_sma': 1.0,
        'bollinger': 0.9,
        'stochastic': 0.8,
        'obv': 1.0,
        'forecast': 1.4  # ML forecast high weight
    }

    # Convert signals to scores (-2 to +2)
    signal_scores = {
        'Strong Bearish': -2,
        'Bearish': -1,
        'Neutral': 0,
        'Bullish': 1,
        'Strong Bullish': 2
    }

    weighted_sum = 0
    total_weight = 0

    for indicator, signal in indicators.items():
        if indicator in weights:
            score = signal_scores.get(signal, 0)
            weight = weights[indicator]
            weighted_sum += score * weight
            total_weight += weight

    # Calculate final score
    final_score = weighted_sum / total_weight if total_weight > 0 else 0

    # Convert to signal with confidence
    if final_score > 1.5:
        return "Strong Bullish", abs(final_score) / 2
    elif final_score > 0.5:
        return "Bullish", abs(final_score) / 2
    elif final_score < -1.5:
        return "Strong Bearish", abs(final_score) / 2
    elif final_score < -0.5:
        return "Bearish", abs(final_score) / 2
    else:
        return "Neutral", 1 - abs(final_score) / 2
```

---

### Context-Aware Threshold Adjustment

**Adapt thresholds based on asset volatility and market regime:**

```python
def adjust_thresholds_for_volatility(base_threshold, volatility_regime):
    """
    Adjust indicator thresholds based on volatility environment

    High volatility = wider neutral zones
    Low volatility = tighter thresholds
    """

    multipliers = {
        'low': 0.7,      # Tighter thresholds
        'normal': 1.0,   # Standard thresholds
        'high': 1.3,     # Wider thresholds
        'extreme': 1.6   # Much wider thresholds
    }

    multiplier = multipliers.get(volatility_regime, 1.0)
    return base_threshold * multiplier


def get_asset_specific_thresholds(asset_type, base_thresholds):
    """
    Adjust thresholds based on asset class characteristics
    """

    adjustments = {
        'crypto': 1.5,    # More volatile, wider thresholds
        'forex': 0.8,     # Less volatile, tighter thresholds
        'equity': 1.0,    # Standard
        'commodity': 1.2  # Moderately volatile
    }

    multiplier = adjustments.get(asset_type, 1.0)

    return {
        key: value * multiplier
        for key, value in base_thresholds.items()
    }
```

---

### Divergence Detection

**Identify powerful reversal signals through indicator-price divergences:**

```python
def detect_divergence(price_series, indicator_series, lookback=20):
    """
    Detect bullish/bearish divergences between price and indicator

    Bullish divergence: Price making lower lows, indicator making higher lows
    Bearish divergence: Price making higher highs, indicator making lower highs
    """

    # Find recent peaks and troughs
    price_peaks = find_peaks(price_series, lookback)
    price_troughs = find_troughs(price_series, lookback)
    indicator_peaks = find_peaks(indicator_series, lookback)
    indicator_troughs = find_troughs(indicator_series, lookback)

    # Bullish divergence
    if len(price_troughs) >= 2 and len(indicator_troughs) >= 2:
        price_lower_low = price_troughs[-1] < price_troughs[-2]
        indicator_higher_low = indicator_troughs[-1] > indicator_troughs[-2]

        if price_lower_low and indicator_higher_low:
            return "Bullish Divergence"

    # Bearish divergence
    if len(price_peaks) >= 2 and len(indicator_peaks) >= 2:
        price_higher_high = price_peaks[-1] > price_peaks[-2]
        indicator_lower_high = indicator_peaks[-1] < indicator_peaks[-2]

        if price_higher_high and indicator_lower_high:
            return "Bearish Divergence"

    return "No Divergence"
```

---

### Signal Filtering & Confirmation

**Reduce false signals through multi-indicator confirmation:**

```python
def require_confirmation(primary_signal, confirming_indicators, min_confirmations=2):
    """
    Require N confirming indicators before acting on primary signal

    Example: RSI oversold + volume spike + bullish MACD cross = confirmed
    """

    signal_alignment = {
        'Strong Bullish': ['Strong Bullish', 'Bullish'],
        'Bullish': ['Strong Bullish', 'Bullish'],
        'Bearish': ['Strong Bearish', 'Bearish'],
        'Strong Bearish': ['Strong Bearish', 'Bearish']
    }

    if primary_signal == 'Neutral':
        return primary_signal, 0

    aligned_signals = signal_alignment.get(primary_signal, [])
    confirmations = sum(
        1 for signal in confirming_indicators
        if signal in aligned_signals
    )

    if confirmations >= min_confirmations:
        return primary_signal, confirmations / len(confirming_indicators)
    else:
        return 'Neutral', 0  # Not enough confirmation
```

---

## 10. Code References

### Client (macOS SwiftUI)
**File:** `client-macos/SwiftBoltML/Models/TechnicalIndicatorsModels.swift`
- RSI interpretation
- MACD histogram categorization
- Price vs SMA distance
- Volume ratio classification
- Display logic for all indicators

### ML Pipeline (Python)
**File:** `ml/src/strategies/multi_indicator_signals.py`
- RSI signal generation
- Stochastic oscillator logic
- Volume-based signals
- Multi-indicator combination

**File:** `ml/src/models/forecast_explainer.py`
- RSI/MACD/ADX interpretation
- Price momentum analysis
- Volume confirmation logic
- Feature importance ranking

**File:** `ml/src/models/lstm_forecaster.py`
**File:** `ml/src/models/arima_garch_forecaster.py`
- Bullish/bearish forecast thresholds
- Confidence scoring
- Return predictions

**File:** `ml/src/evaluation_job_daily.py`
**File:** `ml/src/evaluation_job_intraday.py`
- BEARISH_THRESHOLD = -0.02 (daily), -0.005 (intraday)
- BULLISH_THRESHOLD = +0.02 (daily), +0.005 (intraday)
- Performance evaluation metrics

**File:** `ml/src/features/support_resistance_detector.py`
- Polynomial S/R bias calculation
- Logistic regression probability
- Support/resistance slope analysis

---

## 11. Best Practices

### Multi-Indicator Confirmation Strategy

**Never trade on a single indicator. Use this confirmation hierarchy:**

1. **Trend Confirmation** (ADX + SuperTrend + Moving Averages)
   - Establish if market is trending or ranging
   - Determine trend direction and strength

2. **Momentum Confirmation** (RSI + MACD + Stochastic)
   - Confirm strength of the move
   - Check for overbought/oversold extremes

3. **Volume Confirmation** (Volume Ratio + OBV)
   - Validate with volume participation
   - Strong moves need volume support

4. **Support/Resistance Context** (S/R Levels + Bollinger Bands)
   - Identify risk/reward levels
   - Set stop-loss and target zones

5. **ML Forecast** (LSTM/ARIMA predictions)
   - Use as tie-breaker or confidence boost
   - Weight by model accuracy metrics

### Risk Management Integration

**Adjust position sizing based on signal strength:**

```python
def calculate_position_size(base_size, signal_confidence, indicator_agreement):
    """
    Scale position size based on signal quality

    High confidence + high agreement = larger position
    Low confidence or low agreement = smaller position
    """

    confidence_multiplier = signal_confidence  # 0.0 to 1.0
    agreement_multiplier = indicator_agreement  # 0.0 to 1.0

    # Geometric mean of confidence and agreement
    quality_score = (confidence_multiplier * agreement_multiplier) ** 0.5

    # Scale position: 25% to 100% of base size
    position_multiplier = 0.25 + (0.75 * quality_score)

    return base_size * position_multiplier
```

---

## 12. Summary & Decision Framework

### Quick Decision Tree

```
1. Check TREND (ADX, SuperTrend, MAs)
   ├── Strong trend? → Follow trend indicators
   └── Weak/No trend? → Use reversal indicators (RSI, Stochastic)

2. Check MOMENTUM (RSI, MACD, MFI)
   ├── Overbought/Oversold? → Look for reversal signals
   └── Normal range? → Confirm trend direction

3. Check VOLUME (Volume Ratio, OBV)
   ├── High volume? → Trust the signal more
   └── Low volume? → Wait for confirmation

4. Check S/R LEVELS
   ├── Near support? → Bullish bias
   └── Near resistance? → Bearish bias

5. Check ML FORECAST
   ├── High confidence prediction? → Use as confirmation
   └── Low confidence? → Ignore or use as tie-breaker

6. AGGREGATE SIGNALS
   ├── 70%+ agreement? → Strong signal, act
   ├── 50-70% agreement? → Moderate signal, reduced size
   └── <50% agreement? → Neutral, wait for clarity
```

---

## Revision History

- **v1.0** - January 29, 2026: Initial refined classification guide
- Replaced original technicalsummary.md with context-aware thresholds
- Added implementation guidelines and code examples
- Included divergence detection and confirmation strategies

---

## Next Steps

1. **Backtesting**: Validate thresholds against historical data for your specific assets
2. **Optimization**: Use machine learning to optimize indicator weights
3. **A/B Testing**: Compare performance of different threshold values
4. **Real-time Monitoring**: Track indicator accuracy and adjust dynamically
5. **User Feedback**: Allow traders to customize thresholds for their style

---

**Questions or need specific implementation help?** Reference this guide when building signal generation logic in your Swift/Python codebase.
