# Technical Indicators & ML Strategy Improvement Plan

## Overview

This document outlines a comprehensive plan to improve technical indicators and ML strategies for the **SwiftBolt_ML** project. We use `stock-whisperer-ai-04` as **inspiration only** for indicator implementations and ML patterns, but all code is implemented on the SwiftBolt_ML foundation using its existing APIs, database schema, and GitHub Actions infrastructure.

### Architecture Principles

1. **SwiftBolt_ML is the foundation** - All implementations use existing SwiftBolt_ML infrastructure
2. **stock-whisperer-ai-04 is reference only** - We borrow indicator logic/patterns, not code directly
3. **Leverage existing data pipelines** - GitHub Actions already backfill OHLC and options data
4. **No redundant data fetching** - Use cached Supabase data, don't re-fetch from APIs

---

## Existing Data Infrastructure (SwiftBolt_ML)

### GitHub Actions Workflows

| Workflow | Schedule | Purpose | Data Stored |
|----------|----------|---------|-------------|
| `backfill-ohlc.yml` | Every 6 hours | Fetch OHLC bars for watchlist symbols | `ohlc_bars` table |
| `options-nightly.yml` | Weeknights 02:00 UTC | Fetch options chains + ML ranking | `options_chain_snapshots`, `options_ranks` |

### Database Tables (Supabase)

| Table | Contents | Used By |
|-------|----------|---------|
| `symbols` | Ticker metadata | All jobs |
| `ohlc_bars` | Historical OHLC data (d1 timeframe) | Forecast job, Options ranking |
| `ml_forecasts` | ML predictions (Bullish/Neutral/Bearish) | Swift app |
| `options_ranks` | ML-scored options contracts | Swift app |
| `options_chain_snapshots` | Raw options chain data | Options ranking job |

### Current Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (Scheduled)                       │
├─────────────────────────────────────────────────────────────────────┤
│  backfill-ohlc.yml (6hr)     │    options-nightly.yml (daily)       │
│  ↓                           │    ↓                                  │
│  Polygon API → ohlc_bars     │    Tradier API → options_snapshots   │
│                              │    ↓                                  │
│                              │    OptionsRanker → options_ranks      │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         Supabase Database                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  ohlc_bars   │  │ ml_forecasts │  │ options_ranks            │   │
│  │  (cached)    │  │ (predictions)│  │ (ML-scored contracts)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         Swift macOS App                              │
│  - Reads ohlc_bars for charts                                        │
│  - Reads ml_forecasts for predictions                                │
│  - Reads options_ranks for ranked options                            │
│  - Computes indicators client-side (TechnicalIndicators.swift)       │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Optimization: No Redundant Fetching

The improvement plan **does NOT require additional API calls** for basic data:

| Data Need | Source | Already Available? |
|-----------|--------|-------------------|
| Daily OHLC | `ohlc_bars` table | ✅ Yes (backfill-ohlc.yml) |
| Options chains | `options_chain_snapshots` | ✅ Yes (options-nightly.yml) |
| Multi-timeframe OHLC | Need to extend backfill | ⚠️ Partial (only d1 currently) |

### Required Extension: Multi-Timeframe Backfill

To support multi-timeframe features (m15, h1, d1, w1), we need to **extend the existing backfill workflow**, not create a new one:

```yaml
# Update backfill-ohlc.yml to support multiple timeframes
- name: Backfill all timeframes (scheduled)
  run: |
    cd ml
    # Backfill each timeframe incrementally
    for TF in d1 h1 m15 w1; do
      python src/scripts/backfill_ohlc.py --all --incremental --timeframe $TF
    done
```

---

## Current State Analysis

### SwiftBolt_ML (Current Project)

**Location**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/`

#### Technical Indicators (`features/technical_indicators.py`)
| Indicator | Implementation | Status |
|-----------|---------------|--------|
| Returns (1d, 5d, 20d) | `pct_change()` | ✅ Basic |
| SMA (5, 20, 50) | `rolling().mean()` | ✅ Basic |
| EMA (12, 26) | `ewm().mean()` | ✅ Basic |
| MACD + Signal + Histogram | EMA-based | ✅ Complete |
| RSI (14) | Custom function | ✅ Complete |
| Bollinger Bands | SMA ± 2σ | ✅ Complete |
| ATR (14) | True Range EMA | ✅ Complete |
| Volume SMA + Ratio | Rolling | ✅ Basic |
| Volatility (20d) | Rolling std | ✅ Basic |
| Price vs SMA | Relative position | ✅ Basic |

#### ML Models (`models/`)
| Model | Purpose | Status |
|-------|---------|--------|
| `BaselineForecaster` | Random Forest for price direction (Bullish/Neutral/Bearish) | ✅ Working |
| `OptionsRanker` | Weighted scoring for options contracts | ✅ Working |

---

### Stock-Whisperer-AI-04 (Source Repository)

**Location**: `https://github.com/PapaPablano/stock-whisperer-ai-04`

#### Technical Indicators (`src/lib/technicalIndicators.ts`)
| Indicator | Implementation | Missing in SwiftBolt |
|-----------|---------------|---------------------|
| SMA | Multiple periods | ❌ Need more periods |
| EMA | Multiple periods | ❌ Need more periods |
| RSI | Period 14 | ✅ Have it |
| MACD | 12/26/9 | ✅ Have it |
| **Stochastic Oscillator** | K/D lines | ❌ **MISSING** |
| **KDJ Indicator** | K/D/J with J-D divergence | ❌ **MISSING** |
| Bollinger Bands | 20, ±2σ | ✅ Have it |
| ATR | Period 14 | ✅ Have it |
| **Keltner Channel** | EMA + ATR bands | ❌ **MISSING** |
| **OBV** | On-Balance Volume | ❌ **MISSING** |
| **VROC** | Volume Rate of Change | ❌ **MISSING** |
| **MFI** | Money Flow Index | ❌ **MISSING** |
| **ADX** | Average Directional Index | ❌ **MISSING** |

#### SuperTrend AI (`src/lib/superTrendAI.ts`)
| Feature | Description | Priority |
|---------|-------------|----------|
| Adaptive ATR Multiplier | K-means clustering for optimal factor | 🔴 HIGH |
| Performance Index | EMA-smoothed performance tracking | 🔴 HIGH |
| Trend Regime Detection | Bull/Bear with confirmation bars | 🟡 MEDIUM |
| Signal Metrics | Confidence, stop levels, take profit | 🟡 MEDIUM |
| Cluster Diagnostics | Best/Average/Worst factor analysis | 🟢 LOW |

#### ML Signals Edge Function (`supabase/functions/ml-signals/`)
- Simple RSI-based signal generation (Buy/Hold/Sell)
- Uses Alpaca API for daily bars
- Basic threshold logic (RSI > 70 = Sell, RSI < 30 = Buy)

---

## Improvement Plan

### Phase 1: Expand Technical Indicators (Priority: HIGH)

#### 1.1 Add Missing Momentum Indicators

```python
# Add to technical_indicators.py

def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator (%K and %D).
    """
    lowest_low = df['low'].rolling(window=k_period).min()
    highest_high = df['high'].rolling(window=k_period).max()
    
    df['stoch_k'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
    df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
    
    return df


def calculate_kdj(df: pd.DataFrame, period: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    """
    Calculate KDJ Indicator with J line for early reversal detection.
    J = 3*K - 2*D (more sensitive than K or D alone)
    """
    lowest_low = df['low'].rolling(window=period).min()
    highest_high = df['high'].rolling(window=period).max()
    
    rsv = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
    
    df['kdj_k'] = rsv.rolling(window=k_smooth).mean()
    df['kdj_d'] = df['kdj_k'].rolling(window=d_smooth).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
    df['kdj_j_minus_d'] = df['kdj_j'] - df['kdj_d']  # Divergence signal
    
    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index for trend strength.
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # +DM and -DM
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Smoothed averages
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    # DX and ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.rolling(window=period).mean()
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    
    return df
```

#### 1.2 Add Missing Volume Indicators

```python
def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate On-Balance Volume.
    """
    obv = [df['volume'].iloc[0]]
    
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    
    df['obv'] = obv
    df['obv_sma'] = df['obv'].rolling(window=20).mean()
    
    return df


def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Money Flow Index (volume-weighted RSI).
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    
    positive_flow = money_flow.where(typical_price > typical_price.shift(), 0)
    negative_flow = money_flow.where(typical_price < typical_price.shift(), 0)
    
    positive_mf = positive_flow.rolling(window=period).sum()
    negative_mf = negative_flow.rolling(window=period).sum()
    
    money_ratio = positive_mf / negative_mf
    df['mfi'] = 100 - (100 / (1 + money_ratio))
    
    return df


def calculate_vroc(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Volume Rate of Change.
    """
    df['vroc'] = ((df['volume'] - df['volume'].shift(period)) / df['volume'].shift(period)) * 100
    return df
```

#### 1.3 Add Volatility Indicators

```python
def calculate_keltner_channel(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
    """
    Calculate Keltner Channel (EMA-based volatility bands).
    """
    df['keltner_middle'] = df['close'].ewm(span=ema_period, adjust=False).mean()
    
    # ATR for channel width
    tr = calculate_atr(df.copy(), period=atr_period)['atr_14']
    
    df['keltner_upper'] = df['keltner_middle'] + (tr * multiplier)
    df['keltner_lower'] = df['keltner_middle'] - (tr * multiplier)
    
    return df
```

---

### Phase 2: Port SuperTrend AI Strategy (Priority: HIGH)

#### 2.1 Core SuperTrend Implementation

```python
# New file: ml/src/strategies/supertrend_ai.py

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from typing import Tuple, Dict, Any

class SuperTrendAI:
    """
    Adaptive SuperTrend indicator with ML-optimized ATR multiplier.
    
    Uses K-means clustering to find optimal factor from performance analysis.
    """
    
    def __init__(
        self,
        atr_length: int = 10,
        min_multiplier: float = 1.0,
        max_multiplier: float = 5.0,
        step: float = 0.5,
        perf_alpha: float = 10.0,
        from_cluster: str = "Best",  # Best, Average, Worst
        max_iter: int = 1000,
    ):
        self.atr_length = atr_length
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier
        self.step = step
        self.perf_alpha = perf_alpha
        self.from_cluster = from_cluster
        self.max_iter = max_iter
        
        self.factors = self._generate_factors()
        self.target_factor = min_multiplier
        self.performance_index = 0.0
    
    def _generate_factors(self) -> np.ndarray:
        """Generate array of factors to test."""
        return np.arange(self.min_multiplier, self.max_multiplier + self.step, self.step)
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR using EMA smoothing."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.ewm(span=self.atr_length, adjust=False).mean()
    
    def _calculate_supertrend_for_factor(
        self, df: pd.DataFrame, atr: pd.Series, factor: float
    ) -> Tuple[pd.Series, pd.Series]:
        """Calculate SuperTrend for a single factor."""
        hl2 = (df['high'] + df['low']) / 2
        
        upper_band = hl2 + (atr * factor)
        lower_band = hl2 - (atr * factor)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        final_upper = upper_band.copy()
        final_lower = lower_band.copy()
        
        for i in range(1, len(df)):
            # Adjust bands based on previous values
            if upper_band.iloc[i] < final_upper.iloc[i-1] or df['close'].iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]
            
            if lower_band.iloc[i] > final_lower.iloc[i-1] or df['close'].iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]
            
            # Determine trend
            if df['close'].iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1  # Bullish
            elif df['close'].iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = -1  # Bearish
            else:
                trend.iloc[i] = trend.iloc[i-1] if i > 0 else 0
            
            # Set SuperTrend value
            supertrend.iloc[i] = final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]
        
        return supertrend, trend
    
    def _calculate_performance(
        self, df: pd.DataFrame, supertrend: pd.Series, trend: pd.Series
    ) -> float:
        """Calculate performance score for a SuperTrend configuration."""
        alpha = min(2 / (self.perf_alpha + 1), 0.99) if self.perf_alpha > 1 else self.perf_alpha
        
        perf_numerator = 0.0
        perf_denominator = 0.0
        
        for i in range(1, len(df)):
            prev_close = df['close'].iloc[i-1]
            curr_close = df['close'].iloc[i]
            prev_st = supertrend.iloc[i-1] if pd.notna(supertrend.iloc[i-1]) else prev_close
            
            delta = curr_close - prev_close
            signed_delta = delta * np.sign(prev_close - prev_st)
            abs_delta = abs(delta)
            
            perf_numerator = alpha * signed_delta + (1 - alpha) * perf_numerator
            perf_denominator = alpha * abs_delta + (1 - alpha) * perf_denominator
        
        return perf_numerator / perf_denominator if perf_denominator != 0 else 0
    
    def fit(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Fit the SuperTrend AI model to find optimal factor.
        
        Returns:
            Dictionary with optimal factor, performance metrics, and cluster info
        """
        atr = self._calculate_atr(df)
        
        # Test all factors
        performances = []
        for factor in self.factors:
            supertrend, trend = self._calculate_supertrend_for_factor(df, atr, factor)
            perf = self._calculate_performance(df, supertrend, trend)
            performances.append(perf)
        
        performances = np.array(performances)
        
        # K-means clustering (3 clusters: Best, Average, Worst)
        if len(self.factors) >= 3:
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10, max_iter=self.max_iter)
            cluster_labels = kmeans.fit_predict(performances.reshape(-1, 1))
            
            # Identify clusters by mean performance
            cluster_means = {}
            for i in range(3):
                mask = cluster_labels == i
                cluster_means[i] = performances[mask].mean()
            
            sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1], reverse=True)
            cluster_mapping = {
                sorted_clusters[0][0]: "Best",
                sorted_clusters[1][0]: "Average",
                sorted_clusters[2][0]: "Worst",
            }
            
            # Select target cluster
            target_cluster_id = [k for k, v in cluster_mapping.items() if v == self.from_cluster][0]
            target_mask = cluster_labels == target_cluster_id
            target_factors = self.factors[target_mask]
            
            self.target_factor = target_factors.mean()
        else:
            self.target_factor = self.factors[np.argmax(performances)]
            cluster_mapping = {}
        
        # Calculate final SuperTrend with optimal factor
        supertrend, trend = self._calculate_supertrend_for_factor(df, atr, self.target_factor)
        self.performance_index = self._calculate_performance(df, supertrend, trend)
        
        return {
            "target_factor": self.target_factor,
            "performance_index": self.performance_index,
            "factors_tested": self.factors.tolist(),
            "performances": performances.tolist(),
            "cluster_mapping": cluster_mapping,
        }
    
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate SuperTrend signals using the fitted optimal factor.
        """
        atr = self._calculate_atr(df)
        supertrend, trend = self._calculate_supertrend_for_factor(df, atr, self.target_factor)
        
        df = df.copy()
        df['supertrend'] = supertrend
        df['supertrend_trend'] = trend
        df['supertrend_signal'] = trend.diff().fillna(0)  # 1 = Buy, -1 = Sell, 0 = Hold
        
        return df
```

