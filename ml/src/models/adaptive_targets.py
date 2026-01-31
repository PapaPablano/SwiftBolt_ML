"""
Adaptive classification targets for ensemble models.

Creates direction labels (bearish/neutral/bullish) using horizon- and
volatility-aware thresholds (ATR × sqrt(horizon)), so that:
- 1D with 2% ATR → ±2%
- 5D with 2% ATR → ±4.5%
- 20D with 2% ATR → ±9%

Use when training or evaluating classifiers so small moves are not
all classified as neutral at longer horizons.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd

from src.features.adaptive_thresholds import AdaptiveThresholds

logger = logging.getLogger(__name__)


def create_adaptive_targets(
    df: pd.DataFrame,
    horizon_days: int = 1,
    atr_multiplier: float = 1.0,
    use_atr_prefer: bool = True,
) -> Tuple[pd.Series, float, float]:
    """
    Create direction labels with adaptive thresholds.

    Thresholds scale with horizon (sqrt) and volatility (ATR or rolling vol),
    so longer horizons and higher volatility get wider bands.

    Args:
        df: OHLC DataFrame with 'close' (and optionally 'atr' or 'atr_14').
        horizon_days: Forecast horizon in days (1, 5, 10, 20).
        atr_multiplier: Sensitivity (default 1.0 = 1 ATR).
        use_atr_prefer: Prefer ATR when column exists.

    Returns:
        (labels_series, bearish_threshold, bullish_threshold)
        - labels_series: pd.Series with "bearish" | "neutral" | "bullish", index aligned to df.
        - bearish_threshold: Return below this = bearish.
        - bullish_threshold: Return above this = bullish.
    """
    horizon_days = max(1, int(horizon_days))

    if "close" not in df.columns:
        raise ValueError("create_adaptive_targets requires df with 'close' column")

    # Forward returns
    fwd_return = df["close"].pct_change(periods=horizon_days).shift(-horizon_days)

    # Horizon- and ATR-aware thresholds
    bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
        df,
        horizon_days=horizon_days,
        atr_multiplier=atr_multiplier,
        use_atr_prefer=use_atr_prefer,
    )

    # Classify
    labels = pd.Series("neutral", index=df.index, dtype=object)
    labels.loc[fwd_return < bearish_thresh] = "bearish"
    labels.loc[fwd_return > bullish_thresh] = "bullish"

    # Drop rows with NaN forward return (last horizon_days rows)
    valid = fwd_return.notna()
    labels = labels[valid]

    logger.info(
        "Adaptive targets (%.0fD): bearish<%.2f%%, bullish>%.2f%% → %s",
        horizon_days,
        bearish_thresh * 100,
        bullish_thresh * 100,
        labels.value_counts().to_dict(),
    )

    return labels, bearish_thresh, bullish_thresh
