"""
Simplified regime features using only OHLCV data.
No external APIs needed - works offline.
"""

import numpy as np
import pandas as pd


def add_trend_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify price trend regime using moving averages.
    Expects 'close'; uses sma_50/sma_200 if present (from TechnicalIndicatorsCorrect), else computes.
    """
    df = df.copy()
    if "sma_50" not in df.columns or "sma_200" not in df.columns:
        df["sma_50"] = df["close"].rolling(50, min_periods=1).mean()
        df["sma_200"] = df["close"].rolling(200, min_periods=1).mean()
    sma_200 = df["sma_200"].replace(0, np.nan)
    df["distance_from_200ma"] = (df["close"] / sma_200 - 1)
    # 0 = bearish (>5% below), 1 = sideways, 2 = bullish (>5% above)
    d = df["distance_from_200ma"]
    df["trend_regime"] = np.select([d < -0.05, d > 0.05], [0, 2], default=1)
    df["trend_strength"] = d.abs()
    return df


def add_momentum_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify momentum regime using ADX.
    Expects 'adx' from TechnicalIndicatorsCorrect; computes if missing (simplified).
    """
    df = df.copy()
    if "adx" not in df.columns:
        # Minimal ADX proxy: volatility of returns over 14 days
        ret = df["close"].pct_change()
        df["adx"] = ret.rolling(14).std().abs() * 100
    df["adx_14"] = df["adx"]
    # 0 = weak (ADX < 20), 1 = moderate (20–40), 2 = strong (>40)
    adx = df["adx_14"]
    df["momentum_regime"] = np.select([adx < 20, adx < 40], [0, 1], default=2)
    return df


def add_all_simple_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all simple regime features (trend + momentum) using only OHLCV.
    Volatility features are added by compute_simplified_features(add_volatility=True).
    """
    df = add_trend_regime(df)
    df = add_momentum_regime(df)
    return df


def add_simple_regime_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Fill simple regime columns with neutral defaults when not using simple regime."""
    df = df.copy()
    n = len(df)
    if "distance_from_200ma" not in df.columns:
        df["distance_from_200ma"] = 0.0
    if "trend_regime" not in df.columns:
        df["trend_regime"] = 1
    if "trend_strength" not in df.columns:
        df["trend_strength"] = 0.0
    if "adx_14" not in df.columns:
        df["adx_14"] = 20.0
    if "momentum_regime" not in df.columns:
        df["momentum_regime"] = 1
    return df


SIMPLE_REGIME_FEATURES = [
    "distance_from_200ma",
    "trend_regime",
    "trend_strength",
    "adx_14",
    "momentum_regime",
]