---

### Phase 3: Enhanced ML Strategies (Priority: MEDIUM)

#### 3.1 Multi-Indicator Signal Generator

```python
# New file: ml/src/strategies/multi_indicator_signals.py

class MultiIndicatorSignalGenerator:
    """
    Generates trading signals by combining multiple technical indicators.
    """
    
    def __init__(self):
        self.indicator_weights = {
            'rsi': 0.15,
            'macd': 0.15,
            'kdj': 0.15,
            'adx': 0.10,
            'bollinger': 0.10,
            'volume': 0.10,
            'supertrend': 0.25,
        }
    
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate composite signal from all indicators.
        
        Returns:
            {
                'signal': 'Buy' | 'Sell' | 'Hold',
                'confidence': 0.0-1.0,
                'components': {...}
            }
        """
        signals = {}
        
        # RSI Signal
        rsi = df['rsi_14'].iloc[-1]
        if rsi < 30:
            signals['rsi'] = 1.0  # Oversold = Buy
        elif rsi > 70:
            signals['rsi'] = -1.0  # Overbought = Sell
        else:
            signals['rsi'] = 0.0
        
        # MACD Signal
        macd_hist = df['macd_hist'].iloc[-1]
        macd_hist_prev = df['macd_hist'].iloc[-2]
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            signals['macd'] = 1.0
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            signals['macd'] = -1.0
        else:
            signals['macd'] = 0.0
        
        # KDJ Signal (if available)
        if 'kdj_j' in df.columns:
            j = df['kdj_j'].iloc[-1]
            if j < 0:
                signals['kdj'] = 1.0  # Oversold
            elif j > 100:
                signals['kdj'] = -1.0  # Overbought
            else:
                signals['kdj'] = 0.0
        
        # ADX Signal (trend strength)
        if 'adx' in df.columns:
            adx = df['adx'].iloc[-1]
            plus_di = df['plus_di'].iloc[-1]
            minus_di = df['minus_di'].iloc[-1]
            
            if adx > 25:  # Strong trend
                if plus_di > minus_di:
                    signals['adx'] = 1.0
                else:
                    signals['adx'] = -1.0
            else:
                signals['adx'] = 0.0
        
        # Bollinger Band Signal
        close = df['close'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        
        if close < bb_lower:
            signals['bollinger'] = 1.0  # Below lower band = Buy
        elif close > bb_upper:
            signals['bollinger'] = -1.0  # Above upper band = Sell
        else:
            signals['bollinger'] = 0.0
        
        # Volume Signal
        if 'volume_ratio' in df.columns:
            vol_ratio = df['volume_ratio'].iloc[-1]
            if vol_ratio > 1.5:  # High volume confirms trend
                signals['volume'] = signals.get('macd', 0) * 0.5
            else:
                signals['volume'] = 0.0
        
        # SuperTrend Signal (if available)
        if 'supertrend_trend' in df.columns:
            trend = df['supertrend_trend'].iloc[-1]
            signals['supertrend'] = float(trend)
        
        # Weighted composite
        composite = 0.0
        total_weight = 0.0
        
        for indicator, weight in self.indicator_weights.items():
            if indicator in signals:
                composite += signals[indicator] * weight
                total_weight += weight
        
        if total_weight > 0:
            composite /= total_weight
        
        # Determine final signal
        if composite > 0.3:
            signal = 'Buy'
        elif composite < -0.3:
            signal = 'Sell'
        else:
            signal = 'Hold'
        
        confidence = min(abs(composite), 1.0)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'composite_score': composite,
            'components': signals,
        }
```

#### 3.2 Enhanced Baseline Forecaster

```python
# Improvements to baseline_forecaster.py

# Add these features to the model:
ENHANCED_FEATURES = [
    # Existing
    'returns_1d', 'returns_5d', 'returns_20d',
    'sma_5', 'sma_20', 'sma_50',
    'ema_12', 'ema_26',
    'macd', 'macd_signal', 'macd_hist',
    'rsi_14',
    'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
    'atr_14',
    'volume_ratio',
    'volatility_20d',
    'price_vs_sma20', 'price_vs_sma50',
    
    # NEW: Momentum
    'stoch_k', 'stoch_d',
    'kdj_k', 'kdj_d', 'kdj_j', 'kdj_j_minus_d',
    'adx', 'plus_di', 'minus_di',
    
    # NEW: Volume
    'obv', 'obv_sma',
    'mfi',
    'vroc',
    
    # NEW: Volatility
    'keltner_upper', 'keltner_middle', 'keltner_lower',
    
    # NEW: SuperTrend
    'supertrend', 'supertrend_trend',
]

# Consider upgrading to:
# - XGBoost or LightGBM for better performance
# - LSTM for sequence modeling
# - Ensemble of multiple models
```

---

### Phase 4: Multi-Timeframe Analysis (Priority: MEDIUM)

#### 4.1 Timeframe Aggregator

```python
# New file: ml/src/features/multi_timeframe.py

class MultiTimeframeFeatures:
    """
    Compute indicators across multiple timeframes for attention-based models.
    """
    
    # User-selected timeframes (all supported by current API)
    # See: ChartViewModel.availableTimeframes = ["m15", "h1", "h4", "d1", "w1"]
    TIMEFRAMES = ['m15', 'h1', 'd1', 'w1']  # 15min, 1hr, 1day, 1week
    
    def __init__(self, indicators_func):
        self.indicators_func = indicators_func
    
    def compute_all_timeframes(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Compute indicators for all timeframes and align to common index.
        
        Args:
            data_dict: {'m15': df_15m, 'h1': df_1h, 'd1': df_1d, 'w1': df_1w}
        
        Returns:
            DataFrame with columns like 'rsi_14_m15', 'rsi_14_h1', 'rsi_14_d1', 'rsi_14_w1', etc.
        """
        all_features = {}
        
        for tf, df in data_dict.items():
            df_with_indicators = self.indicators_func(df)
            
            for col in df_with_indicators.columns:
                if col not in ['ts', 'open', 'high', 'low', 'close', 'volume']:
                    all_features[f'{col}_{tf}'] = df_with_indicators[col]
        
        return pd.DataFrame(all_features)
    
    def compute_alignment_score(self, features_df: pd.DataFrame) -> pd.Series:
        """
        Compute cross-timeframe trend alignment score.
        
        Higher score = more timeframes agree on direction.
        """
        trend_cols = [col for col in features_df.columns if 'trend' in col.lower()]
        
        if not trend_cols:
            return pd.Series(0.5, index=features_df.index)
        
        alignment = features_df[trend_cols].mean(axis=1)
        return (alignment + 1) / 2  # Normalize to 0-1
```

---

### Phase 5: Integration & Testing (Priority: HIGH)

#### 5.1 Updated Feature Pipeline

```python
# Update add_technical_features() to include all new indicators

def add_all_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add comprehensive technical indicators for ML training.
    """
    df = df.copy()
    
    # Existing indicators
    df = add_technical_features(df)  # Current implementation
    
    # New momentum indicators
    df = calculate_stochastic(df)
    df = calculate_kdj(df)
    df = calculate_adx(df)
    
    # New volume indicators
    df = calculate_obv(df)
    df = calculate_mfi(df)
    df = calculate_vroc(df)
    
    # New volatility indicators
    df = calculate_keltner_channel(df)
    
    # SuperTrend AI
    supertrend_ai = SuperTrendAI()
    supertrend_ai.fit(df)
    df = supertrend_ai.predict(df)
    
    return df
```

#### 5.2 Testing Checklist

- [ ] Unit tests for each new indicator
- [ ] Comparison with TypeScript implementations (stock-whisperer-ai-04)
- [ ] Backtest SuperTrend AI on historical data
- [ ] Validate multi-indicator signal generator
- [ ] Performance benchmarks for feature computation
- [ ] Integration tests with existing ML models

---

## Implementation Priority

| Phase | Description | Effort | Impact | Priority |
|-------|-------------|--------|--------|----------|
| 1.1 | Add Stochastic, KDJ, ADX | 2 days | High | ✅ DONE |
| 1.2 | Add OBV, MFI, VROC | 1 day | Medium | ✅ DONE |
| 1.3 | Add Keltner Channel | 0.5 days | Low | ✅ DONE |
| 2.1 | Port SuperTrend AI | 3 days | Very High | ✅ DONE |
| 3.1 | Multi-Indicator Signals | 2 days | High | ✅ DONE |
| 3.2 | Enhanced Forecaster | 2 days | High | ✅ DONE |
| 4.1 | Multi-Timeframe Features | 3 days | Very High | ✅ DONE |
| 5.1 | Integration | 2 days | Critical | ✅ DONE |
| 5.2 | Testing | 3 days | Critical | ✅ DONE |

**Total Estimated Effort**: ~18 days

---

## Files to Create/Modify

### New Files
```
ml/src/features/
├── technical_indicators.py  # MODIFY: Add new indicators
├── multi_timeframe.py       # NEW: Multi-timeframe features

ml/src/strategies/
├── __init__.py              # NEW
├── supertrend_ai.py         # NEW: Port from TypeScript
├── multi_indicator_signals.py  # NEW: Composite signals

ml/src/models/
├── baseline_forecaster.py   # MODIFY: Use enhanced features
├── options_ranker.py        # MODIFY: Add SuperTrend signals
```

### Configuration
```
ml/config/
├── indicators.yaml          # NEW: Indicator parameters
├── strategies.yaml          # NEW: Strategy weights
```

---

## Success Metrics

1. **Indicator Parity**: All 17 indicators from stock-whisperer-ai-04 implemented
2. **SuperTrend AI**: Performance index > 0.5 on backtests
3. **Signal Accuracy**: Multi-indicator signals > 55% accuracy
4. **Forecast Improvement**: Baseline forecaster accuracy +5% with new features
5. **Options Ranking**: Improved scoring with trend alignment
6. **Swift App**: All new indicators available in charts
7. **End-to-End**: Options ranked using SuperTrend + multi-indicator signals

---

## Phase 6: Enhanced Options Ranking Integration (Priority: HIGH)

### 6.1 Current Options Ranker Limitations

The current `OptionsRanker` (`ml/src/models/options_ranker.py`) uses:
- Basic `underlying_trend` parameter (bullish/neutral/bearish)
- Simple momentum scoring based on trend string
- No integration with actual technical indicators

### 6.2 Enhanced Options Ranker with ML Indicators

