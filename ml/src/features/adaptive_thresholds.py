"""
Adaptive classification thresholds based on market volatility.
Thresholds adjust to market regime: wider in high volatility, tighter in low.
Horizon-aware: shorter horizons use tighter thresholds, longer horizons use wider.
"""

import logging
from typing import Tuple

import numpy as np
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
        vol_ratio = current_vol / baseline_vol if baseline_vol and baseline_vol > 0 else 1.0

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

        threshold = (current_atr / current_price) * multiplier if current_price else 0.02

        bearish_threshold = -threshold
        bullish_threshold = threshold

        logger.info(
            "ATR-based thresholds - ATR=%.4f range=[%.4f, %.4f]",
            current_atr,
            bearish_threshold,
            bullish_threshold,
        )

        return bearish_threshold, bullish_threshold

    @staticmethod
    def compute_thresholds_percentile(
        df: pd.DataFrame,
        horizon_days: int = 1,
        bearish_percentile: float = 0.35,
        bullish_percentile: float = 0.65,
    ) -> Tuple[float, float]:
        """
        Compute thresholds based on historical return distribution (percentile-based).

        Goal: Create balanced label distribution (e.g., 30% bearish, 40% neutral, 30% bullish)
        instead of ATR-based which creates 96-100% neutral in low-volatility regimes.

        Args:
            df: DataFrame with OHLCV
            horizon_days: Forecast horizon in days
            bearish_percentile: Percentile for bearish threshold (default 0.35 = 35th percentile)
            bullish_percentile: Percentile for bullish threshold (default 0.65 = 65th percentile)

        Returns:
            (bearish_threshold, bullish_threshold)
        """
        horizon_days = max(1, int(horizon_days))
        returns = df["close"].pct_change()

        # Compute forward returns for this horizon
        forward_returns = returns.rolling(horizon_days).sum().shift(-horizon_days)
        forward_returns = forward_returns.dropna()

        if len(forward_returns) < 30:
            logger.warning("Insufficient data for percentile thresholds, falling back to ATR")
            return AdaptiveThresholds.compute_thresholds_horizon(df, horizon_days)

        # Use percentiles to set thresholds (creates 30-40-30 split by default)
        bearish_threshold = float(forward_returns.quantile(bearish_percentile))
        bullish_threshold = float(forward_returns.quantile(bullish_percentile))

        logger.info(
            "Percentile thresholds (%.0fD) - range=[%.4f, %.4f] (p%.0f/p%.0f)",
            horizon_days,
            bearish_threshold,
            bullish_threshold,
            bearish_percentile * 100,
            bullish_percentile * 100,
        )

        return bearish_threshold, bullish_threshold

    @staticmethod
    def compute_thresholds_horizon(
        df: pd.DataFrame,
        horizon_days: int = 1,
        atr_multiplier: float = 1.0,
        use_atr_prefer: bool = True,
        use_percentile: bool = True,
    ) -> Tuple[float, float]:
        """
        Compute horizon-aware thresholds: shorter horizons = tighter, longer = wider.

        Uses percentile-based thresholds by default (creates balanced labels).
        Falls back to ATR when percentile fails or use_percentile=False.

        Args:
            df: DataFrame with OHLCV (and optionally 'atr')
            horizon_days: Forecast horizon in days
            atr_multiplier: Multiplier for ATR-based threshold (default 1.0 = 1 ATR)
            use_atr_prefer: Prefer ATR when column exists (used in fallback)
            use_percentile: Use percentile-based thresholds (default True, recommended)

        Returns:
            (bearish_threshold, bullish_threshold)
        """
        horizon_days = max(1, int(horizon_days))

        # Prefer percentile-based (creates balanced labels, avoids 96% neutral)
        if use_percentile:
            try:
                return AdaptiveThresholds.compute_thresholds_percentile(df, horizon_days)
            except Exception as e:
                logger.warning("Percentile threshold failed: %s, falling back to ATR", e)

        # Fallback: ATR-based (original behavior)
        horizon_scale = np.sqrt(float(horizon_days))

        atr_col = "atr" if "atr" in df.columns else ("atr_14" if "atr_14" in df.columns else None)
        if use_atr_prefer and atr_col and len(df) > 0:
            current_price = float(df["close"].iloc[-1])
            current_atr = float(df[atr_col].iloc[-1])
            if current_price > 0 and current_atr > 0:
                atr_pct = current_atr / current_price
                threshold = atr_pct * atr_multiplier * horizon_scale
                bearish_threshold = -threshold
                bullish_threshold = threshold
                logger.info(
                    "Horizon-aware ATR thresholds (%.0fD) - atr_pct=%.2f%% range=[%.4f, %.4f]",
                    horizon_days,
                    atr_pct * 100,
                    bearish_threshold,
                    bullish_threshold,
                )
                return bearish_threshold, bullish_threshold

        # Final fallback: vol-based with horizon scaling
        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds(df)
        bearish_threshold = bearish_thresh * horizon_scale
        bullish_threshold = bullish_thresh * horizon_scale
        logger.info(
            "Horizon-aware vol thresholds (%.0fD) - range=[%.4f, %.4f]",
            horizon_days,
            bearish_threshold,
            bullish_threshold,
        )
        return bearish_threshold, bullish_threshold
