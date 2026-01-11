"""
Regime Conditioner - Adjusts ranking weights based on market regime.

Implements Perplexity's recommendation:
"Use the same high-level regimes as forecasting:
- trend regime (SuperTrend / ADX)
- vol regime (ATR / rolling std)

Then switch weights:
- trending regime: emphasize momentum/trend/runner signals
- mean-reverting regime: emphasize value/IV rank/spread"

This is compatible with existing underlying_trend and historical_vol
computations in the ranking system.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TrendRegime(Enum):
    """Market trend regime classification."""

    STRONG_TREND = "strong_trend"
    WEAK_TREND = "weak_trend"
    NEUTRAL = "neutral"
    MEAN_REVERTING = "mean_reverting"


class VolatilityRegime(Enum):
    """Market volatility regime classification."""

    HIGH_VOL = "high_vol"
    NORMAL_VOL = "normal_vol"
    LOW_VOL = "low_vol"


@dataclass
class RegimeState:
    """Current market regime state."""

    trend_regime: TrendRegime
    vol_regime: VolatilityRegime
    adx: float
    atr_pct: float
    supertrend_signal: int
    trend_confidence: float
    vol_percentile: float

    def __str__(self) -> str:
        return (
            f"Regime: {self.trend_regime.value} / {self.vol_regime.value} "
            f"(ADX={self.adx:.1f}, ATR%={self.atr_pct:.2%}, "
            f"conf={self.trend_confidence:.2f})"
        )


@dataclass
class RegimeWeights:
    """Ranking weights for a specific regime."""

    momentum: float
    value: float
    greeks: float
    regime_name: str

    def as_dict(self) -> Dict[str, float]:
        return {
            "momentum": self.momentum,
            "value": self.value,
            "greeks": self.greeks,
        }

    def __str__(self) -> str:
        return (
            f"{self.regime_name}: Mom={self.momentum:.0%}, "
            f"Val={self.value:.0%}, Greeks={self.greeks:.0%}"
        )


class RegimeConditioner:
    """
    Detects market regime and provides regime-conditioned ranking weights.

    Regime Detection:
    1. Trend Regime (from ADX + SuperTrend):
       - Strong Trend: ADX > 25 and SuperTrend aligned
       - Weak Trend: ADX 15-25 or mixed signals
       - Neutral: ADX < 15
       - Mean Reverting: Low ADX + high vol + range-bound

    2. Volatility Regime (from ATR% + rolling std):
       - High Vol: ATR% > 75th percentile of history
       - Normal Vol: ATR% 25th-75th percentile
       - Low Vol: ATR% < 25th percentile

    Weight Adjustments:
    - Strong Trend: Boost momentum (50%), reduce value (25%)
    - Mean Reverting: Boost value (45%), reduce momentum (25%)
    - High Vol: Boost greeks (35%), moderate momentum
    - Low Vol: Boost value (40%), reduce greeks
    """

    # Default weights (baseline)
    DEFAULT_WEIGHTS = RegimeWeights(momentum=0.40, value=0.35, greeks=0.25, regime_name="default")

    # Regime-specific weight configurations
    REGIME_WEIGHTS = {
        # Strong trending market: emphasize momentum/runners
        (TrendRegime.STRONG_TREND, VolatilityRegime.NORMAL_VOL): RegimeWeights(
            momentum=0.50, value=0.25, greeks=0.25, regime_name="strong_trend_normal_vol"
        ),
        (TrendRegime.STRONG_TREND, VolatilityRegime.HIGH_VOL): RegimeWeights(
            momentum=0.45, value=0.20, greeks=0.35, regime_name="strong_trend_high_vol"
        ),
        (TrendRegime.STRONG_TREND, VolatilityRegime.LOW_VOL): RegimeWeights(
            momentum=0.55, value=0.25, greeks=0.20, regime_name="strong_trend_low_vol"
        ),
        # Weak trend: balanced approach
        (TrendRegime.WEAK_TREND, VolatilityRegime.NORMAL_VOL): RegimeWeights(
            momentum=0.40, value=0.35, greeks=0.25, regime_name="weak_trend_normal_vol"
        ),
        (TrendRegime.WEAK_TREND, VolatilityRegime.HIGH_VOL): RegimeWeights(
            momentum=0.35, value=0.30, greeks=0.35, regime_name="weak_trend_high_vol"
        ),
        (TrendRegime.WEAK_TREND, VolatilityRegime.LOW_VOL): RegimeWeights(
            momentum=0.40, value=0.40, greeks=0.20, regime_name="weak_trend_low_vol"
        ),
        # Neutral: balanced
        (TrendRegime.NEUTRAL, VolatilityRegime.NORMAL_VOL): RegimeWeights(
            momentum=0.35, value=0.40, greeks=0.25, regime_name="neutral_normal_vol"
        ),
        (TrendRegime.NEUTRAL, VolatilityRegime.HIGH_VOL): RegimeWeights(
            momentum=0.30, value=0.35, greeks=0.35, regime_name="neutral_high_vol"
        ),
        (TrendRegime.NEUTRAL, VolatilityRegime.LOW_VOL): RegimeWeights(
            momentum=0.35, value=0.45, greeks=0.20, regime_name="neutral_low_vol"
        ),
        # Mean reverting: emphasize value/IV rank/spread
        (TrendRegime.MEAN_REVERTING, VolatilityRegime.NORMAL_VOL): RegimeWeights(
            momentum=0.25, value=0.45, greeks=0.30, regime_name="mean_reverting_normal_vol"
        ),
        (TrendRegime.MEAN_REVERTING, VolatilityRegime.HIGH_VOL): RegimeWeights(
            momentum=0.20, value=0.40, greeks=0.40, regime_name="mean_reverting_high_vol"
        ),
        (TrendRegime.MEAN_REVERTING, VolatilityRegime.LOW_VOL): RegimeWeights(
            momentum=0.25, value=0.50, greeks=0.25, regime_name="mean_reverting_low_vol"
        ),
    }

    # Thresholds for regime detection
    ADX_STRONG_TREND = 25.0
    ADX_WEAK_TREND = 15.0
    VOL_HIGH_PERCENTILE = 75
    VOL_LOW_PERCENTILE = 25

    def __init__(
        self,
        lookback_days: int = 60,
        smooth_transitions: bool = True,
        transition_alpha: float = 0.3,
    ):
        """
        Initialize regime conditioner.

        Args:
            lookback_days: Days of history for volatility percentile
            smooth_transitions: Blend weights during regime transitions
            transition_alpha: Blending factor for smooth transitions
        """
        self.lookback_days = lookback_days
        self.smooth_transitions = smooth_transitions
        self.transition_alpha = transition_alpha
        self._previous_weights: Optional[RegimeWeights] = None
        self._vol_history: list = []

    def detect_regime(
        self,
        df_ohlc: pd.DataFrame,
        supertrend_signal: Optional[int] = None,
    ) -> RegimeState:
        """
        Detect current market regime from OHLC data.

        Args:
            df_ohlc: DataFrame with OHLC data (needs at least 20 bars)
            supertrend_signal: SuperTrend signal (-1, 0, 1) if available

        Returns:
            RegimeState with detected regime
        """
        if len(df_ohlc) < 20:
            logger.warning("Insufficient data for regime detection")
            return RegimeState(
                trend_regime=TrendRegime.NEUTRAL,
                vol_regime=VolatilityRegime.NORMAL_VOL,
                adx=20.0,
                atr_pct=0.02,
                supertrend_signal=0,
                trend_confidence=0.5,
                vol_percentile=50.0,
            )

        # Calculate ADX if not present
        if "adx" in df_ohlc.columns:
            adx = float(df_ohlc["adx"].iloc[-1])
        else:
            adx = self._calculate_adx(df_ohlc)

        # Calculate ATR percentage
        atr_pct = self._calculate_atr_pct(df_ohlc)

        # Update volatility history
        self._vol_history.append(atr_pct)
        if len(self._vol_history) > self.lookback_days:
            self._vol_history = self._vol_history[-self.lookback_days :]

        # Calculate volatility percentile
        if len(self._vol_history) >= 10:
            vol_percentile = (
                np.sum(np.array(self._vol_history) <= atr_pct) / len(self._vol_history) * 100
            )
        else:
            vol_percentile = 50.0

        # Get SuperTrend signal
        if supertrend_signal is None:
            if "supertrend_trend" in df_ohlc.columns:
                supertrend_signal = int(df_ohlc["supertrend_trend"].iloc[-1])
            else:
                supertrend_signal = 0

        # Detect trend regime
        trend_regime, trend_confidence = self._classify_trend_regime(
            adx, supertrend_signal, df_ohlc
        )

        # Detect volatility regime
        vol_regime = self._classify_vol_regime(vol_percentile)

        return RegimeState(
            trend_regime=trend_regime,
            vol_regime=vol_regime,
            adx=adx,
            atr_pct=atr_pct,
            supertrend_signal=supertrend_signal,
            trend_confidence=trend_confidence,
            vol_percentile=vol_percentile,
        )

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ADX from OHLC data."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # True Range
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )

        # Directional Movement
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed averages (Wilder's smoothing)
        def wilder_smooth(arr, period):
            result = np.zeros_like(arr)
            result[period - 1] = np.mean(arr[:period])
            for i in range(period, len(arr)):
                result[i] = (result[i - 1] * (period - 1) + arr[i]) / period
            return result

        atr = wilder_smooth(tr, period)
        plus_di = 100 * wilder_smooth(plus_dm, period) / (atr + 1e-10)
        minus_di = 100 * wilder_smooth(minus_dm, period) / (atr + 1e-10)

        # DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = wilder_smooth(dx, period)

        return float(adx[-1]) if len(adx) > 0 else 20.0

    def _calculate_atr_pct(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR as percentage of price."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])),
        )

        atr = np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
        current_price = close[-1]

        return atr / current_price if current_price > 0 else 0.02

    def _classify_trend_regime(
        self,
        adx: float,
        supertrend_signal: int,
        df: pd.DataFrame,
    ) -> Tuple[TrendRegime, float]:
        """Classify trend regime from ADX and SuperTrend."""
        # Check for range-bound (mean-reverting) conditions
        if len(df) >= 20:
            close = df["close"].values[-20:]
            price_range = (close.max() - close.min()) / close.mean()
            is_range_bound = price_range < 0.05  # Less than 5% range
        else:
            is_range_bound = False

        # Strong trend: high ADX with aligned SuperTrend
        if adx >= self.ADX_STRONG_TREND and supertrend_signal != 0:
            confidence = min(1.0, (adx - 20) / 20)
            return TrendRegime.STRONG_TREND, confidence

        # Mean reverting: low ADX and range-bound
        if adx < self.ADX_WEAK_TREND and is_range_bound:
            confidence = min(1.0, (self.ADX_WEAK_TREND - adx) / 10)
            return TrendRegime.MEAN_REVERTING, confidence

        # Weak trend: moderate ADX
        if adx >= self.ADX_WEAK_TREND:
            confidence = 0.5 + (adx - self.ADX_WEAK_TREND) / 20
            return TrendRegime.WEAK_TREND, min(1.0, confidence)

        # Neutral: low ADX, not range-bound
        confidence = 0.5
        return TrendRegime.NEUTRAL, confidence

    def _classify_vol_regime(self, vol_percentile: float) -> VolatilityRegime:
        """Classify volatility regime from percentile."""
        if vol_percentile >= self.VOL_HIGH_PERCENTILE:
            return VolatilityRegime.HIGH_VOL
        elif vol_percentile <= self.VOL_LOW_PERCENTILE:
            return VolatilityRegime.LOW_VOL
        else:
            return VolatilityRegime.NORMAL_VOL

    def get_regime_weights(
        self,
        regime_state: RegimeState,
    ) -> RegimeWeights:
        """
        Get ranking weights for the current regime.

        Args:
            regime_state: Current market regime

        Returns:
            RegimeWeights for the regime
        """
        key = (regime_state.trend_regime, regime_state.vol_regime)
        weights = self.REGIME_WEIGHTS.get(key, self.DEFAULT_WEIGHTS)

        # Apply smooth transitions if enabled
        if self.smooth_transitions and self._previous_weights is not None:
            weights = self._blend_weights(self._previous_weights, weights)

        self._previous_weights = weights

        logger.info(f"Regime weights: {weights}")
        return weights

    def _blend_weights(
        self,
        prev: RegimeWeights,
        curr: RegimeWeights,
    ) -> RegimeWeights:
        """Blend weights for smooth regime transitions."""
        alpha = self.transition_alpha
        return RegimeWeights(
            momentum=alpha * curr.momentum + (1 - alpha) * prev.momentum,
            value=alpha * curr.value + (1 - alpha) * prev.value,
            greeks=alpha * curr.greeks + (1 - alpha) * prev.greeks,
            regime_name=f"blended_{curr.regime_name}",
        )

    def condition_ranking(
        self,
        df: pd.DataFrame,
        regime_state: RegimeState,
        momentum_col: str = "momentum_score",
        value_col: str = "value_score",
        greeks_col: str = "greeks_score",
    ) -> pd.DataFrame:
        """
        Apply regime-conditioned weights to ranking scores.

        Args:
            df: DataFrame with component scores
            regime_state: Current market regime
            momentum_col: Column name for momentum score
            value_col: Column name for value score
            greeks_col: Column name for greeks score

        Returns:
            DataFrame with regime_conditioned_rank column
        """
        weights = self.get_regime_weights(regime_state)

        df = df.copy()

        # Calculate regime-conditioned composite rank
        df["regime_conditioned_rank"] = (
            df[momentum_col] * weights.momentum
            + df[value_col] * weights.value
            + df[greeks_col] * weights.greeks
        )

        # Add regime metadata
        df["trend_regime"] = regime_state.trend_regime.value
        df["vol_regime"] = regime_state.vol_regime.value
        df["regime_adx"] = regime_state.adx
        df["regime_atr_pct"] = regime_state.atr_pct
        df["regime_weights"] = str(weights.as_dict())

        return df

    def get_signal_emphasis(
        self,
        regime_state: RegimeState,
    ) -> Dict[str, float]:
        """
        Get signal emphasis multipliers for the current regime.

        Returns multipliers for different signal types:
        - runner: Momentum runner signals
        - discount: Value discount signals
        - greeks: Greeks-aligned signals

        In trending regimes, runner signals get boosted.
        In mean-reverting regimes, discount signals get boosted.
        """
        trend = regime_state.trend_regime
        vol = regime_state.vol_regime

        # Base multipliers
        emphasis = {
            "runner": 1.0,
            "discount": 1.0,
            "greeks": 1.0,
        }

        # Trend regime adjustments
        if trend == TrendRegime.STRONG_TREND:
            emphasis["runner"] = 1.5
            emphasis["discount"] = 0.7
        elif trend == TrendRegime.MEAN_REVERTING:
            emphasis["runner"] = 0.7
            emphasis["discount"] = 1.5
        elif trend == TrendRegime.WEAK_TREND:
            emphasis["runner"] = 1.2
            emphasis["discount"] = 0.9

        # Volatility regime adjustments
        if vol == VolatilityRegime.HIGH_VOL:
            emphasis["greeks"] = 1.3
            emphasis["runner"] *= 0.9
        elif vol == VolatilityRegime.LOW_VOL:
            emphasis["greeks"] = 0.8
            emphasis["discount"] *= 1.1

        return emphasis


def detect_and_condition(
    df_ohlc: pd.DataFrame,
    rankings_df: pd.DataFrame,
    supertrend_signal: Optional[int] = None,
) -> Tuple[pd.DataFrame, RegimeState]:
    """
    Convenience function to detect regime and condition rankings.

    Args:
        df_ohlc: OHLC data for regime detection
        rankings_df: Rankings to condition
        supertrend_signal: Optional SuperTrend signal

    Returns:
        Tuple of (conditioned rankings, regime state)
    """
    conditioner = RegimeConditioner()
    regime = conditioner.detect_regime(df_ohlc, supertrend_signal)
    conditioned = conditioner.condition_ranking(rankings_df, regime)

    return conditioned, regime