```python
# Enhanced options_ranker.py

class EnhancedOptionsRanker:
    """
    Options ranker that integrates with full technical indicator suite.
    """
    
    def __init__(self):
        self.weights = {
            "moneyness": 0.20,
            "iv_rank": 0.15,
            "liquidity": 0.10,
            "delta_score": 0.10,
            "theta_decay": 0.08,
            # NEW: ML-derived scores
            "supertrend_alignment": 0.15,  # SuperTrend AI signal
            "multi_indicator_score": 0.12,  # Composite indicator signal
            "trend_strength": 0.10,  # ADX-based
        }
        
        self.supertrend_ai = None
        self.signal_generator = None
    
    def rank_options_with_indicators(
        self,
        options_df: pd.DataFrame,
        underlying_df: pd.DataFrame,  # OHLCV with indicators
        underlying_price: float,
        historical_vol: float = 0.30,
    ) -> pd.DataFrame:
        """
        Rank options using full technical indicator analysis.
        
        Args:
            options_df: Options chain data
            underlying_df: Underlying price data WITH technical indicators
            underlying_price: Current underlying price
            historical_vol: Historical volatility
        
        Returns:
            Ranked options with ml_score and component breakdown
        """
        df = options_df.copy()
        
        # Get ML-derived trend from indicators
        trend_analysis = self._analyze_underlying_trend(underlying_df)
        
        # Existing scores
        df["moneyness_score"] = self._score_moneyness(
            df["strike"], df["side"], underlying_price, trend_analysis["trend"]
        )
        df["iv_rank_score"] = self._score_iv_rank(df["impliedVolatility"], historical_vol)
        df["liquidity_score"] = self._score_liquidity(df["volume"], df["openInterest"])
        df["delta_score"] = self._score_delta(df["delta"], df["side"], trend_analysis["trend"])
        df["theta_decay_score"] = self._score_theta(df["theta"], df["side"], df["expiration"])
        
        # NEW: SuperTrend alignment score
        df["supertrend_alignment_score"] = self._score_supertrend_alignment(
            df["side"], trend_analysis["supertrend_signal"]
        )
        
        # NEW: Multi-indicator composite score
        df["multi_indicator_score"] = self._score_multi_indicator(
            df["side"], trend_analysis["composite_signal"]
        )
        
        # NEW: Trend strength score (ADX-based)
        df["trend_strength_score"] = self._score_trend_strength(
            df["side"], trend_analysis["adx"], trend_analysis["trend"]
        )
        
        # Weighted composite
        df["ml_score"] = sum(
            df[f"{component}_score"] * weight 
            for component, weight in self.weights.items()
            if f"{component}_score" in df.columns
        )
        
        # Normalize and sort
        df["ml_score"] = (df["ml_score"] / df["ml_score"].max()).clip(0, 1)
        df = df.sort_values("ml_score", ascending=False).reset_index(drop=True)
        
        # Add trend analysis metadata
        df.attrs["trend_analysis"] = trend_analysis
        
        return df
    
    def _analyze_underlying_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Comprehensive trend analysis using all available indicators.
        """
        latest = df.iloc[-1]
        
        # SuperTrend signal
        supertrend_signal = 0
        if 'supertrend_trend' in df.columns:
            supertrend_signal = int(latest['supertrend_trend'])
        
        # ADX trend strength
        adx = latest.get('adx', 20)
        plus_di = latest.get('plus_di', 50)
        minus_di = latest.get('minus_di', 50)
        
        # RSI
        rsi = latest.get('rsi_14', 50)
        
        # MACD
        macd_hist = latest.get('macd_hist', 0)
        
        # KDJ
        kdj_j = latest.get('kdj_j', 50)
        
        # Composite signal (-1 to 1)
        signals = []
        
        if supertrend_signal != 0:
            signals.append(supertrend_signal * 0.3)
        
        if adx > 25:
            di_signal = 1 if plus_di > minus_di else -1
            signals.append(di_signal * 0.2)
        
        if rsi < 30:
            signals.append(0.15)  # Oversold = bullish
        elif rsi > 70:
            signals.append(-0.15)  # Overbought = bearish
        
        if macd_hist > 0:
            signals.append(0.15)
        elif macd_hist < 0:
            signals.append(-0.15)
        
        if kdj_j < 0:
            signals.append(0.1)  # Oversold
        elif kdj_j > 100:
            signals.append(-0.1)  # Overbought
        
        composite = sum(signals) if signals else 0
        
        # Determine trend label
        if composite > 0.2:
            trend = "bullish"
        elif composite < -0.2:
            trend = "bearish"
        else:
            trend = "neutral"
        
        return {
            "trend": trend,
            "composite_signal": composite,
            "supertrend_signal": supertrend_signal,
            "adx": adx,
            "rsi": rsi,
            "confidence": min(abs(composite) * 2, 1.0),
        }
    
    def _score_supertrend_alignment(self, sides: pd.Series, supertrend_signal: int) -> pd.Series:
        """Score based on SuperTrend alignment."""
        scores = pd.Series(0.5, index=sides.index)
        
        for idx in sides.index:
            side = sides.loc[idx]
            if supertrend_signal == 1 and side == "call":
                scores.loc[idx] = 1.0
            elif supertrend_signal == -1 and side == "put":
                scores.loc[idx] = 1.0
            elif supertrend_signal == 0:
                scores.loc[idx] = 0.5
            else:
                scores.loc[idx] = 0.2  # Counter-trend
        
        return scores
    
    def _score_multi_indicator(self, sides: pd.Series, composite_signal: float) -> pd.Series:
        """Score based on multi-indicator composite signal."""
        scores = pd.Series(0.5, index=sides.index)
        
        for idx in sides.index:
            side = sides.loc[idx]
            if composite_signal > 0 and side == "call":
                scores.loc[idx] = 0.5 + abs(composite_signal) * 0.5
            elif composite_signal < 0 and side == "put":
                scores.loc[idx] = 0.5 + abs(composite_signal) * 0.5
            else:
                scores.loc[idx] = 0.5 - abs(composite_signal) * 0.3
        
        return scores.clip(0, 1)
    
    def _score_trend_strength(self, sides: pd.Series, adx: float, trend: str) -> pd.Series:
        """Score based on ADX trend strength."""
        scores = pd.Series(0.5, index=sides.index)
        
        # Strong trend (ADX > 25) favors directional options
        if adx > 25:
            strength_bonus = min((adx - 25) / 25, 0.5)
            for idx in sides.index:
                side = sides.loc[idx]
                if (trend == "bullish" and side == "call") or (trend == "bearish" and side == "put"):
                    scores.loc[idx] = 0.5 + strength_bonus
                else:
                    scores.loc[idx] = 0.5 - strength_bonus * 0.5
        
        return scores.clip(0, 1)
```

### 6.3 Options Ranking API Enhancement

```python
# Update options_ranking_job.py to use enhanced ranker

async def rank_options_for_symbol(symbol: str, expiration: str) -> Dict:
    """
    Enhanced options ranking with full indicator integration.
    """
    # Fetch underlying price data
    underlying_df = await fetch_underlying_with_indicators(symbol)
    
    # Add all technical indicators
    underlying_df = add_all_technical_features(underlying_df)
    
    # Fit SuperTrend AI
    supertrend_ai = SuperTrendAI()
    supertrend_ai.fit(underlying_df)
    underlying_df = supertrend_ai.predict(underlying_df)
    
    # Fetch options chain
    options_df = await fetch_options_chain(symbol, expiration)
    
    # Rank with enhanced ranker
    ranker = EnhancedOptionsRanker()
    ranked_df = ranker.rank_options_with_indicators(
        options_df=options_df,
        underlying_df=underlying_df,
        underlying_price=underlying_df['close'].iloc[-1],
    )
    
    # Include trend analysis in response
    return {
        "symbol": symbol,
        "expiration": expiration,
        "ranked_options": ranked_df.to_dict(orient="records"),
        "trend_analysis": ranked_df.attrs.get("trend_analysis", {}),
        "supertrend_factor": supertrend_ai.target_factor,
        "supertrend_performance": supertrend_ai.performance_index,
    }
```

---

## Phase 7: Swift App Charting Integration (Priority: HIGH)

### 7.1 Current Swift Indicators

**Location**: `client-macos/SwiftBoltML/Services/TechnicalIndicators.swift`

| Indicator | Status |
|-----------|--------|
| SMA | ✅ Implemented |
| EMA | ✅ Implemented |
| RSI | ✅ Implemented |
| VWAP | ✅ Implemented |
| Bollinger Bands | ✅ Implemented |
| **Stochastic** | ❌ Missing |
| **KDJ** | ❌ Missing |
| **MACD** | ❌ Missing |
| **ADX** | ❌ Missing |
| **SuperTrend** | ❌ Missing |

### 7.2 Add Missing Swift Indicators

```swift
// Add to TechnicalIndicators.swift

// MARK: - MACD

struct MACDResult {
    let macd: [Double?]
    let signal: [Double?]
    let histogram: [Double?]
}

static func macd(
    _ data: [Double],
    fastPeriod: Int = 12,
    slowPeriod: Int = 26,
    signalPeriod: Int = 9
) -> MACDResult {
    let fastEMA = ema(data, period: fastPeriod)
    let slowEMA = ema(data, period: slowPeriod)
    
    // MACD line = Fast EMA - Slow EMA
    var macdLine: [Double?] = []
    for i in 0..<data.count {
        if let fast = fastEMA[i], let slow = slowEMA[i] {
            macdLine.append(fast - slow)
        } else {
            macdLine.append(nil)
        }
    }
    
    // Signal line = EMA of MACD
    let macdValues = macdLine.compactMap { $0 }
    let signalEMA = ema(macdValues, period: signalPeriod)
    
    // Align signal line with MACD
    var signalLine: [Double?] = []
    var signalIdx = 0
    for macdVal in macdLine {
        if macdVal != nil {
            signalLine.append(signalIdx < signalEMA.count ? signalEMA[signalIdx] : nil)
            signalIdx += 1
        } else {
            signalLine.append(nil)
        }
    }
    
    // Histogram = MACD - Signal
    var histogram: [Double?] = []
    for i in 0..<macdLine.count {
        if let m = macdLine[i], let s = signalLine[i] {
            histogram.append(m - s)
        } else {
            histogram.append(nil)
        }
    }
    
    return MACDResult(macd: macdLine, signal: signalLine, histogram: histogram)
}

// MARK: - Stochastic Oscillator

struct StochasticResult {
    let k: [Double?]
    let d: [Double?]
}

static func stochastic(
    bars: [OHLCBar],
    kPeriod: Int = 14,
    dPeriod: Int = 3
) -> StochasticResult {
    var kValues: [Double?] = []
    
    for i in 0..<bars.count {
        if i < kPeriod - 1 {
            kValues.append(nil)
        } else {
            let periodBars = Array(bars[(i - kPeriod + 1)...i])
            let highestHigh = periodBars.map(\.high).max() ?? 0
            let lowestLow = periodBars.map(\.low).min() ?? 0
            let close = bars[i].close
            
            let range = highestHigh - lowestLow
            let k = range == 0 ? 50 : ((close - lowestLow) / range) * 100
            kValues.append(k)
        }
    }
    
    // D = SMA of K
    let kFiltered = kValues.compactMap { $0 }
    let dSMA = sma(kFiltered, period: dPeriod)
    
    var dValues: [Double?] = []
    var dIdx = 0
    for kVal in kValues {
        if kVal != nil {
            dValues.append(dIdx < dSMA.count ? dSMA[dIdx] : nil)
            dIdx += 1
        } else {
            dValues.append(nil)
        }
    }
    
    return StochasticResult(k: kValues, d: dValues)
}

// MARK: - KDJ Indicator

struct KDJResult {
    let k: [Double?]
    let d: [Double?]
    let j: [Double?]
}

static func kdj(
    bars: [OHLCBar],
    period: Int = 9,
    kSmooth: Int = 3,
    dSmooth: Int = 3
) -> KDJResult {
    // Calculate RSV (Raw Stochastic Value)
    var rsvValues: [Double?] = []
    
    for i in 0..<bars.count {
        if i < period - 1 {
            rsvValues.append(nil)
        } else {
            let periodBars = Array(bars[(i - period + 1)...i])
            let highestHigh = periodBars.map(\.high).max() ?? 0
            let lowestLow = periodBars.map(\.low).min() ?? 0
            let close = bars[i].close
            
            let range = highestHigh - lowestLow
            let rsv = range == 0 ? 50 : ((close - lowestLow) / range) * 100
            rsvValues.append(rsv)
        }
    }
    
    // K = SMA of RSV
    let rsvFiltered = rsvValues.compactMap { $0 }
    let kSMA = sma(rsvFiltered, period: kSmooth)
    
    var kValues: [Double?] = []
    var kIdx = 0
    for rsv in rsvValues {
        if rsv != nil {
            kValues.append(kIdx < kSMA.count ? kSMA[kIdx] : nil)
            kIdx += 1
        } else {
            kValues.append(nil)
        }
    }
    
    // D = SMA of K
    let kFiltered = kValues.compactMap { $0 }
    let dSMA = sma(kFiltered, period: dSmooth)
    
    var dValues: [Double?] = []
    var dIdx = 0
    for kVal in kValues {
        if kVal != nil {
            dValues.append(dIdx < dSMA.count ? dSMA[dIdx] : nil)
            dIdx += 1
        } else {
            dValues.append(nil)
        }
    }
    
    // J = 3*K - 2*D
    var jValues: [Double?] = []
    for i in 0..<kValues.count {
        if let k = kValues[i], let d = dValues[i] {
            jValues.append(3 * k - 2 * d)
        } else {
            jValues.append(nil)
        }
    }
    
    return KDJResult(k: kValues, d: dValues, j: jValues)
}

// MARK: - ADX (Average Directional Index)

struct ADXResult {
    let adx: [Double?]
    let plusDI: [Double?]
    let minusDI: [Double?]
}

static func adx(bars: [OHLCBar], period: Int = 14) -> ADXResult {
    guard bars.count > period else {
        return ADXResult(
            adx: Array(repeating: nil, count: bars.count),
            plusDI: Array(repeating: nil, count: bars.count),
            minusDI: Array(repeating: nil, count: bars.count)
        )
    }
    
    var plusDM: [Double] = [0]
    var minusDM: [Double] = [0]
    var tr: [Double] = [bars[0].high - bars[0].low]
    
    for i in 1..<bars.count {
        let highDiff = bars[i].high - bars[i-1].high
        let lowDiff = bars[i-1].low - bars[i].low
        
        plusDM.append(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
        minusDM.append(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)
        
        let trueRange = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i-1].close),
            abs(bars[i].low - bars[i-1].close)
        )
        tr.append(trueRange)
    }
    
    // Smooth with EMA
    let plusDIEMA = ema(plusDM, period: period)
    let minusDIEMA = ema(minusDM, period: period)
    let trEMA = ema(tr, period: period)
    
    var plusDI: [Double?] = []
    var minusDI: [Double?] = []
    var dx: [Double] = []
    
    for i in 0..<bars.count {
        if let pdi = plusDIEMA[i], let mdi = minusDIEMA[i], let atr = trEMA[i], atr > 0 {
            let pdiVal = (pdi / atr) * 100
            let mdiVal = (mdi / atr) * 100
            plusDI.append(pdiVal)
            minusDI.append(mdiVal)
            
            let sum = pdiVal + mdiVal
            if sum > 0 {
                dx.append(abs(pdiVal - mdiVal) / sum * 100)
            }
        } else {
            plusDI.append(nil)
            minusDI.append(nil)
        }
    }
    
    // ADX = SMA of DX
    let adxSMA = sma(dx, period: period)
    var adxValues: [Double?] = Array(repeating: nil, count: bars.count - dx.count)
    adxValues.append(contentsOf: adxSMA)
    
    return ADXResult(adx: adxValues, plusDI: plusDI, minusDI: minusDI)
}

// MARK: - SuperTrend (Simplified)

struct SuperTrendResult {
    let supertrend: [Double?]
    let trend: [Int]  // 1 = bullish, -1 = bearish
}

static func superTrend(
    bars: [OHLCBar],
    period: Int = 10,
    multiplier: Double = 3.0
) -> SuperTrendResult {
    // Calculate ATR
    var tr: [Double] = []
    for i in 0..<bars.count {
        if i == 0 {
            tr.append(bars[i].high - bars[i].low)
        } else {
            let trueRange = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i-1].close),
                abs(bars[i].low - bars[i-1].close)
            )
            tr.append(trueRange)
        }
    }
    
    let atrEMA = ema(tr, period: period)
    
    var supertrend: [Double?] = []
    var trend: [Int] = []
    var finalUpper: [Double] = []
    var finalLower: [Double] = []
    
    for i in 0..<bars.count {
        let hl2 = (bars[i].high + bars[i].low) / 2
        
        guard let atr = atrEMA[i] else {
            supertrend.append(nil)
            trend.append(0)
            finalUpper.append(hl2)
            finalLower.append(hl2)
            continue
        }
        
        let upperBand = hl2 + multiplier * atr
        let lowerBand = hl2 - multiplier * atr
        
        if i == 0 {
            finalUpper.append(upperBand)
            finalLower.append(lowerBand)
            trend.append(1)
            supertrend.append(lowerBand)
        } else {
            // Adjust bands
            let prevClose = bars[i-1].close
            let newUpper = upperBand < finalUpper[i-1] || prevClose > finalUpper[i-1] 
                ? upperBand : finalUpper[i-1]
            let newLower = lowerBand > finalLower[i-1] || prevClose < finalLower[i-1] 
                ? lowerBand : finalLower[i-1]
            
            finalUpper.append(newUpper)
            finalLower.append(newLower)
            
            // Determine trend
            let close = bars[i].close
            if close > newUpper {
                trend.append(1)
            } else if close < newLower {
                trend.append(-1)
            } else {
                trend.append(trend[i-1])
            }
            
            supertrend.append(trend[i] == 1 ? newLower : newUpper)
        }
    }
    
    return SuperTrendResult(supertrend: supertrend, trend: trend)
}
```

