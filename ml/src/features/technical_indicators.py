"""Technical indicator calculations for feature engineering.

UPDATED: 2025-12-24
This module now uses CORRECTED indicator implementations from
technical_indicators_corrected.py with proper:
- ADX: Wilder's smoothing (not rolling mean)
- KDJ: Exponential smoothing (2/3 weight on prior)
- SuperTrend: Full implementation (was missing!)
- ATR: For normalization only, not directional signal
"""

import logging

import numpy as np
import pandas as pd

from src.features.market_regime import add_market_regime_features
from src.features.regime_indicators import add_regime_features_to_technical
from src.features.volatility_regime import add_garch_features
from src.features.technical_indicators_corrected import TechnicalIndicatorsCorrect
from src.features.support_resistance_detector import add_support_resistance_features

logger = logging.getLogger(__name__)


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators as features to OHLC DataFrame.

    UPDATED: Now uses corrected indicator implementations.

    Args:
        df: DataFrame with columns [ts, open, high, low, close, volume]

    Returns:
        DataFrame with additional technical indicator columns
    """
    # Handle empty dataframe edge case
    if len(df) == 0:
        return df.copy()

    df = df.copy()

    # Returns
    df["returns_1d"] = df["close"].pct_change()
    df["returns_5d"] = df["close"].pct_change(periods=5)
    df["returns_20d"] = df["close"].pct_change(periods=20)

    # =========================================================================
    # CORRECTED INDICATORS (from technical_indicators_corrected.py)
    # =========================================================================

    # Moving Averages
    df = TechnicalIndicatorsCorrect.add_moving_averages(df)

    # MACD (standard implementation)
    df["macd"], df["macd_signal"], df["macd_hist"] = TechnicalIndicatorsCorrect.calculate_macd(
        df["close"], fast=12, slow=26, signal=9
    )

    # RSI (using proper EMA smoothing)
    df["rsi_14"] = TechnicalIndicatorsCorrect.calculate_rsi(df["close"], period=14)

    # Bollinger Bands (with width percentile for regime detection)
    df = TechnicalIndicatorsCorrect.calculate_bollinger_bands(df, period=20, std_dev=2.0)

    # ADX (CRITICAL FIX: Wilder's smoothing, not rolling mean)
    # TRADINGVIEW-VALIDATED: period=14
    df = TechnicalIndicatorsCorrect.calculate_adx_correct(df, period=14)

    # KDJ (CRITICAL FIX: Exponential smoothing, not SMA)
    # TRADINGVIEW-VALIDATED: period=9, k_smooth=5, d_smooth=5 (EMA smoothing)
    df = TechnicalIndicatorsCorrect.calculate_kdj_correct(df, period=9, k_smooth=5, d_smooth=5)

    # SuperTrend (WAS MISSING - now implemented with 20% weight)
    # TRADINGVIEW-VALIDATED: period=7, multiplier=2.0
    df = TechnicalIndicatorsCorrect.calculate_supertrend(df, period=7, multiplier=2.0)

    # ATR (for normalization only, NOT as directional signal)
    df["atr_14"] = TechnicalIndicatorsCorrect.calculate_atr(df, period=14)
    df["atr_normalized"] = df["atr_14"] / df["close"] * 100

    # Volume indicators
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    # MFI (volume-weighted RSI)
    df["mfi_14"] = TechnicalIndicatorsCorrect.calculate_mfi(df, period=14)
    df["mfi"] = df["mfi_14"]  # Alias for backward compatibility

    # OBV
    df["obv"] = TechnicalIndicatorsCorrect.calculate_obv(df)
    df["obv_sma"] = df["obv"].rolling(window=20).mean()

    # Volatility (annualized)
    df["volatility_20d"] = df["returns_1d"].rolling(window=20).std() * np.sqrt(252)

    # Price position relative to range
    df["price_vs_sma20"] = (df["close"] - df["sma_20"]) / df["sma_20"]
    df["price_vs_sma50"] = (df["close"] - df["sma_50"]) / df["sma_50"]

    # =========================================================================
    # REGIME FEATURES (HMM + GARCH)
    # =========================================================================

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

    # =========================================================================
    # SUPPORT/RESISTANCE FEATURES
    # =========================================================================

    # Add S/R features (5 additional indicators for ML)
    try:
        df = add_support_resistance_features(df)

        # Add volume-based S/R strength features (Phase 1: 6 additional features)
        from src.features.support_resistance_detector import SupportResistanceDetector

        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        df = sr_detector.add_volume_strength_features(df, sr_levels)

        # Add polynomial S/R features (Phase 3: 4 additional features)
        from src.features.sr_polynomial import SRPolynomialRegressor

        poly_regressor = SRPolynomialRegressor(degree=2, min_points=4)
        df = poly_regressor.add_polynomial_features(df, sr_levels)

        logger.info("Added S/R features with volume strength + polynomial")
    except Exception as exc:  # noqa: BLE001
        logger.warning("S/R features failed: %s", exc)

    logger.info(
        "Added %s technical indicators (CORRECTED implementations + S/R)",
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


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
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
    df["keltner_middle"] = (
        df["close"]
        .ewm(
            span=ema_period,
            adjust=False,
        )
        .mean()
    )

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

    UPDATED: Now uses CORRECTED implementations from technical_indicators_corrected.py.

    This function adds all available indicators including:
    - Basic indicators (returns, MAs, MACD, RSI, BB, ATR)
    - Momentum indicators (Stochastic, KDJ, ADX) - CORRECTED
    - SuperTrend - NEW (was missing!)
    - Volume indicators (OBV, MFI, VROC)
    - Volatility indicators (Keltner Channel)

    Args:
        df: DataFrame with columns [ts, open, high, low, close, volume]

    Returns:
        DataFrame with all technical indicator columns added
    """
    # Use the corrected add_technical_features which now includes:
    # - ADX with Wilder's smoothing
    # - KDJ with exponential smoothing
    # - SuperTrend (was completely missing)
    # - ATR for normalization only
    df = add_technical_features(df)

    # Add additional volume indicators (legacy for compatibility)
    df = calculate_vroc(df)

    # Add volatility indicators (legacy for compatibility)
    df = calculate_keltner_channel(df)

    logger.info(
        "Added all technical indicators (CORRECTED): %s features total",
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
