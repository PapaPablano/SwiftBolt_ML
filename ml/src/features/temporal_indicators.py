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
        return float(np.mean(close_prices[idx - window + 1 : idx + 1]))

    @staticmethod
    def compute_ema(close_prices: np.ndarray, window: int, idx: int) -> float:
        """Compute EMA up to index idx (no lookahead)."""
        if idx < window - 1:
            return np.nan

        prices = close_prices[idx - window + 1 : idx + 1]
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

        changes = np.diff(close_prices[idx - window : idx + 1])
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

        ema12 = prices[idx - 12 + 1 : idx + 1].mean()
        for i in range(idx - 11, idx + 1):
            ema12 = prices[i] * (2 / 13) + ema12 * (11 / 13)

        ema26 = prices[idx - 26 + 1 : idx + 1].mean()
        for i in range(idx - 25, idx + 1):
            ema26 = prices[i] * (2 / 27) + ema26 * (25 / 27)

        macd = ema12 - ema26
        return float(macd), float(ema26)

    @staticmethod
    def compute_supertrend_features(
        df: pd.DataFrame,
        idx: int,
        atr_length: int = 10,
        multiplier: float = 2.0,
    ) -> dict:
        """
        Compute SuperTrend features up to idx (no lookahead).

        Uses precomputed SuperTrend AI columns if present in df; otherwise
        falls back to a basic SuperTrend calculation using only history.
        """
        min_required = max(atr_length, 2)
        if idx < min_required:
            return {
                "supertrend_value": np.nan,
                "supertrend_trend": np.nan,
                "supertrend_factor": np.nan,
                "supertrend_performance_index": np.nan,
                "supertrend_signal_strength": np.nan,
                "signal_confidence": np.nan,
                "supertrend_confidence_norm": np.nan,
                "supertrend_distance_norm": np.nan,
                "perf_ama": np.nan,
            }

        # Prefer precomputed AI features if available in df
        if "supertrend_value" in df.columns and "supertrend_trend" in df.columns:
            row = df.iloc[idx]
            value = float(row.get("supertrend_value", np.nan))
            trend = float(row.get("supertrend_trend", np.nan))
            factor = float(row.get("supertrend_factor", multiplier))
            perf_idx = float(row.get("supertrend_performance_index", 0.5))
            strength = float(row.get("supertrend_signal_strength", 5))
            confidence = float(row.get("signal_confidence", 5))
            conf_norm = float(row.get("supertrend_confidence_norm", confidence / 10.0))
            dist_norm = float(row.get("supertrend_distance_norm", np.nan))
            perf_ama = float(row.get("perf_ama", value))

            if pd.isna(dist_norm):
                close_val = float(row.get("close", np.nan))
                if close_val and close_val == close_val:
                    dist_norm = float(abs(close_val - value) / close_val)

            return {
                "supertrend_value": value,
                "supertrend_trend": trend,
                "supertrend_factor": factor,
                "supertrend_performance_index": perf_idx,
                "supertrend_signal_strength": strength,
                "signal_confidence": confidence,
                "supertrend_confidence_norm": conf_norm,
                "supertrend_distance_norm": dist_norm,
                "perf_ama": perf_ama,
            }

        # Fallback: compute a basic SuperTrend using only historical data
        high = df["high"].values[: idx + 1]
        low = df["low"].values[: idx + 1]
        close = df["close"].values[: idx + 1]

        start = max(1, idx - atr_length + 1)
        high_window = high[start : idx + 1]
        low_window = low[start : idx + 1]
        close_window = close[start : idx + 1]

        if start > 0:
            prev_close = np.concatenate([close[start - 1 : start], close_window[:-1]])
        else:
            prev_close = np.concatenate([close_window[:1], close_window[:-1]])

        tr = np.maximum(
            high_window - low_window,
            np.maximum(
                np.abs(high_window - prev_close),
                np.abs(low_window - prev_close),
            ),
        )
        atr = float(np.mean(tr)) if len(tr) else np.nan

        hl2 = (high[-1] + low[-1]) / 2.0
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)

        close_last = close[-1]
        supertrend_value = basic_lower if close_last > basic_upper else basic_upper
        supertrend_trend = 1 if close_last > supertrend_value else 0
        distance_norm = float(abs(close_last - supertrend_value) / close_last) if close_last else np.nan

        return {
            "supertrend_value": float(supertrend_value),
            "supertrend_trend": float(supertrend_trend),
            "supertrend_factor": float(multiplier),
            "supertrend_performance_index": 0.5,
            "supertrend_signal_strength": 5.0,
            "signal_confidence": 5.0,
            "supertrend_confidence_norm": 0.5,
            "supertrend_distance_norm": distance_norm,
            "perf_ama": float(supertrend_value),
        }

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

        # Handle both 'ts' and 'date' column names
        ts_col = point.get("ts") if "ts" in point else point.get("date")
        
        features = {
            "ts": ts_col,
            "close": point["close"],
            "volume": point["volume"],
            "high": point["high"],
            "low": point["low"],
            "sma_5": TemporalFeatureEngineer.compute_sma(close_prices, 5, idx),
            "sma_20": sma_20,
            "sma_50": TemporalFeatureEngineer.compute_sma(close_prices, 50, idx),
            "ema_12": TemporalFeatureEngineer.compute_ema(close_prices, 12, idx),
            "ema_26": TemporalFeatureEngineer.compute_ema(close_prices, 26, idx),
            "rsi_14": TemporalFeatureEngineer.compute_rsi(close_prices, 14, idx),
            "price_vs_sma20": (
                (point["close"] - sma_20) / point["close"] if point["close"] > 0 else 0
            ),
        }

        # Add SuperTrend AI/basic features (temporal-safe)
        supertrend_features = TemporalFeatureEngineer.compute_supertrend_features(df, idx)
        features.update(supertrend_features)

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

    # Convert horizon_days to int for pandas operations
    horizon_days_int = max(1, int(np.ceil(horizon_days)))
    forward_returns = df["close"].pct_change(periods=horizon_days_int).shift(-horizon_days_int)

    for idx in range(50, len(df) - horizon_days_int):
        features = engineer.add_features_to_point(df, idx, lookback=50)
        actual_return = forward_returns.iloc[idx]

        if pd.notna(actual_return):
            X_list.append(features)
            label = (
                "bullish"
                if actual_return > 0.02
                else "bearish" if actual_return < -0.02 else "neutral"
            )
            y_list.append(label)

    logger.info("Prepared %s temporal samples (no lookahead)", len(X_list))

    return pd.DataFrame(X_list), pd.Series(y_list)