### 7.3 Update IndicatorConfig

```swift
// Update IndicatorConfig in TechnicalIndicators.swift

struct IndicatorConfig {
    // Existing
    var showSMA20: Bool = false
    var showSMA50: Bool = false
    var showSMA200: Bool = false
    var showEMA9: Bool = false
    var showEMA21: Bool = false
    var showRSI: Bool = false
    var showVolume: Bool = true
    var showBollingerBands: Bool = false
    
    // NEW: Phase 7 additions
    var showMACD: Bool = false
    var showStochastic: Bool = false
    var showKDJ: Bool = false
    var showADX: Bool = false
    var showSuperTrend: Bool = false
}
```

### 7.4 Update ChartResponse Model

```swift
// Update ChartResponse.swift to include indicator data from backend

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
    
    // NEW: Pre-computed indicators from backend
    let indicators: IndicatorData?
}

struct IndicatorData: Codable, Equatable {
    // SuperTrend AI results
    let supertrendFactor: Double?
    let supertrendPerformance: Double?
    let supertrendSignal: Int?  // 1 = bullish, -1 = bearish
    
    // Trend analysis
    let trendLabel: String?  // bullish, neutral, bearish
    let trendConfidence: Double?
    
    // Key indicator values (latest)
    let rsi: Double?
    let adx: Double?
    let macdHistogram: Double?
    let kdjJ: Double?
}
```

### 7.5 Update Chart Views

```swift
// Add to AdvancedChartView.swift or create new overlay views

struct SuperTrendOverlay: View {
    let bars: [OHLCBar]
    let result: TechnicalIndicators.SuperTrendResult
    
    var body: some View {
        // Draw SuperTrend line with color based on trend
        Path { path in
            for (index, bar) in bars.enumerated() {
                guard let st = result.supertrend[index] else { continue }
                let point = CGPoint(x: xPosition(for: index), y: yPosition(for: st))
                
                if index == 0 || result.supertrend[index - 1] == nil {
                    path.move(to: point)
                } else {
                    path.addLine(to: point)
                }
            }
        }
        .stroke(
            result.trend.last == 1 ? Color.green : Color.red,
            lineWidth: 2
        )
    }
}

struct KDJIndicatorView: View {
    let bars: [OHLCBar]
    let result: TechnicalIndicators.KDJResult
    
    var body: some View {
        VStack {
            // K line (blue)
            IndicatorLine(values: result.k, color: .blue, label: "K")
            // D line (orange)
            IndicatorLine(values: result.d, color: .orange, label: "D")
            // J line (purple) - most sensitive
            IndicatorLine(values: result.j, color: .purple, label: "J")
            
            // Overbought/Oversold zones
            Rectangle()
                .fill(Color.red.opacity(0.1))
                .frame(height: 20)  // 80-100 zone
            Rectangle()
                .fill(Color.green.opacity(0.1))
                .frame(height: 20)  // 0-20 zone
        }
    }
}
```

---

## Phase 8: End-to-End Testing & Validation (Priority: CRITICAL)

### 8.1 Test Matrix

| Test Case | Components | Expected Outcome |
|-----------|------------|------------------|
| Indicator Accuracy | Python vs Swift calculations | < 0.01% variance |
| SuperTrend Backtest | 1 year SPY data | Performance index > 0.5 |
| Options Ranking | Enhanced vs Basic ranker | +10% better picks |
| Swift Chart Render | All new indicators | No crashes, correct display |
| API Response | Backend → Swift | All indicator data present |

### 8.2 Backtest Framework

```python
# New file: ml/src/testing/backtest_framework.py

class IndicatorBacktester:
    """
    Backtest technical indicators and ML strategies.
    """
    
    def backtest_supertrend(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000,
    ) -> Dict[str, Any]:
        """
        Backtest SuperTrend AI strategy.
        """
        supertrend_ai = SuperTrendAI()
        supertrend_ai.fit(df)
        df = supertrend_ai.predict(df)
        
        # Simulate trades
        capital = initial_capital
        position = 0
        trades = []
        
        for i in range(1, len(df)):
            signal = df['supertrend_signal'].iloc[i]
            price = df['close'].iloc[i]
            
            if signal == 1 and position == 0:  # Buy
                position = capital / price
                capital = 0
                trades.append({"type": "buy", "price": price, "date": df['ts'].iloc[i]})
            
            elif signal == -1 and position > 0:  # Sell
                capital = position * price
                position = 0
                trades.append({"type": "sell", "price": price, "date": df['ts'].iloc[i]})
        
        # Final value
        final_value = capital + position * df['close'].iloc[-1]
        
        return {
            "initial_capital": initial_capital,
            "final_value": final_value,
            "return_pct": (final_value - initial_capital) / initial_capital * 100,
            "num_trades": len(trades),
            "trades": trades,
            "supertrend_factor": supertrend_ai.target_factor,
            "performance_index": supertrend_ai.performance_index,
        }
    
    def backtest_options_ranking(
        self,
        historical_options: List[Dict],
        historical_prices: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Backtest options ranking accuracy.
        """
        ranker = EnhancedOptionsRanker()
        
        correct_predictions = 0
        total_predictions = 0
        
        for option_snapshot in historical_options:
            # Rank options at that point in time
            ranked = ranker.rank_options_with_indicators(
                options_df=pd.DataFrame(option_snapshot["options"]),
                underlying_df=historical_prices.loc[:option_snapshot["date"]],
                underlying_price=option_snapshot["underlying_price"],
            )
            
            # Check if top-ranked options performed well
            top_options = ranked.head(5)
            for _, opt in top_options.iterrows():
                actual_return = option_snapshot["actual_returns"].get(opt["contract_id"], 0)
                if actual_return > 0:
                    correct_predictions += 1
                total_predictions += 1
        
        return {
            "accuracy": correct_predictions / total_predictions if total_predictions > 0 else 0,
            "total_predictions": total_predictions,
            "correct_predictions": correct_predictions,
        }
```

---

## Phase 9: Data Pipeline Integration (Priority: HIGH)

### 9.1 Enhanced Data Flow (Post-Implementation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (Scheduled)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  backfill-ohlc.yml (6hr)              │    options-nightly.yml (daily)      │
│  ↓                                    │    ↓                                 │
│  Polygon API → ohlc_bars              │    Tradier API → options_snapshots  │
│  (d1, h1, m15, w1 timeframes)         │    ↓                                 │
│                                       │    EnhancedOptionsRanker             │
│                                       │    (uses ohlc_bars + indicators)     │
│                                       │    ↓                                 │
│                                       │    options_ranks (with trend_analysis)│
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ML Processing (On Cached Data)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Read ohlc_bars from Supabase (NO API CALL)                      │    │
│  │  2. Compute technical indicators (Python)                            │    │
│  │  3. Fit SuperTrend AI                                                │    │
│  │  4. Generate multi-timeframe features                                │    │
│  │  5. Store ml_features in Supabase (optional, for caching)            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Supabase Database                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐   │
│  │  ohlc_bars   │  │ ml_forecasts │  │ options_ranks  │  │ ml_features  │   │
│  │  (multi-TF)  │  │ (predictions)│  │ (enhanced)     │  │ (cached)     │   │
│  └──────────────┘  └──────────────┘  └────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Workflow Updates Required

#### Update `backfill-ohlc.yml` for Multi-Timeframe

```yaml
# .github/workflows/backfill-ohlc.yml - UPDATED

name: Automated OHLC Backfill (Multi-Timeframe)

on:
  schedule:
    - cron: "0 */6 * * *"  # Every 6 hours
  workflow_dispatch:
    inputs:
      symbol:
        description: "Symbol to backfill (optional)"
        required: false
        type: string
      timeframes:
        description: "Timeframes to backfill (comma-separated)"
        required: false
        type: string
        default: "d1,h1,m15,w1"

jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 45  # Increased for multi-timeframe

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: "ml/requirements.txt"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r ml/requirements.txt

      # Scheduled run: backfill all timeframes incrementally
      - name: Backfill all timeframes (scheduled)
        if: github.event_name == 'schedule'
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          # Backfill each timeframe incrementally
          for TF in d1 h1 m15 w1; do
            echo "📊 Backfilling timeframe: $TF"
            python src/scripts/backfill_ohlc.py --all --incremental --timeframe $TF
            sleep 5  # Rate limit between timeframes
          done

      # Manual run: specified timeframes
      - name: Backfill (manual)
        if: github.event_name == 'workflow_dispatch'
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          SYMBOL="${{ github.event.inputs.symbol }}"
          TIMEFRAMES="${{ github.event.inputs.timeframes }}"
          
          IFS=',' read -ra TF_ARRAY <<< "$TIMEFRAMES"
          for TF in "${TF_ARRAY[@]}"; do
            echo "📊 Backfilling timeframe: $TF"
            if [ -n "$SYMBOL" ]; then
              python src/scripts/backfill_ohlc.py --symbol "$SYMBOL" --timeframe "$TF"
            else
              python src/scripts/backfill_ohlc.py --all --incremental --timeframe "$TF"
            fi
            sleep 5
          done
```

