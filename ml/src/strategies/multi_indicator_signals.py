"""
Multi-Indicator Signal Generator for composite trading signals.

This module combines multiple technical indicators to generate weighted
trading signals with confidence scores.

Usage:
    generator = MultiIndicatorSignalGenerator()
    signal = generator.generate_signal(df_with_indicators)
    # Returns: {'signal': 'Buy'|'Sell'|'Hold', 'confidence': 0.0-1.0, 'components': {...}}
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MultiIndicatorSignalGenerator:
    """
    Generates trading signals by combining multiple technical indicators.

    Each indicator contributes a score from -1 (bearish) to +1 (bullish),
    weighted by configurable importance. The composite score determines
    the final signal.

    Default weights prioritize:
    - SuperTrend (25%) - trend-following with ML optimization
    - RSI/MACD/KDJ (15% each) - momentum indicators
    - ADX (10%) - trend strength confirmation
    - Bollinger/Volume (10% each) - volatility/volume confirmation
    """

    def __init__(
        self,
        indicator_weights: Optional[Dict[str, float]] = None,
        buy_threshold: float = 0.3,
        sell_threshold: float = -0.3,
    ):
        """
        Initialize the signal generator.

        Args:
            indicator_weights: Dict mapping indicator names to weights (0-1).
                              Weights should sum to 1.0.
            buy_threshold: Composite score above which to generate Buy signal
            sell_threshold: Composite score below which to generate Sell signal
        """
        self.indicator_weights = indicator_weights or {
            "rsi": 0.15,
            "macd": 0.15,
            "kdj": 0.15,
            "adx": 0.10,
            "bollinger": 0.10,
            "volume": 0.10,
            "supertrend": 0.25,
        }
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

        # Validate weights sum to ~1.0
        total_weight = sum(self.indicator_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(
                f"Indicator weights sum to {total_weight:.2f}, not 1.0. "
                "Signals will be normalized."
            )

    def _score_rsi(self, df: pd.DataFrame) -> float:
        """
        Score RSI indicator.

        RSI < 30: Oversold = Bullish (+1)
        RSI > 70: Overbought = Bearish (-1)
        RSI 30-70: Neutral (0)
        """
        if "rsi_14" not in df.columns:
            return 0.0

        rsi = df["rsi_14"].iloc[-1]
        if pd.isna(rsi):
            return 0.0

        if rsi < 30:
            return 1.0  # Oversold = Buy signal
        elif rsi > 70:
            return -1.0  # Overbought = Sell signal
        elif rsi < 40:
            return 0.5  # Approaching oversold
        elif rsi > 60:
            return -0.5  # Approaching overbought
        return 0.0

    def _score_macd(self, df: pd.DataFrame) -> float:
        """
        Score MACD indicator.

        Histogram positive and increasing: Bullish
        Histogram negative and decreasing: Bearish
        """
        if "macd_hist" not in df.columns or len(df) < 2:
            return 0.0

        macd_hist = df["macd_hist"].iloc[-1]
        macd_hist_prev = df["macd_hist"].iloc[-2]

        if pd.isna(macd_hist) or pd.isna(macd_hist_prev):
            return 0.0

        if macd_hist > 0 and macd_hist > macd_hist_prev:
            return 1.0  # Bullish momentum increasing
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            return -1.0  # Bearish momentum increasing
        elif macd_hist > 0:
            return 0.5  # Bullish but weakening
        elif macd_hist < 0:
            return -0.5  # Bearish but weakening
        return 0.0

    def _score_kdj(self, df: pd.DataFrame) -> float:
        """
        Score KDJ indicator.

        J < 0: Oversold = Bullish
        J > 100: Overbought = Bearish
        J-D divergence indicates early reversals
        """
        if "kdj_j" not in df.columns:
            return 0.0

        j = df["kdj_j"].iloc[-1]
        if pd.isna(j):
            return 0.0

        if j < 0:
            return 1.0  # Strong oversold
        elif j > 100:
            return -1.0  # Strong overbought
        elif j < 20:
            return 0.5  # Oversold zone
        elif j > 80:
            return -0.5  # Overbought zone
        return 0.0

    def _score_adx(self, df: pd.DataFrame) -> float:
        """
        Score ADX indicator.

        ADX measures trend strength, not direction.
        +DI > -DI with strong ADX: Bullish
        -DI > +DI with strong ADX: Bearish
        Weak ADX: No clear signal (neutral)
        """
        if "adx" not in df.columns or "plus_di" not in df.columns:
            return 0.0

        adx = df["adx"].iloc[-1]
        plus_di = df["plus_di"].iloc[-1]
        minus_di = df["minus_di"].iloc[-1]

        if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
            return 0.0

        # Only generate signals when trend is strong enough
        if adx > 25:
            if plus_di > minus_di:
                return min(1.0, (adx - 25) / 25)  # Scale by trend strength
            else:
                return max(-1.0, -(adx - 25) / 25)
        return 0.0

    def _score_bollinger(self, df: pd.DataFrame) -> float:
        """
        Score Bollinger Bands.

        Price below lower band: Oversold = Bullish
        Price above upper band: Overbought = Bearish
        """
        if "bb_upper" not in df.columns or "bb_lower" not in df.columns:
            return 0.0

        close = df["close"].iloc[-1]
        bb_upper = df["bb_upper"].iloc[-1]
        bb_lower = df["bb_lower"].iloc[-1]
        bb_middle = df["bb_middle"].iloc[-1]

        if pd.isna(close) or pd.isna(bb_upper) or pd.isna(bb_lower):
            return 0.0

        if close < bb_lower:
            return 1.0  # Below lower band = Buy
        elif close > bb_upper:
            return -1.0  # Above upper band = Sell
        elif close < bb_middle:
            # Proportional score based on position in band
            return (bb_middle - close) / (bb_middle - bb_lower) * 0.5
        else:
            return -(close - bb_middle) / (bb_upper - bb_middle) * 0.5

    def _score_volume(self, df: pd.DataFrame) -> float:
        """
        Score volume indicator.

        High volume confirms the current trend signal.
        Returns a multiplier based on volume ratio.
        """
        if "volume_ratio" not in df.columns:
            return 0.0

        vol_ratio = df["volume_ratio"].iloc[-1]
        if pd.isna(vol_ratio):
            return 0.0

        # Get MACD direction to confirm with volume
        macd_signal = self._score_macd(df)

        if vol_ratio > 1.5:
            # High volume confirms trend
            return macd_signal * 0.5
        elif vol_ratio > 1.2:
            return macd_signal * 0.25
        return 0.0

    def _score_supertrend(self, df: pd.DataFrame) -> float:
        """
        Score SuperTrend indicator.

        Trend = 1: Bullish
        Trend = 0 or -1: Bearish
        Signal changes are stronger signals
        """
        if "supertrend_trend" not in df.columns:
            return 0.0

        trend = df["supertrend_trend"].iloc[-1]

        if pd.isna(trend):
            return 0.0

        # Check for recent signal change (stronger signal)
        if "supertrend_signal" in df.columns and len(df) >= 1:
            signal = df["supertrend_signal"].iloc[-1]
            if signal == 1:  # Fresh buy signal
                return 1.0
            elif signal == -1:  # Fresh sell signal
                return -1.0

        # Ongoing trend
        return 1.0 if trend == 1 else -1.0

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate composite signal from all indicators.

        Args:
            df: DataFrame with technical indicators computed

        Returns:
            Dict containing:
            - signal: 'Buy', 'Sell', or 'Hold'
            - confidence: 0.0 to 1.0 (strength of signal)
            - composite_score: Raw weighted score (-1 to 1)
            - components: Individual indicator scores
        """
        if len(df) < 2:
            return {
                "signal": "Hold",
                "confidence": 0.0,
                "composite_score": 0.0,
                "components": {},
            }

        # Calculate individual scores
        scores = {
            "rsi": self._score_rsi(df),
            "macd": self._score_macd(df),
            "kdj": self._score_kdj(df),
            "adx": self._score_adx(df),
            "bollinger": self._score_bollinger(df),
            "volume": self._score_volume(df),
            "supertrend": self._score_supertrend(df),
        }

        # Calculate weighted composite
        composite = 0.0
        total_weight = 0.0

        for indicator, weight in self.indicator_weights.items():
            if indicator in scores:
                composite += scores[indicator] * weight
                total_weight += weight

        if total_weight > 0:
            composite /= total_weight

        # Determine signal
        if composite > self.buy_threshold:
            signal = "Buy"
        elif composite < self.sell_threshold:
            signal = "Sell"
        else:
            signal = "Hold"

        # Confidence is the magnitude of the signal
        confidence = min(abs(composite), 1.0)

        result = {
            "signal": signal,
            "confidence": confidence,
            "composite_score": composite,
            "components": scores,
        }

        logger.debug(
            f"Signal generated: {signal} (confidence={confidence:.2f}, "
            f"composite={composite:.3f})"
        )

        return result

    def generate_signal_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals for entire DataFrame (rolling).

        Useful for backtesting - generates signal for each row.

        Args:
            df: DataFrame with technical indicators

        Returns:
            DataFrame with signal, confidence, composite_score columns
        """
        signals = []

        # Minimum window for stable indicators
        min_window = 50

        for i in range(len(df)):
            if i < min_window:
                signals.append(
                    {
                        "signal": "Hold",
                        "confidence": 0.0,
                        "composite_score": 0.0,
                    }
                )
            else:
                window_df = df.iloc[: i + 1]
                result = self.generate_signal(window_df)
                signals.append(
                    {
                        "signal": result["signal"],
                        "confidence": result["confidence"],
                        "composite_score": result["composite_score"],
                    }
                )

        result_df = pd.DataFrame(signals)
        result_df.index = df.index

        return result_df

    def get_trend_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Comprehensive trend analysis using all available indicators.

        Returns detailed breakdown for options ranking and display.

        Args:
            df: DataFrame with technical indicators

        Returns:
            Dict with trend label, composite signal, individual readings,
            and confidence score
        """
        if len(df) < 2:
            return {
                "trend": "neutral",
                "composite_signal": 0.0,
                "supertrend_signal": 0,
                "adx": 0.0,
                "rsi": 50.0,
                "confidence": 0.0,
            }

        latest = df.iloc[-1]

        # SuperTrend signal
        supertrend_signal = 0
        if "supertrend_trend" in df.columns:
            trend_val = latest.get("supertrend_trend", 0)
            supertrend_signal = int(trend_val) if pd.notna(trend_val) else 0

        # Individual indicator values
        adx = latest.get("adx", 20)
        plus_di = latest.get("plus_di", 50)
        minus_di = latest.get("minus_di", 50)
        rsi = latest.get("rsi_14", 50)
        macd_hist = latest.get("macd_hist", 0)
        kdj_j = latest.get("kdj_j", 50)

        # Generate full signal
        signal_result = self.generate_signal(df)
        composite = signal_result["composite_score"]

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
            "adx": float(adx) if pd.notna(adx) else 0.0,
            "plus_di": float(plus_di) if pd.notna(plus_di) else 50.0,
            "minus_di": float(minus_di) if pd.notna(minus_di) else 50.0,
            "rsi": float(rsi) if pd.notna(rsi) else 50.0,
            "macd_hist": float(macd_hist) if pd.notna(macd_hist) else 0.0,
            "kdj_j": float(kdj_j) if pd.notna(kdj_j) else 50.0,
            "confidence": signal_result["confidence"],
        }
