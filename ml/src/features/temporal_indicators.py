"""
Temporal-aware feature engineering to prevent lookahead bias.
Computes features bar-by-bar ensuring no forward-looking information.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TemporalFeatureEngineer:
    """Compute features bar-by-bar with no lookahead bias."""

    @staticmethod
    def compute_sma(close_prices: np.ndarray, window: int, idx: int) -> float:
        """Compute SMA up to index idx (no lookahead)."""
        if idx < window - 1:
            return np.nan
        return float(
            np.mean(close_prices[idx - window + 1: idx + 1])
        )

    @staticmethod
    def compute_ema(close_prices: np.ndarray, window: int, idx: int) -> float:
        """Compute EMA up to index idx (no lookahead)."""
        if idx < window - 1:
            return np.nan

        prices = close_prices[idx - window + 1: idx + 1]
        ema = prices[0]
        multiplier = 2 / (window + 1)

        for price in prices[1:]:
            ema = price * multiplier + ema * (1 - multiplier)

        return float(ema)

    @staticmethod
    def compute_rsi(close_prices: np.ndarray, window: int, idx: int) -> float:
        """RSI with no lookahead."""
        if idx < window:
            return np.nan

        changes = np.diff(close_prices[idx - window: idx + 1])
        gains = np.sum(np.maximum(changes, 0))
        losses = np.sum(np.maximum(-changes, 0))

        if losses == 0:
            return 100.0 if gains > 0 else 0.0

        rs = gains / losses
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def compute_macd(
        close_prices: np.ndarray,
        idx: int,
    ) -> Tuple[float, float]:
        """MACD with no lookahead."""
        if idx < 26:
            return np.nan, np.nan

        prices = close_prices[: idx + 1]

        ema12 = prices[idx - 12 + 1: idx + 1].mean()
        for i in range(idx - 11, idx + 1):
            ema12 = prices[i] * (2 / 13) + ema12 * (11 / 13)

        ema26 = prices[idx - 26 + 1: idx + 1].mean()
        for i in range(idx - 25, idx + 1):
            ema26 = prices[i] * (2 / 27) + ema26 * (25 / 27)

        macd = ema12 - ema26
        return float(macd), float(ema26)

    @staticmethod
    def add_features_to_point(
        df: pd.DataFrame,
        idx: int,
        lookback: int = 50,
    ) -> dict:
        """
        Add features for point at idx using only data up to idx.

        Args:
            df: Full dataframe
            idx: Index of current point
            lookback: How many bars back to use

        Returns:
            Dict of features
        """
        _ = lookback  # reserved for future use

        point = df.iloc[idx]
        close_prices = df["close"].values[: idx + 1]
        high_prices = df["high"].values[: idx + 1]
        low_prices = df["low"].values[: idx + 1]
        _ = (high_prices, low_prices)  # placeholders for future features
        volume_data = df["volume"].values[: idx + 1]
        _ = volume_data

        sma_20 = TemporalFeatureEngineer.compute_sma(close_prices, 20, idx)

        features = {
            "ts": point["ts"],
            "close": point["close"],
            "volume": point["volume"],
            "high": point["high"],
            "low": point["low"],
            "sma_5": TemporalFeatureEngineer.compute_sma(
                close_prices, 5, idx
            ),
            "sma_20": sma_20,
            "sma_50": TemporalFeatureEngineer.compute_sma(
                close_prices, 50, idx
            ),
            "ema_12": TemporalFeatureEngineer.compute_ema(
                close_prices, 12, idx
            ),
            "ema_26": TemporalFeatureEngineer.compute_ema(
                close_prices, 26, idx
            ),
            "rsi_14": TemporalFeatureEngineer.compute_rsi(
                close_prices, 14, idx
            ),
            "price_vs_sma20": (
                (point["close"] - sma_20) / point["close"]
                if point["close"] > 0
                else 0
            ),
        }

        return features


def prepare_training_data_temporal(
    df: pd.DataFrame,
    horizon_days: int = 1,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepare training data with NO lookahead bias.

    Features are computed bar-by-bar using only historical data.
    """
    engineer = TemporalFeatureEngineer()

    X_list: list[dict] = []
    y_list: list[str] = []

    forward_returns = df["close"].pct_change(periods=horizon_days).shift(-horizon_days)

    for idx in range(50, len(df) - horizon_days):
        features = engineer.add_features_to_point(df, idx, lookback=50)
        actual_return = forward_returns.iloc[idx]

        if pd.notna(actual_return):
            X_list.append(features)
            label = (
                "bullish"
                if actual_return > 0.02
                else "bearish"
                if actual_return < -0.02
                else "neutral"
            )
            y_list.append(label)

    logger.info("Prepared %s temporal samples (no lookahead)", len(X_list))

    return pd.DataFrame(X_list), pd.Series(y_list)