#### Update `options-nightly.yml` to Use Enhanced Ranker

```yaml
# .github/workflows/options-nightly.yml - UPDATED

# ... (existing setup steps) ...

      - name: Options Ranking with Enhanced ML
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          # Use enhanced ranker that reads from ohlc_bars (no extra API calls)
          python src/scripts/backfill_options.py --all --use-enhanced-ranker
```

### 9.3 Database Schema Updates

```sql
-- Add ml_features table for caching computed indicators (optional)
CREATE TABLE IF NOT EXISTS ml_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    
    -- Cached indicator values
    rsi_14 REAL,
    macd_hist REAL,
    stoch_k REAL,
    stoch_d REAL,
    kdj_j REAL,
    adx REAL,
    plus_di REAL,
    minus_di REAL,
    supertrend REAL,
    supertrend_trend INTEGER,  -- 1 = bullish, -1 = bearish
    
    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol_id, timeframe, ts)
);

-- Add trend_analysis to options_ranks
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS trend_analysis JSONB;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS supertrend_factor REAL;
ALTER TABLE options_ranks ADD COLUMN IF NOT EXISTS supertrend_performance REAL;
```

### 9.4 Data Fetching Strategy

| Scenario | Data Source | API Calls? |
|----------|-------------|------------|
| Compute indicators for ranking | `ohlc_bars` table | ❌ No |
| Generate ML forecast | `ohlc_bars` table | ❌ No |
| Multi-timeframe features | `ohlc_bars` table (multi-TF) | ❌ No |
| Options chain data | `options_chain_snapshots` | ❌ No |
| Backfill new OHLC data | Polygon API | ✅ Yes (scheduled) |
| Backfill new options | Tradier API | ✅ Yes (scheduled) |

**Key Insight**: All ML processing reads from cached Supabase data. API calls only happen during scheduled GitHub Actions backfills.

### 9.5 Updated Python Data Access

```python
# ml/src/data/supabase_db.py - ADD these methods

def fetch_ohlc_bars_multi_timeframe(
    self,
    symbol: str,
    timeframes: list[str] = ['m15', 'h1', 'd1', 'w1'],
    limit: int | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLC bars for multiple timeframes from cached database.
    
    NO API CALLS - reads from ohlc_bars table populated by GitHub Actions.
    
    Returns:
        Dict mapping timeframe to DataFrame: {'d1': df_d1, 'h1': df_h1, ...}
    """
    result = {}
    for tf in timeframes:
        df = self.fetch_ohlc_bars(symbol, timeframe=tf, limit=limit)
        if not df.empty:
            result[tf] = df
    return result


def fetch_cached_features(
    self,
    symbol: str,
    timeframe: str = 'd1',
    limit: int | None = None,
) -> pd.DataFrame | None:
    """
    Fetch pre-computed ML features from cache (if available).
    
    Returns None if features not cached, caller should compute fresh.
    """
    try:
        symbol_id = self.get_symbol_id(symbol)
        query = (
            self.client.table("ml_features")
            .select("*")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .order("ts", desc=True)
        )
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        if response.data:
            return pd.DataFrame(response.data)
        return None
    except Exception:
        return None  # Cache miss, compute fresh


def cache_features(
    self,
    symbol_id: str,
    timeframe: str,
    features_df: pd.DataFrame,
) -> None:
    """
    Cache computed ML features to avoid recomputation.
    """
    for _, row in features_df.iterrows():
        self.client.table("ml_features").upsert({
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "ts": row["ts"].isoformat(),
            "rsi_14": row.get("rsi_14"),
            "macd_hist": row.get("macd_hist"),
            "stoch_k": row.get("stoch_k"),
            "stoch_d": row.get("stoch_d"),
            "kdj_j": row.get("kdj_j"),
            "adx": row.get("adx"),
            "plus_di": row.get("plus_di"),
            "minus_di": row.get("minus_di"),
            "supertrend": row.get("supertrend"),
            "supertrend_trend": row.get("supertrend_trend"),
        }, on_conflict="symbol_id,timeframe,ts").execute()
```

---

## Phase 10: Critical ML Components from examplescripts- (Priority: CRITICAL)

**Source**: `https://github.com/PapaPablano/examplescripts-`

These components were identified as critical for the successful dashboard implementation and **must not be lost**:

### 10.1 Walk-Forward Cross-Validation (CRITICAL FIX #2)

**Why Critical**: Random K-fold CV causes **250% performance overestimation** in time series. Walk-forward CV prevents data leakage and gives realistic accuracy estimates.

```python
# New file: ml/src/evaluation/walk_forward_cv.py
# Ported from: examplescripts-/kaggle_inspired_dashboard/evaluation/walk_forward_cv.py

from typing import List, Tuple, Dict
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import logging

logger = logging.getLogger(__name__)


class WalkForwardCV:
    """
    Walk-forward cross-validation for time series.
    NEVER shuffles data - maintains temporal order.
    
    Structure:
      - Train: Jan-Aug, Validate: Sep
      - Train: Jan-Sep, Validate: Oct
      - Train: Jan-Oct, Validate: Nov
    """

    def __init__(
        self,
        n_splits: int = 5,
        test_size: int = 28,  # 28 days as per M5 Kaggle competition
        gap: int = 0,  # Gap between train/test to prevent leakage
    ):
        self.n_splits = n_splits
        self.test_size = test_size
        self.gap = gap
        logger.info(f"Walk-Forward CV: {n_splits} splits, {test_size} days test, {gap} days gap")

    def split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Generate train/test indices for walk-forward validation."""
        n_samples = len(X)
        splits = []
        initial_train_size = n_samples - (self.n_splits * self.test_size)

        if initial_train_size < self.test_size:
            raise ValueError(f"Not enough data! Need at least {self.n_splits * self.test_size * 2} samples")

        for i in range(self.n_splits):
            train_end = initial_train_size + (i * self.test_size) - self.gap
            train_idx = np.arange(0, train_end)
            
            test_start = train_end + self.gap
            test_end = test_start + self.test_size
            test_idx = np.arange(test_start, min(test_end, n_samples))
            
            splits.append((train_idx, test_idx))
        
        return splits

    def validate(self, model, X: pd.DataFrame, y: pd.Series, verbose: bool = True) -> Dict:
        """Perform walk-forward validation with proper time series metrics."""
        results = {
            "mae": [], "rmse": [], "r2": [], "mape": [], "directional_accuracy": [],
        }
        
        splits = self.split(X)
        
        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)
            mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
            
            # Directional accuracy (critical for trading)
            if len(y_test) > 1:
                direction_actual = np.diff(y_test) > 0
                direction_pred = np.diff(y_pred) > 0
                dir_accuracy = np.mean(direction_actual == direction_pred)
            else:
                dir_accuracy = np.nan
            
            results["mae"].append(mae)
            results["rmse"].append(rmse)
            results["r2"].append(r2)
            results["mape"].append(mape)
            results["directional_accuracy"].append(dir_accuracy)
        
        return {
            "mae_mean": np.mean(results["mae"]),
            "mae_std": np.std(results["mae"]),
            "rmse_mean": np.mean(results["rmse"]),
            "rmse_std": np.std(results["rmse"]),
            "r2_mean": np.mean(results["r2"]),
            "r2_std": np.std(results["r2"]),
            "mape_mean": np.mean(results["mape"]),
            "directional_accuracy_mean": np.nanmean(results["directional_accuracy"]),
            "fold_results": results,
        }


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate directional accuracy (trend prediction)."""
    if len(y_true) < 2:
        return np.nan
    direction_true = np.diff(y_true) > 0
    direction_pred = np.diff(y_pred) > 0
    return np.mean(direction_true == direction_pred)
```

### 10.2 LightGBM with linear_tree=True (CRITICAL FIX #1)

**Why Critical**: Without `linear_tree=True`, LightGBM **cannot extrapolate** beyond training data range. This caused **122x worse** extrapolation accuracy.

```python
# New file: ml/src/models/lightgbm_forecaster.py
# Config from: examplescripts-/config/model_config.yaml

import lightgbm as lgb
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


class LightGBMForecaster:
    """
    LightGBM model with linear_tree=True for time series extrapolation.
    
    CRITICAL: linear_tree=True enables extrapolation beyond training range.
    Without this, predictions are bounded by training data min/max.
    """
    
    DEFAULT_PARAMS = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'linear_tree': True,  # CRITICAL for extrapolation
        'num_leaves': 31,
        'max_depth': 10,
        'learning_rate': 0.05,
        'min_child_samples': 20,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'feature_fraction': 0.9,
        'n_estimators': 100,
        'verbose': -1,
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.params = self.DEFAULT_PARAMS.copy()
        self.model = None
        self.feature_names = None
        
        if config_path:
            self._load_config(config_path)
        
        logger.info(f"LightGBM initialized with linear_tree={self.params.get('linear_tree')}")
    
    def _load_config(self, config_path: str):
        """Load parameters from YAML config."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        if 'lightgbm' in config:
            self.params.update(config['lightgbm'])
    
    def train(self, X: pd.DataFrame, y: pd.Series, verbose: bool = True):
        """Train the model."""
        self.feature_names = list(X.columns)
        
        train_data = lgb.Dataset(X, label=y)
        
        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=self.params.get('n_estimators', 100),
            valid_sets=[train_data] if verbose else None,
            callbacks=[lgb.log_evaluation(50)] if verbose else None,
        )
        
        logger.info(f"Model trained on {len(X)} samples with {len(self.feature_names)} features")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions."""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        return self.model.predict(X)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if self.model is None:
            return {}
        importance = self.model.feature_importance(importance_type='gain')
        return dict(zip(self.feature_names, importance))
```

### 10.3 Enhanced SuperTrend AI with K-Means Clustering

**Why Critical**: The SuperTrend AI uses K-means clustering to find the **optimal ATR factor** dynamically. This was key to the successful dashboard.

