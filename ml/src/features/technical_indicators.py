"""Technical indicator calculations for feature engineering."""

import logging

import numpy as np
import pandas as pd

from src.features.market_regime import add_market_regime_features
from src.features.regime_indicators import add_regime_features_to_technical
from src.features.volatility_regime import add_garch_features

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

    # Add regime features (5 additional indicators)
    df = add_regime_features_to_technical(df, df)

    # Add HMM market regimes (discrete + probabilities)
    try:
        df = add_market_regime_features(df)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Market regime features failed: %s", exc)

    # Add GARCH variance/regime
    try:
        df = add_garch_features(df)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GARCH features failed: %s", exc)

    logger.info(
        "Added %s technical indicators (including regime features)",
        len(df.columns) - 6,
    )

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


# ============================================================================
# MOMENTUM INDICATORS
# ============================================================================


def calculate_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator (%K and %D).

    %K = 100 * (Close - Lowest Low) / (Highest High - Lowest Low)
    %D = SMA of %K

    Args:
        df: DataFrame with high, low, close columns
        k_period: Lookback period for %K (default: 14)
        d_period: Smoothing period for %D (default: 3)

    Returns:
        DataFrame with stoch_k and stoch_d columns added
    """
    df = df.copy()

    lowest_low = df["low"].rolling(window=k_period).min()
    highest_high = df["high"].rolling(window=k_period).max()

    # Handle division by zero
    range_hl = highest_high - lowest_low
    range_hl = range_hl.replace(0, np.nan)

    df["stoch_k"] = 100 * (df["close"] - lowest_low) / range_hl
    df["stoch_d"] = df["stoch_k"].rolling(window=d_period).mean()

    return df


def calculate_kdj(
    df: pd.DataFrame, period: int = 9, k_smooth: int = 3, d_smooth: int = 3
) -> pd.DataFrame:
    """
    Calculate KDJ Indicator with J line for early reversal detection.

    RSV = 100 * (Close - Lowest Low) / (Highest High - Lowest Low)
    K = SMA(RSV, k_smooth)
    D = SMA(K, d_smooth)
    J = 3*K - 2*D (more sensitive than K or D alone)

    Args:
        df: DataFrame with high, low, close columns
        period: Lookback period for RSV (default: 9)
        k_smooth: Smoothing period for K (default: 3)
        d_smooth: Smoothing period for D (default: 3)

    Returns:
        DataFrame with kdj_k, kdj_d, kdj_j, kdj_j_minus_d columns added
    """
    df = df.copy()

    lowest_low = df["low"].rolling(window=period).min()
    highest_high = df["high"].rolling(window=period).max()

    # Handle division by zero
    range_hl = highest_high - lowest_low
    range_hl = range_hl.replace(0, np.nan)

    rsv = 100 * (df["close"] - lowest_low) / range_hl

    df["kdj_k"] = rsv.rolling(window=k_smooth).mean()
    df["kdj_d"] = df["kdj_k"].rolling(window=d_smooth).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]
    df["kdj_j_minus_d"] = df["kdj_j"] - df["kdj_d"]  # Divergence signal

    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index for trend strength.

    ADX measures trend strength (0-100), not direction.
    +DI/-DI indicate direction.

    ADX < 20: Weak/No trend
    ADX 20-40: Moderate trend
    ADX > 40: Strong trend

    Args:
        df: DataFrame with high, low, close columns
        period: Smoothing period (default: 14)

    Returns:
        DataFrame with adx, plus_di, minus_di columns added
    """
    df = df.copy()

    high = df["high"]
    low = df["low"]
    close = df["close"]

    # +DM and -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()

    # Apply conditions
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smoothed averages (Wilder's smoothing = EMA with span=period)
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(span=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(span=period, adjust=False).mean()

    # +DI and -DI
    df["plus_di"] = 100 * (plus_dm_smooth / atr)
    df["minus_di"] = 100 * (minus_dm_smooth / atr)

    # DX and ADX
    di_sum = df["plus_di"] + df["minus_di"]
    di_sum = di_sum.replace(0, np.nan)
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / di_sum
    df["adx"] = dx.rolling(window=period).mean()

    return df


# ============================================================================
# VOLUME INDICATORS
# ============================================================================


def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate On-Balance Volume (OBV).

    OBV is a cumulative indicator that adds volume on up days
    and subtracts volume on down days.

    Args:
        df: DataFrame with close and volume columns

    Returns:
        DataFrame with obv and obv_sma columns added
    """
    df = df.copy()

    # Direction of price change
    direction = np.sign(df["close"].diff())

    # OBV calculation
    obv = (direction * df["volume"]).cumsum()
    df["obv"] = obv
    df["obv_sma"] = df["obv"].rolling(window=20).mean()

    return df


def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Money Flow Index (MFI) - volume-weighted RSI.

    MFI combines price and volume to identify overbought/oversold.
    MFI < 20: Oversold
    MFI > 80: Overbought

    Args:
        df: DataFrame with high, low, close, volume columns
        period: Lookback period (default: 14)

    Returns:
        DataFrame with mfi column added
    """
    df = df.copy()

    # Typical Price
    typical_price = (df["high"] + df["low"] + df["close"]) / 3

    # Raw Money Flow
    money_flow = typical_price * df["volume"]

    # Positive and Negative Money Flow
    price_change = typical_price.diff()
    positive_flow = money_flow.where(price_change > 0, 0)
    negative_flow = money_flow.where(price_change < 0, 0)

    # Sum over period
    positive_mf = positive_flow.rolling(window=period).sum()
    negative_mf = negative_flow.rolling(window=period).sum()

    # Money Flow Ratio and MFI
    negative_mf = negative_mf.replace(0, np.nan)
    money_ratio = positive_mf / negative_mf
    df["mfi"] = 100 - (100 / (1 + money_ratio))

    return df


def calculate_vroc(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Volume Rate of Change (VROC).

    VROC measures the percentage change in volume over a period.

    Args:
        df: DataFrame with volume column
        period: Lookback period (default: 14)

    Returns:
        DataFrame with vroc column added
    """
    df = df.copy()

    prev_volume = df["volume"].shift(period)
    prev_volume = prev_volume.replace(0, np.nan)

    df["vroc"] = ((df["volume"] - prev_volume) / prev_volume) * 100

    return df


# ============================================================================
# VOLATILITY INDICATORS
# ============================================================================


def calculate_keltner_channel(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> pd.DataFrame:
    """
    Calculate Keltner Channel (EMA-based volatility bands).

    Keltner Channels use ATR instead of standard deviation (like Bollinger).
    Useful for trend-following and breakout strategies.

    Args:
        df: DataFrame with high, low, close columns
        ema_period: Period for center EMA (default: 20)
        atr_period: Period for ATR calculation (default: 10)
        multiplier: ATR multiplier for bands (default: 2.0)

    Returns:
        DataFrame with keltner_middle, keltner_upper, keltner_lower
        columns added
    """
    df = df.copy()

    # Center line (EMA)
    df["keltner_middle"] = df["close"].ewm(
        span=ema_period,
        adjust=False,
    ).mean()

    # ATR for channel width
    atr = calculate_atr(df, period=atr_period)

    # Bands
    df["keltner_upper"] = df["keltner_middle"] + (atr * multiplier)
    df["keltner_lower"] = df["keltner_middle"] - (atr * multiplier)

    return df


# ============================================================================
# COMPOSITE FEATURE FUNCTIONS
# ============================================================================


def add_all_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add comprehensive technical indicators for ML training.

    This function adds all available indicators including:
    - Basic indicators (returns, MAs, MACD, RSI, BB, ATR)
    - Momentum indicators (Stochastic, KDJ, ADX)
    - Volume indicators (OBV, MFI, VROC)
    - Volatility indicators (Keltner Channel)

    Args:
        df: DataFrame with columns [ts, open, high, low, close, volume]

    Returns:
        DataFrame with all technical indicator columns added
    """
    # Start with basic indicators
    df = add_technical_features(df)

    # Add momentum indicators
    df = calculate_stochastic(df)
    df = calculate_kdj(df)
    df = calculate_adx(df)

    # Add volume indicators
    df = calculate_obv(df)
    df = calculate_mfi(df)
    df = calculate_vroc(df)

    # Add volatility indicators
    df = calculate_keltner_channel(df)

    logger.info(
        "Added all technical indicators: %s features total",
        len(df.columns) - 6,
    )

    return df


def prepare_features_for_ml(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare features for ML model by selecting relevant columns and
    handling NaNs.

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

    logger.info(
        "Prepared %s samples with %s features",
        len(features_df),
        len(feature_cols),
    )

    return features_df
