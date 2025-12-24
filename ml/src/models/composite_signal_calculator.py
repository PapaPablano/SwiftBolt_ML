"""
CORRECTED Composite Signal Calculation
======================================

Properly combines indicators into [-1, 1] directional signal
using corrected weights and normalized scaling.

KEY FIX: ATR used for NORMALIZATION, not directional signal

Generated: 2025-12-24
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class CompositeSignalCalculator:
    """Calculate weighted composite trading signal from corrected indicators."""

    # Corrected weights (verified to sum to 1.0)
    # OLD (PROBLEMATIC):
    # - SuperTrend: 18% [NOT IMPLEMENTED]
    # - RSI: 15% [OK but overweighted]
    # - ADX: 14% [WRONG SMOOTHING]
    # - MACD: 12% [OK]
    # - BB Width: 11% [OK but underutilized]
    # - KDJ: 10% [WRONG SMOOTHING]
    # - MFI: 8% [OK but overlaps]
    # - ATR: 7% [CRITICALLY WRONG - not directional]
    # - Vol Ratio: 5% [OK]

    # NEW (CORRECTED):
    WEIGHTS = {
        "supertrend": 0.20,      # Trend following (NOW PROPERLY IMPLEMENTED)
        "rsi_14": 0.12,          # Momentum (reduced due to overlap)
        "adx": 0.14,             # Trend strength (FIXED: Wilder's smoothing)
        "macd": 0.13,            # MACD histogram direction
        "bb_width": 0.10,        # Volatility regime adaptation
        "kdj_j": 0.12,           # Extreme sensitivity (FIXED: proper smoothing)
        "mfi_14": 0.07,          # Volume-weighted momentum (reduced)
        # "atr": REMOVED - use for NORMALIZATION ONLY
        "volume_ratio": 0.02,    # Signal dampening (minimal weight)
        # Padding to ensure sum = 1.0
        "regime_adjustment": 0.10,  # Dynamic regime-based adjustment
    }

    @staticmethod
    def normalize_to_minus_one_plus_one(value: float, min_val: float, max_val: float) -> float:
        """Normalize value to [-1, +1] range."""
        if min_val == max_val:
            return 0.0
        normalized = 2 * (value - min_val) / (max_val - min_val) - 1
        return np.clip(normalized, -1, 1)

    @staticmethod
    def score_supertrend(supertrend_score: float) -> float:
        """
        Score SuperTrend: +1 bullish, -1 bearish
        supertrend_score is already in [-1, 1] from indicator
        """
        return float(supertrend_score)

    @staticmethod
    def score_rsi(rsi: float) -> float:
        """
        Score RSI: momentum indicator
        < 30: oversold (+1)
        30-40: weak buy (+0.5)
        40-60: neutral (0)
        60-70: weak sell (-0.5)
        > 70: overbought (-1)
        """
        if pd.isna(rsi):
            return 0.0
        if rsi < 30:
            return 1.0
        elif rsi < 40:
            return 0.5
        elif rsi < 60:
            return 0.0
        elif rsi < 70:
            return -0.5
        else:
            return -1.0

    @staticmethod
    def score_adx(plus_di: float, minus_di: float, adx: float) -> float:
        """
        Score ADX: trend strength modulated by direction

        If ADX < 20: weak trend, return smaller score
        If ADX >= 25: strong trend, return larger score
        If +DI > -DI: bullish
        If -DI > +DI: bearish
        """
        if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
            return 0.0

        # Direction component
        if plus_di > minus_di:
            direction = 1.0
        elif minus_di > plus_di:
            direction = -1.0
        else:
            direction = 0.0

        # Strength modulation
        if adx < 20:
            strength = 0.3  # Weak signal
        elif adx < 30:
            strength = 0.7
        else:
            strength = 1.0  # Strong trend

        return direction * strength

    @staticmethod
    def score_macd(macd: float, signal: float, histogram: float) -> float:
        """
        Score MACD: histogram direction and strength
        """
        if pd.isna(histogram) or pd.isna(signal):
            return 0.0

        if histogram > 0:
            # Bullish
            if abs(signal) > 0 and histogram > abs(signal) * 0.1:
                return 1.0
            else:
                return 0.5
        elif histogram < 0:
            # Bearish
            if abs(signal) > 0 and histogram < -abs(signal) * 0.1:
                return -1.0
            else:
                return -0.5
        else:
            return 0.0

    @staticmethod
    def score_bb_width(bb_width: float, bb_width_pct: float) -> float:
        """
        Score Bollinger Bands Width: volatility regime

        Width percentile:
        < 10%: Squeeze (neutral, slight bullish) = 0.2
        10-25%: Low volatility (ready for move) = 0.3
        25-75%: Normal volatility = 0.0
        75-90%: Expansion (continuation likely) = 0.3
        > 90%: High volatility (move ending soon) = -0.2
        """
        if pd.isna(bb_width_pct):
            return 0.0

        if bb_width_pct < 10:
            return 0.2
        elif bb_width_pct < 25:
            return 0.3
        elif bb_width_pct < 75:
            return 0.0
        elif bb_width_pct < 90:
            return 0.3
        else:
            return -0.2

    @staticmethod
    def score_kdj_j(kdj_j: float) -> float:
        """
        Score KDJ-J: extreme oscillator

        J < 0: Strong oversold (+1)
        0-20: Oversold (+0.7)
        20-80: Neutral (0)
        80-100: Overbought (-0.7)
        J > 100: Strong overbought (-1)
        """
        if pd.isna(kdj_j):
            return 0.0

        if kdj_j < 0:
            return 1.0
        elif kdj_j < 20:
            return 0.7
        elif kdj_j < 80:
            return 0.0
        elif kdj_j < 100:
            return -0.7
        else:
            return -1.0

    @staticmethod
    def score_mfi(mfi: float) -> float:
        """
        Score MFI: volume-weighted momentum (similar to RSI scoring)
        """
        if pd.isna(mfi):
            return 0.0

        if mfi < 20:
            return 1.0
        elif mfi < 30:
            return 0.5
        elif mfi < 70:
            return 0.0
        elif mfi < 80:
            return -0.5
        else:
            return -1.0

    @staticmethod
    def score_volume_ratio(vol_ratio: float) -> float:
        """
        Score Volume Ratio: participation dampening
        > 1.3: Strong volume (+0.3)
        1.0-1.3: Normal (+0.0)
        0.7-1.0: Weak (-0.2)
        < 0.7: Very weak (-0.4)
        """
        if pd.isna(vol_ratio):
            return 0.0

        if vol_ratio > 1.3:
            return 0.3
        elif vol_ratio >= 1.0:
            return 0.0
        elif vol_ratio >= 0.7:
            return -0.2
        else:
            return -0.4

    @staticmethod
    def score_regime(adx: float, bb_width_pct: float, rsi: float) -> float:
        """
        Score market regime: trending vs ranging adjustment

        Uses ADX for trend strength and BB width for volatility regime
        """
        if pd.isna(adx) or pd.isna(bb_width_pct):
            return 0.0

        # Trending regime (ADX > 25): boost trend signals
        if adx > 25:
            regime_score = 0.3
        elif adx > 20:
            regime_score = 0.1
        else:
            regime_score = -0.1  # Ranging: slightly dampen

        # Squeeze detection: potential breakout
        if bb_width_pct < 15:
            regime_score += 0.2

        return np.clip(regime_score, -1, 1)

    @staticmethod
    def calculate_composite_score(row: pd.Series) -> Tuple[float, Dict[str, float]]:
        """
        Calculate composite score and individual component scores.

        Args:
            row: DataFrame row with all indicator values

        Returns:
            (composite_score, component_scores_dict)
        """
        scores = {}

        try:
            # Score each indicator
            scores["supertrend"] = CompositeSignalCalculator.score_supertrend(
                row.get("supertrend_score", 0)
            )
            scores["rsi_14"] = CompositeSignalCalculator.score_rsi(
                row.get("rsi_14", 50)
            )
            scores["adx"] = CompositeSignalCalculator.score_adx(
                row.get("plus_di", 0),
                row.get("minus_di", 0),
                row.get("adx", 0)
            )
            scores["macd"] = CompositeSignalCalculator.score_macd(
                row.get("macd", 0),
                row.get("macd_signal", 0),
                row.get("macd_hist", 0)
            )
            scores["bb_width"] = CompositeSignalCalculator.score_bb_width(
                row.get("bb_width", 0),
                row.get("bb_width_pct", 50)
            )
            scores["kdj_j"] = CompositeSignalCalculator.score_kdj_j(
                row.get("kdj_j", 50)
            )
            scores["mfi_14"] = CompositeSignalCalculator.score_mfi(
                row.get("mfi_14", 50)
            )
            scores["volume_ratio"] = CompositeSignalCalculator.score_volume_ratio(
                row.get("volume_ratio", 1.0)
            )
            scores["regime_adjustment"] = CompositeSignalCalculator.score_regime(
                row.get("adx", 0),
                row.get("bb_width_pct", 50),
                row.get("rsi_14", 50)
            )

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Error calculating scores: {e}")
            return 0.0, {k: 0.0 for k in CompositeSignalCalculator.WEIGHTS.keys()}

        # Calculate weighted composite
        composite = sum(
            scores.get(key, 0.0) * weight
            for key, weight in CompositeSignalCalculator.WEIGHTS.items()
        )

        # Normalize ATR for signal scaling (but don't use as directional)
        # Higher volatility = dampen signal slightly
        try:
            atr_norm = row.get("atr_normalized", 0)
            if atr_norm > 0:
                volatility_dampener = 1.0 / (1.0 + atr_norm / 100.0)
                composite = composite * volatility_dampener
        except (KeyError, TypeError):
            pass

        return np.clip(composite, -1, 1), scores

    @staticmethod
    def add_composite_signals(df: pd.DataFrame) -> pd.DataFrame:
        """Add composite score and label to DataFrame."""
        df = df.copy()

        composite_scores = []
        component_scores_list = []

        for idx, row in df.iterrows():
            score, components = CompositeSignalCalculator.calculate_composite_score(row)
            composite_scores.append(score)
            component_scores_list.append(components)

        df["composite_score"] = composite_scores

        # Generate labels based on thresholds
        df["signal_label"] = "neutral"
        df.loc[df["composite_score"] > 0.3, "signal_label"] = "bullish"
        df.loc[df["composite_score"] < -0.3, "signal_label"] = "bearish"

        # Confidence based on score magnitude
        df["signal_confidence"] = df["composite_score"].abs()

        logger.info(f"Added composite signals to {len(df)} rows")

        return df

    @staticmethod
    def get_signal_breakdown(row: pd.Series) -> Dict[str, any]:
        """Get detailed breakdown of signal components for explainability."""
        score, components = CompositeSignalCalculator.calculate_composite_score(row)

        # Calculate contribution of each component
        contributions = {
            key: components.get(key, 0) * CompositeSignalCalculator.WEIGHTS.get(key, 0)
            for key in CompositeSignalCalculator.WEIGHTS.keys()
        }

        # Sort by absolute contribution
        sorted_contributions = dict(
            sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)
        )

        return {
            "composite_score": score,
            "signal_label": "bullish" if score > 0.3 else ("bearish" if score < -0.3 else "neutral"),
            "component_scores": components,
            "weighted_contributions": sorted_contributions,
            "top_contributors": list(sorted_contributions.keys())[:3],
        }


if __name__ == "__main__":
    # Verify weights sum to 1.0
    total = sum(CompositeSignalCalculator.WEIGHTS.values())
    print(f"Weights sum: {total:.2f}")
    assert np.isclose(total, 1.0), f"Weights must sum to 1.0, got {total}"
    print("Composite signal calculator loaded and validated")