```python
# New file: ml/src/strategies/supertrend_ai.py
# Ported from: examplescripts-/main_production_system/core/supertrend_ai.py

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from typing import Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class SuperTrendAI:
    """
    SuperTrend AI with K-means Clustering for adaptive factor selection.
    
    Key Features:
    - Tests multiple ATR factors (1.0 to 5.0)
    - Clusters factors by performance using K-means
    - Selects optimal factor from 'Best' cluster
    - Generates performance-adaptive moving average (Perf AMA)
    - Outputs signal strength score (0-10)
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        atr_length: int = 10,
        min_mult: float = 1.0,
        max_mult: float = 5.0,
        step: float = 0.5,
        perf_alpha: int = 10,
        from_cluster: str = 'Best',  # 'Best', 'Average', or 'Worst'
        max_iter: int = 1000,
        max_data: int = 10000,
    ):
        self.df = df.copy()
        self.atr_length = atr_length
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.step = step
        self.perf_alpha = perf_alpha
        self.from_cluster = from_cluster
        self.max_iter = max_iter
        self.max_data = max_data
        
        if min_mult > max_mult:
            raise ValueError('Minimum factor is greater than maximum factor')
        
        self.factors = np.arange(min_mult, max_mult + step, step)
    
    def calculate_atr(self) -> pd.Series:
        """Calculate Average True Range using EMA."""
        high, low, close = self.df['high'], self.df['low'], self.df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=self.atr_length, adjust=False).mean()
    
    def calculate_supertrend(self, atr: pd.Series, factor: float) -> Tuple[pd.Series, pd.Series]:
        """Calculate SuperTrend for a given factor."""
        high, low, close = self.df['high'], self.df['low'], self.df['close']
        hl2 = (high + low) / 2
        
        upper_band = hl2 + (atr * factor)
        lower_band = hl2 - (atr * factor)
        
        final_upper = pd.Series(0.0, index=self.df.index)
        final_lower = pd.Series(0.0, index=self.df.index)
        supertrend = pd.Series(0.0, index=self.df.index)
        trend = pd.Series(0, index=self.df.index)
        
        for i in range(1, len(self.df)):
            # Final upper band
            if upper_band.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]
            
            # Final lower band
            if lower_band.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]
            
            # Trend determination
            if close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1  # Bullish
            elif close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = 0  # Bearish
            else:
                trend.iloc[i] = trend.iloc[i-1]
            
            # SuperTrend output
            supertrend.iloc[i] = final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]
        
        return supertrend, trend
    
    def calculate_performance(self, supertrend: pd.Series, trend: pd.Series) -> float:
        """Calculate performance metric for a SuperTrend configuration."""
        close = self.df['close']
        perf = pd.Series(0.0, index=self.df.index)
        alpha = 2 / (self.perf_alpha + 1)
        
        for i in range(1, len(self.df)):
            diff = np.sign(close.iloc[i-1] - supertrend.iloc[i-1])
            price_change = close.iloc[i] - close.iloc[i-1]
            perf.iloc[i] = perf.iloc[i-1] + alpha * (price_change * diff - perf.iloc[i-1])
        
        return perf.iloc[-1]
    
    def run_kmeans_clustering(self, performances: list, factors: list) -> Tuple[float, Dict]:
        """Perform K-means clustering to find optimal factor."""
        data_limit = min(len(performances), self.max_data)
        perf_array = np.array(performances[-data_limit:]).reshape(-1, 1)
        factor_array = np.array(factors[-data_limit:])
        
        # Initialize centroids using quartiles
        q25, q50, q75 = np.percentile(perf_array, [25, 50, 75])
        initial_centroids = np.array([[q25], [q50], [q75]])
        
        kmeans = KMeans(n_clusters=3, init=initial_centroids, max_iter=self.max_iter, n_init=1, random_state=42)
        labels = kmeans.fit_predict(perf_array)
        
        # Group factors by cluster
        clusters = {0: [], 1: [], 2: []}
        perf_clusters = {0: [], 1: [], 2: []}
        
        for i, label in enumerate(labels):
            clusters[label].append(factor_array[i])
            perf_clusters[label].append(perf_array[i][0])
        
        # Sort clusters by average performance
        cluster_means = {k: np.mean(v) if v else 0 for k, v in perf_clusters.items()}
        sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1])
        
        cluster_mapping = {
            sorted_clusters[0][0]: 'Worst',
            sorted_clusters[1][0]: 'Average',
            sorted_clusters[2][0]: 'Best'
        }
        
        # Get target cluster factors
        target_label = [k for k, v in cluster_mapping.items() if v == self.from_cluster][0]
        target_factors = clusters[target_label]
        
        return np.mean(target_factors) if target_factors else self.min_mult, cluster_mapping
    
    def calculate(self) -> Tuple[pd.DataFrame, Dict]:
        """Main calculation - returns DataFrame with SuperTrend and info dict."""
        atr = self.calculate_atr()
        
        # Test all factors
        all_performances = []
        for factor in self.factors:
            st, trend = self.calculate_supertrend(atr, factor)
            perf = self.calculate_performance(st, trend)
            all_performances.append(perf)
        
        # Find optimal factor via clustering
        target_factor, cluster_mapping = self.run_kmeans_clustering(
            all_performances, self.factors.tolist()
        )
        
        # Calculate final SuperTrend with optimal factor
        final_st, final_trend = self.calculate_supertrend(atr, target_factor)
        
        # Performance index (0-1 normalized)
        close = self.df['close']
        den = close.diff().abs().ewm(span=self.perf_alpha, adjust=False).mean()
        perf_idx = max(self.calculate_performance(final_st, final_trend), 0) / (den.iloc[-1] + 1e-10)
        perf_idx = min(max(perf_idx, 0), 1)
        
        # Performance-adaptive MA
        perf_ama = pd.Series(final_st.iloc[0], index=self.df.index)
        for i in range(1, len(self.df)):
            perf_ama.iloc[i] = perf_ama.iloc[i-1] + perf_idx * (final_st.iloc[i] - perf_ama.iloc[i-1])
        
        # Store results
        self.df['supertrend'] = final_st
        self.df['trend'] = final_trend
        self.df['perf_ama'] = perf_ama
        self.df['target_factor'] = target_factor
        self.df['atr'] = atr
        
        # Generate signals
        self.df['signal'] = 0
        for i in range(1, len(self.df)):
            if self.df['trend'].iloc[i-1] == 0 and self.df['trend'].iloc[i] == 1:
                self.df.loc[self.df.index[i], 'signal'] = 1  # Buy
            elif self.df['trend'].iloc[i-1] == 1 and self.df['trend'].iloc[i] == 0:
                self.df.loc[self.df.index[i], 'signal'] = -1  # Sell
        
        return self.df, {
            'target_factor': target_factor,
            'cluster_mapping': cluster_mapping,
            'performance_index': perf_idx,
            'signal_strength': int(perf_idx * 10),  # 0-10 score
        }
```

### 10.4 Direct Multi-Horizon Forecasting (CRITICAL FIX #5)

**Why Critical**: Recursive forecasting causes **error accumulation** across horizons. Direct forecasting trains separate models per horizon, achieving **3x better accuracy**.

```python
# New file: ml/src/models/direct_forecaster.py
# Concept from: examplescripts-/kaggle_inspired_dashboard/models/direct_forecaster.py

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor
import logging

logger = logging.getLogger(__name__)


class DirectForecaster:
    """
    Direct multi-horizon forecasting - separate model per horizon.
    
    Why Direct > Recursive:
    - Recursive: predict t+1, use prediction to predict t+2, etc.
      → Errors compound: 200%+ error growth
    - Direct: train separate model for each horizon
      → No error accumulation: ~80% error growth
    
    M5 Kaggle 1st place solution used this approach.
    """
    
    def __init__(
        self,
        horizons: List[int] = [1, 7, 14, 28],  # Days ahead
        base_model_class=None,  # Default: LightGBM
        model_params: Optional[Dict] = None,
    ):
        self.horizons = horizons
        self.models = {}
        self.base_model_class = base_model_class
        self.model_params = model_params or {'linear_tree': True, 'num_leaves': 31}
    
    def _create_model(self):
        """Create a new model instance."""
        if self.base_model_class:
            return self.base_model_class(**self.model_params)
        
        # Default: LightGBM
        import lightgbm as lgb
        return lgb.LGBMRegressor(**self.model_params)
    
    def _train_single_horizon(self, X: pd.DataFrame, y: pd.Series, horizon: int):
        """Train model for a single horizon."""
        # Shift target by horizon
        y_shifted = y.shift(-horizon).dropna()
        X_aligned = X.iloc[:len(y_shifted)]
        
        model = self._create_model()
        model.fit(X_aligned, y_shifted)
        
        return horizon, model
    
    def train(self, X: pd.DataFrame, y: pd.Series, n_jobs: int = -1):
        """
        Train separate model for each horizon.
        
        Args:
            X: Feature matrix
            y: Target (typically close price or returns)
            n_jobs: Parallel jobs (-1 = all cores)
        """
        logger.info(f"Training {len(self.horizons)} horizon-specific models...")
        
        if n_jobs == 1:
            # Sequential training
            for horizon in self.horizons:
                _, model = self._train_single_horizon(X, y, horizon)
                self.models[horizon] = model
        else:
            # Parallel training (8x speedup on multi-core)
            with ProcessPoolExecutor(max_workers=n_jobs if n_jobs > 0 else None) as executor:
                futures = [
                    executor.submit(self._train_single_horizon, X, y, h)
                    for h in self.horizons
                ]
                for future in futures:
                    horizon, model = future.result()
                    self.models[horizon] = model
        
        logger.info(f"Trained models for horizons: {list(self.models.keys())}")
    
    def predict(self, X: pd.DataFrame) -> Dict[int, np.ndarray]:
        """
        Generate predictions for all horizons.
        
        Returns:
            Dict mapping horizon to predictions: {1: [...], 7: [...], ...}
        """
        predictions = {}
        for horizon, model in self.models.items():
            predictions[horizon] = model.predict(X)
        return predictions
    
    def predict_dataframe(self, X: pd.DataFrame, dates: Optional[pd.DatetimeIndex] = None) -> pd.DataFrame:
        """Return predictions as DataFrame with horizon columns."""
        predictions = self.predict(X)
        
        df = pd.DataFrame(predictions)
        df.columns = [f't+{h}' for h in df.columns]
        
        if dates is not None:
            df.index = dates
        
        return df
```

### 10.5 Data Drift Detection (CRITICAL FIX #3)

**Why Critical**: Model performance degrades when data distribution shifts. Automated drift detection triggers retraining when needed.

```python
# New file: ml/src/monitoring/drift_detector.py
# Concept from: examplescripts-/kaggle_inspired_dashboard/monitoring/drift_detector.py

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Statistical drift detection using Kolmogorov-Smirnov test.
    
    Detects when current data distribution differs significantly
    from training data, indicating model retraining is needed.
    """
    
    def __init__(
        self,
        reference_data: pd.DataFrame,
        significance_level: float = 0.05,
        drift_threshold: float = 0.1,  # 10% of features drifted = dataset drift
    ):
        self.reference_data = reference_data
        self.significance_level = significance_level
        self.drift_threshold = drift_threshold
        self.reference_stats = self._compute_reference_stats()
    
    def _compute_reference_stats(self) -> Dict:
        """Compute reference statistics for each feature."""
        stats_dict = {}
        for col in self.reference_data.select_dtypes(include=[np.number]).columns:
            stats_dict[col] = {
                'mean': self.reference_data[col].mean(),
                'std': self.reference_data[col].std(),
                'min': self.reference_data[col].min(),
                'max': self.reference_data[col].max(),
                'values': self.reference_data[col].dropna().values,
            }
        return stats_dict
    
    def detect_feature_drift(self, current_data: pd.DataFrame, feature: str) -> Dict:
        """Detect drift for a single feature using KS test."""
        if feature not in self.reference_stats:
            return {'drift': False, 'reason': 'Feature not in reference'}
        
        ref_values = self.reference_stats[feature]['values']
        curr_values = current_data[feature].dropna().values
        
        if len(curr_values) < 10:
            return {'drift': False, 'reason': 'Insufficient data'}
        
        # Kolmogorov-Smirnov test
        ks_stat, p_value = stats.ks_2samp(ref_values, curr_values)
        
        drift_detected = p_value < self.significance_level
        
        return {
            'drift': drift_detected,
            'ks_statistic': ks_stat,
            'p_value': p_value,
            'ref_mean': self.reference_stats[feature]['mean'],
            'curr_mean': current_data[feature].mean(),
            'mean_shift': abs(current_data[feature].mean() - self.reference_stats[feature]['mean']),
        }
    
    def detect_data_drift(self, current_data: pd.DataFrame) -> Dict:
        """Detect drift across all features."""
        feature_results = {}
        drifted_features = []
        
        numeric_cols = current_data.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if col in self.reference_stats:
                result = self.detect_feature_drift(current_data, col)
                feature_results[col] = result
                if result['drift']:
                    drifted_features.append(col)
        
        n_features = len(feature_results)
        n_drifted = len(drifted_features)
        drift_ratio = n_drifted / n_features if n_features > 0 else 0
        
        dataset_drift = drift_ratio >= self.drift_threshold
        
        return {
            'dataset_drift': dataset_drift,
            'drift_ratio': drift_ratio,
            'n_features': n_features,
            'n_drifted_features': n_drifted,
            'drifted_features': drifted_features,
            'feature_results': feature_results,
            'timestamp': datetime.now().isoformat(),
            'recommendation': 'RETRAIN' if dataset_drift else 'OK',
        }
```

### 10.6 Model Configuration (YAML-based)

```yaml
# New file: ml/config/model_config.yaml
# From: examplescripts-/config/model_config.yaml

lightgbm:
  # CRITICAL: linear_tree=True enables extrapolation for time series
  linear_tree: true
  objective: 'regression'
  metric: 'rmse'
  boosting_type: 'gbdt'
  num_leaves: 31
  max_depth: 10
  learning_rate: 0.05
  min_child_samples: 20
  subsample: 0.8
  colsample_bytree: 0.8
  feature_fraction: 0.9
  n_estimators: 100
  verbose: -1

xgboost:
  objective: 'reg:squarederror'
  max_depth: 8
  learning_rate: 0.1
  n_estimators: 100
  subsample: 0.8
  colsample_bytree: 0.8

ensemble:
  weights:
    lightgbm: 0.5
    xgboost: 0.3
    random_forest: 0.2

walk_forward_cv:
  n_splits: 5
  test_size: 28  # M5 Kaggle standard
  gap: 0

direct_forecasting:
  horizons: [1, 7, 14, 28]
  parallel_training: true
```

### 10.7 Performance Comparison (From examplescripts- Testing)

| Metric | Before Fixes | After Fixes | Improvement |
|--------|--------------|-------------|-------------|
| Extrapolation MAPE | >50% | 0.41% | **122x better** |
| CV Overestimation | 250% | 0% | **Eliminated** |
| Multi-horizon Accuracy | ~12-15% | 4.45% | **3x better** |
| Training Speed | 1x | 8x | **8x faster** |
| Error Accumulation | 200%+ | 80.8% | **2.5x reduction** |

---

## Updated Implementation Priority

