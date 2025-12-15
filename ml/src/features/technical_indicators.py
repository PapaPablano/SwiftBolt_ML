"""Technical indicator calculations for feature engineering."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators as features to OHLC DataFrame.

    Args:
        df: DataFrame with columns [ts, open, high, low, close, volume]

    Returns:
        DataFrame with additional technical indicator columns
    """
    df = df.copy()

    # Returns
    df["returns_1d"] = df["close"].pct_change()
    df["returns_5d"] = df["close"].pct_change(periods=5)
    df["returns_20d"] = df["close"].pct_change(periods=20)

    # Moving Averages
    df["sma_5"] = df["close"].rolling(window=5).mean()
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["sma_50"] = df["close"].rolling(window=50).mean()

    # Exponential Moving Averages
    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()

    # MACD
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # RSI
    df["rsi_14"] = calculate_rsi(df["close"], period=14)

    # Bollinger Bands
    bb_period = 20
    bb_std = 2
    df["bb_middle"] = df["close"].rolling(window=bb_period).mean()
    rolling_std = df["close"].rolling(window=bb_period).std()
    df["bb_upper"] = df["bb_middle"] + (rolling_std * bb_std)
    df["bb_lower"] = df["bb_middle"] - (rolling_std * bb_std)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

    # Volume indicators
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    # Volatility
    df["volatility_20d"] = df["returns_1d"].rolling(window=20).std()

    # Price position relative to range
    df["price_vs_sma20"] = (df["close"] - df["sma_20"]) / df["sma_20"]
    df["price_vs_sma50"] = (df["close"] - df["sma_50"]) / df["sma_50"]

    # Average True Range (ATR)
    df["atr_14"] = calculate_atr(df, period=14)

    logger.info(f"Added {len(df.columns) - 6} technical indicators")

    return df


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.

    Args:
        series: Price series
        period: RSI period (default: 14)

    Returns:
        RSI values (0-100)
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.

    Args:
        df: DataFrame with high, low, close columns
        period: ATR period (default: 14)

    Returns:
        ATR values
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def prepare_features_for_ml(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare features for ML model by selecting relevant columns and handling NaNs.

    Args:
        df: DataFrame with technical indicators

    Returns:
        Clean DataFrame ready for ML training
    """
    # Select feature columns (exclude raw OHLCV and timestamp)
    feature_cols = [
        col
        for col in df.columns
        if col
        not in [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    # Create features DataFrame
    features_df = df[["ts", "close"] + feature_cols].copy()

    # Drop rows with NaN (typically from rolling window initialization)
    features_df = features_df.dropna()

    logger.info(f"Prepared {len(features_df)} samples with {len(feature_cols)} features")

    return features_df
