"""
Adaptive classification thresholds based on market volatility.
Thresholds adjust to market regime: wider in high volatility, tighter in low.
"""

import logging
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class AdaptiveThresholds:
    """Compute dynamic thresholds based on market volatility."""

    @staticmethod
    def compute_thresholds(
        df: pd.DataFrame,
        volatility_window: int = 20,
        zscore_threshold: float = 1.0,
    ) -> Tuple[float, float]:
        """
        Compute bullish/bearish thresholds using rolling volatility.

        Args:
            df: DataFrame with OHLCV
            volatility_window: Window for volatility calculation
            zscore_threshold: How many vol-sigmas for threshold

        Returns:
            (bearish_threshold, bullish_threshold)
        """
        returns = df["close"].pct_change()

        current_vol = returns.iloc[-volatility_window:].std()
        baseline_vol = returns.std()
        vol_ratio = (
            current_vol / baseline_vol
            if baseline_vol and baseline_vol > 0
            else 1.0
        )

        base_bearish = -0.02
        base_bullish = 0.02

        bearish_threshold = base_bearish * vol_ratio * zscore_threshold
        bullish_threshold = base_bullish * vol_ratio * zscore_threshold

        logger.info(
            "Adaptive thresholds - vol_ratio=%.2f range=[%.4f, %.4f]",
            vol_ratio,
            bearish_threshold,
            bullish_threshold,
        )

        return bearish_threshold, bullish_threshold

    @staticmethod
    def compute_thresholds_atr(
        df: pd.DataFrame,
        atr_window: int = 14,
        multiplier: float = 1.0,
    ) -> Tuple[float, float]:
        """
        Compute thresholds based on ATR (Average True Range).

        Args:
            df: DataFrame with OHLCV (should include 'atr' column)
            atr_window: ATR window
            multiplier: How many ATRs for threshold

        Returns:
            (bearish_threshold, bullish_threshold)
        """
        if "atr" not in df.columns:
            return AdaptiveThresholds.compute_thresholds(df)

        current_price = df["close"].iloc[-1]
        current_atr = df["atr"].iloc[-1]

        threshold = (
            (current_atr / current_price) * multiplier
            if current_price
            else 0.02
        )

        bearish_threshold = -threshold
        bullish_threshold = threshold

        logger.info(
            "ATR-based thresholds - ATR=%.4f range=[%.4f, %.4f]",
            current_atr,
            bearish_threshold,
            bullish_threshold,
        )

        return bearish_threshold, bullish_threshold