| Phase | Description | Effort | Impact | Priority |
|-------|-------------|--------|--------|----------|
| **10.1** | **Walk-Forward CV** | **1 day** | **CRITICAL** | **🔴 P0** |
| **10.2** | **LightGBM linear_tree** | **0.5 days** | **CRITICAL** | **🔴 P0** |
| **10.3** | **SuperTrend AI (K-means)** | **2 days** | **CRITICAL** | **🔴 P0** |
| **10.4** | **Direct Multi-Horizon Forecasting** | **1 day** | **CRITICAL** | **🔴 P0** |
| **10.5** | **Drift Detection** | **1 day** | **High** | **🟡 P1** |
| 1.1 | Add Stochastic, KDJ, ADX (Python) | 2 days | High | 🔴 P0 |
| 1.2 | Add OBV, MFI, VROC (Python) | 1 day | Medium | 🔴 P0 |
| 1.3 | Add Keltner Channel (Python) | 0.5 days | Low | 🟡 P1 |
| 2.1 | Port SuperTrend AI (Python) | 3 days | Very High | 🔴 P0 |
| 3.1 | Multi-Indicator Signals | 2 days | High | 🟡 P1 |
| 3.2 | Enhanced Forecaster | 2 days | High | 🟡 P1 |
| 4.1 | Multi-Timeframe Features | 3 days | Very High | 🟡 P1 |
| 5.1 | Integration | 2 days | Critical | 🔴 P0 |
| 5.2 | Testing | 3 days | Critical | 🔴 P0 |
| **6.1** | **Enhanced Options Ranker** | **2 days** | **Very High** | **🔴 P0** |
| **6.2** | **Options API Enhancement** | **1 day** | **High** | **🔴 P0** |
| **7.1** | **Swift Indicators (MACD, Stoch, KDJ)** | **2 days** | **High** | **🔴 P0** |
| **7.2** | **Swift SuperTrend** | **1 day** | **Very High** | **🔴 P0** |
| **7.3** | **Swift Chart Updates** | **2 days** | **High** | **🟡 P1** |
| **7.4** | **API Response Updates** | **1 day** | **High** | **🟡 P1** |
| **8.1** | **End-to-End Testing** | **3 days** | **Critical** | **🔴 P0** |
| **8.2** | **Backtest Framework** | **2 days** | **High** | **🟡 P1** |

**Total Estimated Effort**: ~32 days (expanded from 18)

---

## Files to Create/Modify (Updated)

### Python Backend
```
ml/src/features/
├── technical_indicators.py  # MODIFY: Add new indicators
├── multi_timeframe.py       # NEW: Multi-timeframe features

ml/src/strategies/
├── __init__.py              # NEW
├── supertrend_ai.py         # NEW: Port from TypeScript
├── multi_indicator_signals.py  # NEW: Composite signals

ml/src/models/
├── baseline_forecaster.py   # MODIFY: Use enhanced features
├── options_ranker.py        # MODIFY: Add indicator integration (Phase 6)
├── enhanced_options_ranker.py  # NEW: Full indicator-aware ranker

ml/src/testing/
├── __init__.py              # NEW
├── backtest_framework.py    # NEW: Backtesting tools
├── indicator_tests.py       # NEW: Unit tests for indicators
```

### Swift Client
```
client-macos/SwiftBoltML/Services/
├── TechnicalIndicators.swift  # MODIFY: Add MACD, Stoch, KDJ, ADX, SuperTrend

client-macos/SwiftBoltML/Models/
├── ChartResponse.swift        # MODIFY: Add IndicatorData

client-macos/SwiftBoltML/Views/
├── AdvancedChartView.swift    # MODIFY: Add indicator overlays
├── SuperTrendOverlay.swift    # NEW: SuperTrend visualization
├── KDJIndicatorView.swift     # NEW: KDJ panel
├── ADXIndicatorView.swift     # NEW: ADX panel
```

---

## Phase 11: Critical Infrastructure Gaps (User-Identified)

Based on blueprint review and best practices research, these gaps were identified:

### 🔴 HIGH PRIORITY (Block Other Work)

#### 11.1 Backtesting Framework with Walk-Forward Validation (2-3 days)

**Status**: ✅ Partially addressed in Phase 10.1 (WalkForwardCV class)

**Additional Requirements**:

```python
# New file: ml/src/testing/backtest_framework.py

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results from a single backtest run."""
    start_date: datetime
    end_date: datetime
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: float
    equity_curve: pd.Series
    trades: pd.DataFrame


class BacktestFramework:
    """
    Production-grade backtesting with walk-forward validation.
    
    Key Features:
    - Walk-forward optimization (prevents overfitting)
    - Transaction cost modeling
    - Slippage simulation
    - Position sizing rules
    - Risk metrics (Sharpe, Sortino, Max DD, Calmar)
    """
    
    def __init__(
        self,
        initial_capital: float = 100_000,
        commission_rate: float = 0.001,  # 0.1% per trade
        slippage_bps: float = 5,  # 5 basis points
        max_position_pct: float = 0.1,  # Max 10% per position
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.max_position_pct = max_position_pct
    
    def run_backtest(
        self,
        data: pd.DataFrame,
        signal_generator: Callable[[pd.DataFrame], pd.Series],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResult:
        """
        Run backtest with realistic execution simulation.
        
        Args:
            data: OHLCV DataFrame with DatetimeIndex
            signal_generator: Function that returns signals (-1, 0, 1)
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        # Filter date range
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        # Generate signals
        signals = signal_generator(data)
        
        # Initialize tracking
        capital = self.initial_capital
        position = 0
        equity_curve = []
        trades = []
        
        for i, (idx, row) in enumerate(data.iterrows()):
            signal = signals.iloc[i] if i < len(signals) else 0
            price = row['close']
            
            # Apply slippage
            if signal > 0:
                exec_price = price * (1 + self.slippage_bps / 10000)
            elif signal < 0:
                exec_price = price * (1 - self.slippage_bps / 10000)
            else:
                exec_price = price
            
            # Position sizing
            max_shares = int((capital * self.max_position_pct) / exec_price)
            
            # Execute trades
            if signal > 0 and position <= 0:  # Buy signal
                shares = max_shares
                cost = shares * exec_price * (1 + self.commission_rate)
                if cost <= capital:
                    capital -= cost
                    position = shares
                    trades.append({
                        'date': idx, 'type': 'BUY', 'price': exec_price,
                        'shares': shares, 'cost': cost
                    })
            
            elif signal < 0 and position > 0:  # Sell signal
                proceeds = position * exec_price * (1 - self.commission_rate)
                capital += proceeds
                trades.append({
                    'date': idx, 'type': 'SELL', 'price': exec_price,
                    'shares': position, 'proceeds': proceeds
                })
                position = 0
            
            # Track equity
            equity = capital + (position * price)
            equity_curve.append({'date': idx, 'equity': equity})
        
        # Calculate metrics
        equity_df = pd.DataFrame(equity_curve).set_index('date')
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        return self._calculate_metrics(equity_df, trades_df, data)
    
    def walk_forward_backtest(
        self,
        data: pd.DataFrame,
        model_trainer: Callable,
        n_splits: int = 5,
        train_pct: float = 0.7,
    ) -> List[BacktestResult]:
        """
        Walk-forward optimization backtest.
        
        For each period:
        1. Train model on in-sample data
        2. Generate signals on out-of-sample data
        3. Backtest out-of-sample period
        
        This prevents overfitting by ensuring model never sees future data.
        """
        results = []
        n = len(data)
        split_size = n // n_splits
        
        for i in range(n_splits):
            # Define windows
            train_end = int((i + 1) * split_size * train_pct)
            test_start = train_end
            test_end = min((i + 1) * split_size, n)
            
            if test_start >= test_end:
                continue
            
            train_data = data.iloc[:train_end]
            test_data = data.iloc[test_start:test_end]
            
            # Train model on in-sample
            signal_generator = model_trainer(train_data)
            
            # Backtest on out-of-sample
            result = self.run_backtest(test_data, signal_generator)
            results.append(result)
            
            logger.info(f"Fold {i+1}/{n_splits}: Return={result.total_return:.2%}, "
                       f"Sharpe={result.sharpe_ratio:.2f}")
        
        return results
    
    def _calculate_metrics(
        self,
        equity_df: pd.DataFrame,
        trades_df: pd.DataFrame,
        data: pd.DataFrame,
    ) -> BacktestResult:
        """Calculate comprehensive backtest metrics."""
        equity = equity_df['equity']
        returns = equity.pct_change().dropna()
        
        # Total return
        total_return = (equity.iloc[-1] / self.initial_capital) - 1
        
        # Sharpe ratio (annualized, assuming daily data)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # Max drawdown
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Win rate
        if len(trades_df) > 1:
            # Pair buy/sell trades
            buys = trades_df[trades_df['type'] == 'BUY']
            sells = trades_df[trades_df['type'] == 'SELL']
            n_trades = min(len(buys), len(sells))
            
            if n_trades > 0:
                profits = []
                for j in range(n_trades):
                    buy_cost = buys.iloc[j]['cost']
                    sell_proceeds = sells.iloc[j]['proceeds']
                    profits.append(sell_proceeds - buy_cost)
                
                win_rate = sum(1 for p in profits if p > 0) / len(profits)
                gross_profit = sum(p for p in profits if p > 0)
                gross_loss = abs(sum(p for p in profits if p < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            else:
                win_rate = 0
                profit_factor = 0
        else:
            win_rate = 0
            profit_factor = 0
            n_trades = 0
        
        return BacktestResult(
            start_date=data.index[0],
            end_date=data.index[-1],
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=n_trades,
            avg_trade_duration=0,  # TODO: Calculate
            equity_curve=equity,
            trades=trades_df,
        )
```

#### 11.2 Watchlist Sync (Server-Side) (1-2 days)

**Problem**: Watchlist is local-only (UserDefaults). Options nightly backfill can't know which symbols to process.

**Solution**: Sync watchlist to Supabase so GitHub Actions can read it.

```sql
-- New migration: supabase/migrations/YYYYMMDD_watchlist_sync.sql

CREATE TABLE IF NOT EXISTS user_watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    priority INTEGER DEFAULT 0,  -- Higher = process first in nightly job
    notes TEXT,
    
    UNIQUE(user_id, symbol)
);

-- Index for nightly job queries
CREATE INDEX idx_watchlist_symbols ON user_watchlists(symbol);
CREATE INDEX idx_watchlist_priority ON user_watchlists(priority DESC);

-- RLS policies
ALTER TABLE user_watchlists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own watchlist"
ON user_watchlists FOR ALL
USING (auth.uid() = user_id);

-- Function to get all unique symbols across all users (for nightly job)
CREATE OR REPLACE FUNCTION get_all_watchlist_symbols()
RETURNS TABLE(symbol TEXT, user_count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT w.symbol, COUNT(DISTINCT w.user_id) as user_count
    FROM user_watchlists w
    GROUP BY w.symbol
    ORDER BY user_count DESC, w.symbol;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

```swift
// client-macos/SwiftBoltML/Services/WatchlistSyncService.swift

import Foundation
import Supabase

actor WatchlistSyncService {
    private let supabase: SupabaseClient
    private var localWatchlist: Set<String> = []
    
    init(supabase: SupabaseClient) {
        self.supabase = supabase
    }
    
    /// Sync local watchlist to server
    func syncToServer(symbols: [String]) async throws {
        guard let userId = supabase.auth.currentUser?.id else {
            throw WatchlistError.notAuthenticated
        }
        
        // Get current server watchlist
        let serverSymbols: [WatchlistEntry] = try await supabase
            .from("user_watchlists")
            .select()
            .eq("user_id", value: userId.uuidString)
            .execute()
            .value
        
        let serverSet = Set(serverSymbols.map { $0.symbol })
        let localSet = Set(symbols)
        
        // Add new symbols
        let toAdd = localSet.subtracting(serverSet)
        for symbol in toAdd {
            try await supabase
                .from("user_watchlists")
                .insert(["user_id": userId.uuidString, "symbol": symbol])
                .execute()
        }
        
        // Remove deleted symbols
        let toRemove = serverSet.subtracting(localSet)
        for symbol in toRemove {
            try await supabase
                .from("user_watchlists")
                .delete()
                .eq("user_id", value: userId.uuidString)
                .eq("symbol", value: symbol)
                .execute()
        }
    }
    
    /// Fetch watchlist from server (for initial load)
    func fetchFromServer() async throws -> [String] {
        guard let userId = supabase.auth.currentUser?.id else {
            return []
        }
        
        let entries: [WatchlistEntry] = try await supabase
            .from("user_watchlists")
            .select()
            .eq("user_id", value: userId.uuidString)
            .order("priority", ascending: false)
            .execute()
            .value
        
        return entries.map { $0.symbol }
    }
}

struct WatchlistEntry: Codable {
    let id: UUID
    let userId: UUID
    let symbol: String
    let addedAt: Date
    let priority: Int
    
    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case symbol
        case addedAt = "added_at"
        case priority
    }
}

enum WatchlistError: Error {
    case notAuthenticated
    case syncFailed(String)
}
```

```python
# ml/src/scripts/get_watchlist_symbols.py
# Used by GitHub Actions to get symbols for nightly processing

from data.supabase_db import SupabaseDatabase

def get_nightly_symbols() -> list[str]:
    """Get all unique symbols from user watchlists for nightly processing."""
    db = SupabaseDatabase()
    
    response = db.client.rpc('get_all_watchlist_symbols').execute()
    
    if response.data:
        return [row['symbol'] for row in response.data]
    
    # Fallback to default watchlist
    return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'SPY', 'QQQ']
```

#### 11.3 SwiftUI Performance - Debounce Specification (2-3 days)

**Problem**: High-frequency updates (WebSocket, rapid user input) can cause 100% CPU spikes.

**Solution**: Implement debounce/throttle patterns with clear specifications.

```swift
// client-macos/SwiftBoltML/Utilities/Debouncer.swift

import Foundation
import Combine

/// Debounce specification for different update types
enum UpdateFrequency {
    case realtime      // No debounce (use sparingly)
    case fast          // 100ms - UI interactions
    case normal        // 250ms - Data updates
    case slow          // 500ms - Heavy computations
    case lazy          // 1000ms - Background tasks
    
    var interval: TimeInterval {
        switch self {
        case .realtime: return 0
        case .fast: return 0.1
        case .normal: return 0.25
        case .slow: return 0.5
        case .lazy: return 1.0
        }
    }
}

/// Thread-safe debouncer for high-frequency events
actor Debouncer {
    private var task: Task<Void, Never>?
    private let interval: TimeInterval
    
    init(frequency: UpdateFrequency) {
        self.interval = frequency.interval
    }
    
    func debounce(action: @escaping () async -> Void) {
        task?.cancel()
        task = Task {
            try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
            guard !Task.isCancelled else { return }
            await action()
        }
    }
}

/// Throttler - ensures minimum interval between executions
actor Throttler {
    private var lastExecution: Date = .distantPast
    private let interval: TimeInterval
    
    init(frequency: UpdateFrequency) {
        self.interval = frequency.interval
    }
    
    func throttle(action: @escaping () async -> Void) async {
        let now = Date()
        let elapsed = now.timeIntervalSince(lastExecution)
        
        if elapsed >= interval {
            lastExecution = now
            await action()
        }
    }
}

// MARK: - Usage in ViewModels

@MainActor
class ChartViewModel: ObservableObject {
    @Published var chartData: [CandleData] = []
    
    private let priceDebouncer = Debouncer(frequency: .normal)  // 250ms
    private let indicatorThrottler = Throttler(frequency: .slow)  // 500ms
    
    /// Called on every WebSocket price update
    func onPriceUpdate(_ price: Double) {
        Task {
            await priceDebouncer.debounce { [weak self] in
                await self?.updateChartWithPrice(price)
            }
        }
    }
    
    /// Called when user changes indicator settings
    func onIndicatorSettingsChanged() {
        Task {
            await indicatorThrottler.throttle { [weak self] in
                await self?.recalculateIndicators()
            }
        }
    }
    
    private func updateChartWithPrice(_ price: Double) async {
        // Actual chart update logic
    }
    
    private func recalculateIndicators() async {
        // Heavy indicator computation
    }
}
```

**Debounce Specification Table**:

| Component | Event Type | Frequency | Interval | Rationale |
|-----------|------------|-----------|----------|-----------|
| ChartView | Price updates | `.normal` | 250ms | Balance responsiveness vs CPU |
| ChartView | Indicator recalc | `.slow` | 500ms | Heavy computation |
| SearchBar | Text input | `.fast` | 100ms | Responsive autocomplete |
| WatchlistView | Reorder | `.normal` | 250ms | Prevent rapid saves |
| OptionsTable | Sort/filter | `.fast` | 100ms | Quick UI response |
| WebSocket | Reconnect | `.lazy` | 1000ms | Prevent connection spam |

---

### 🟠 MEDIUM PRIORITY (Improve UX & Reliability)

#### 11.4 Cache Staleness Specification

**TTL Tiers**:

| Tier | Age | Status | Action |
|------|-----|--------|--------|
| **Fresh** | < 5 min | ✅ Use directly | No fetch needed |
| **Warm** | 5-30 min | ⚠️ Use + background refresh | Fetch in background |
| **Stale** | 30 min - 6 hr | ⚠️ Show warning | Prompt user to refresh |
| **Critical** | > 6 hr | 🔴 Force refresh | Block until fresh data |

```swift
// client-macos/SwiftBoltML/Services/CacheManager.swift

enum CacheFreshness {
    case fresh      // < 5 min
    case warm       // 5-30 min
    case stale      // 30 min - 6 hr
    case critical   // > 6 hr
    
    init(age: TimeInterval) {
        switch age {
        case ..<300: self = .fresh           // 5 min
        case ..<1800: self = .warm           // 30 min
        case ..<21600: self = .stale         // 6 hr
        default: self = .critical
        }
    }
    
    var shouldBackgroundRefresh: Bool {
        self == .warm
    }
    
    var shouldShowWarning: Bool {
        self == .stale || self == .critical
    }
    
    var shouldBlockUntilRefresh: Bool {
        self == .critical
    }
}

actor CacheManager {
    private var cache: [String: CacheEntry] = [:]
    
    struct CacheEntry {
        let data: Data
        let timestamp: Date
        
        var freshness: CacheFreshness {
            CacheFreshness(age: Date().timeIntervalSince(timestamp))
        }
    }
    
    func get<T: Codable>(_ key: String, type: T.Type) async throws -> (T, CacheFreshness)? {
        guard let entry = cache[key] else { return nil }
        let decoded = try JSONDecoder().decode(T.self, from: entry.data)
        return (decoded, entry.freshness)
    }
}
```

#### 11.5 Model Drift Detection (30-Day Monitoring)

**Already covered in Phase 10.5** - `DriftDetector` class with KS-test.

**Additional**: Add scheduled monitoring job:

```yaml
# .github/workflows/drift-monitoring.yml

name: Model Drift Monitoring

on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8 AM UTC (2 AM CST)
  workflow_dispatch:

jobs:
  check-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd ml
          pip install -r requirements.txt
      
      - name: Run drift detection
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          python src/monitoring/run_drift_check.py --window-days 30
      
      - name: Alert on drift
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "⚠️ Model drift detected! Review required."}
```

#### 11.6 Options Nightly Schedule Specification

**Recommended Schedule**: 2:00 AM CST (8:00 AM UTC)

**Rationale**:
- After market close (4 PM ET) + settlement
- Before pre-market (4 AM ET)
- Low API traffic period

```yaml
# .github/workflows/options-nightly.yml (UPDATED)

name: Options Nightly Backfill

on:
  schedule:
    - cron: '0 8 * * 1-5'  # 2 AM CST, Mon-Fri only
  workflow_dispatch:
    inputs:
      symbols:
        description: 'Comma-separated symbols (empty = all watchlist)'
        required: false

jobs:
  options-backfill:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # Prevent runaway jobs
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd ml
          pip install -r requirements.txt
      
      - name: Get watchlist symbols
        id: symbols
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          SYMBOLS=$(python src/scripts/get_watchlist_symbols.py)
          echo "symbols=$SYMBOLS" >> $GITHUB_OUTPUT
      
      - name: Backfill options data
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          POLYGON_API_KEY: ${{ secrets.POLYGON_API_KEY }}
        run: |
          cd ml
          python src/scripts/backfill_options.py \
            --symbols "${{ steps.symbols.outputs.symbols }}" \
            --incremental
      
      - name: Run ML ranking
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          cd ml
          python src/scripts/run_options_ranking.py
      
      - name: Notify on failure
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "❌ Options nightly job failed! Check logs."}
```

#### 11.7 ML Forecast Staleness Alert

```python
# ml/src/monitoring/forecast_staleness.py

from datetime import datetime, timedelta
from data.supabase_db import SupabaseDatabase
import logging

logger = logging.getLogger(__name__)

STALENESS_THRESHOLD_HOURS = 6


def check_forecast_staleness() -> dict:
    """Check if ML forecasts are stale (> 6 hours old)."""
    db = SupabaseDatabase()
    
    # Get most recent forecast timestamp
    response = db.client.table("ml_forecasts") \
        .select("created_at") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    
    if not response.data:
        return {
            'status': 'CRITICAL',
            'message': 'No forecasts found in database',
            'last_forecast': None,
            'hours_old': None,
        }
    
    last_forecast = datetime.fromisoformat(response.data[0]['created_at'].replace('Z', '+00:00'))
    age = datetime.now(last_forecast.tzinfo) - last_forecast
    hours_old = age.total_seconds() / 3600
    
    if hours_old > STALENESS_THRESHOLD_HOURS:
        status = 'STALE'
        message = f'Forecasts are {hours_old:.1f} hours old (threshold: {STALENESS_THRESHOLD_HOURS}h)'
    else:
        status = 'OK'
        message = f'Forecasts are fresh ({hours_old:.1f} hours old)'
    
    return {
        'status': status,
        'message': message,
        'last_forecast': last_forecast.isoformat(),
        'hours_old': hours_old,
    }


if __name__ == "__main__":
    result = check_forecast_staleness()
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    
    if result['status'] != 'OK':
        exit(1)
```

---

### 🟡 LOW PRIORITY (Nice-to-Have)

#### 11.8 Volatility Surface (Defer to Phase 8)

**Current approach**: Use market-data Greeks from options chain API.

**Future enhancement**: Build IV smile/skew model for better strike selection.

#### 11.9 Delisting & Corporate Actions

**Survivorship bias handling**:
- Flag delisted symbols in `symbols` table
- Exclude from backtest unless explicitly included
- Log corporate actions (splits, dividends) for adjustment

#### 11.10 Runbooks & Cost Monitoring

**Documentation gaps to address**:
- Incident response runbook
- API cost tracking dashboard
- Rate limit monitoring

---

## Updated Implementation Priority (Final)

| Phase | Description | Effort | Impact | Priority |
|-------|-------------|--------|--------|----------|
| **10.1** | **Walk-Forward CV** | **1 day** | **CRITICAL** | **🔴 P0** |
| **10.2** | **LightGBM linear_tree** | **0.5 days** | **CRITICAL** | **🔴 P0** |
| **10.3** | **SuperTrend AI (K-means)** | **2 days** | **CRITICAL** | **🔴 P0** |
| **10.4** | **Direct Multi-Horizon Forecasting** | **1 day** | **CRITICAL** | **🔴 P0** |
| **11.1** | **Backtest Framework** | **2-3 days** | **CRITICAL** | **🔴 P0** |
| **11.2** | **Watchlist Sync** | **1-2 days** | **CRITICAL** | **🔴 P0** |
| **11.3** | **SwiftUI Debounce** | **2-3 days** | **CRITICAL** | **🔴 P0** |
| 10.5 | Drift Detection | 1 day | High | 🟡 P1 |
| 11.4 | Cache Staleness Spec | 0.5 days | Medium | 🟡 P1 |
| 11.5 | Drift Monitoring Job | 0.5 days | Medium | 🟡 P1 |
| 11.6 | Options Nightly Schedule | 0.5 days | Medium | 🟡 P1 |
| 11.7 | Forecast Staleness Alert | 0.5 days | Medium | 🟡 P1 |
| 1.1 | Add Stochastic, KDJ, ADX | 2 days | High | ✅ DONE |
| 1.2 | Add OBV, MFI, VROC | 1 day | Medium | ✅ DONE |
| 2.1 | Port SuperTrend AI | 3 days | Very High | ✅ DONE |
| 6.1 | Enhanced Options Ranker | 2 days | Very High | ✅ DONE |
| 7.1-7.4 | Swift App Integration | 6 days | High | 🟡 P1 |
| 8.1-8.2 | End-to-End Testing | 5 days | Critical | 🔴 P0 |
| 11.8-11.10 | Low Priority Items | 3-5 days | Low | 🟢 P2 |

**Total Estimated Effort**: ~40-45 days

---

## Next Steps (Revised)

1. **Week 1 (CRITICAL)**:
   - Phase 10.1-10.2: Walk-Forward CV + LightGBM linear_tree
   - Phase 11.2: Watchlist Sync (unblocks nightly job)

2. **Week 2 (CRITICAL)**:
   - Phase 10.3-10.4: SuperTrend AI + Direct Forecasting
   - Phase 11.3: SwiftUI Debounce

3. **Week 3**:
   - Phase 11.1: Backtest Framework
   - Phase 1.1-1.2: Technical Indicators

4. **Week 4**:
   - Phase 6: Enhanced Options Ranker
   - Phase 11.4-11.7: Medium priority items

5. **Week 5+**:
   - Phase 7: Swift App Integration
   - Phase 8: End-to-End Testing

---

*Document created: December 19, 2024*
*Last updated: December 20, 2024*
