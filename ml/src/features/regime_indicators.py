"""
Regime Indicators: Market State Features
========================================

Compute features that capture market regime (low vol, normal, high vol).
These features help models understand "what kind of market are we in?"
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegimeIndicators:
    """
    Compute regime-aware features for stock forecasting.

    Features:
    1. realized_volatility: Rolling standard deviation of returns
    2. volatility_regime: Classify market into Low/Normal/High vol
    3. volatility_of_volatility: How fast is vol changing?
    4. vol_percentile: Percentile of current vol vs historical
    5. vol_trend: Is vol increasing or decreasing?
    """

    @staticmethod
    def realized_volatility(ohlc_df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """
        Compute realized volatility: std of close-to-close returns.

        Args:
            ohlc_df: DataFrame with 'close' column
            lookback: Window size (default 20 days)

        Returns:
            Series with realized volatility for each bar
        """
        if "close" not in ohlc_df.columns:
            raise ValueError("DataFrame must have 'close' column")

        returns = ohlc_df["close"].pct_change()
        realized_vol = returns.rolling(window=lookback).std() * np.sqrt(252)  # Annualized

        return realized_vol

    @staticmethod
    def volatility_regime(realized_vol_series: pd.Series) -> pd.Series:
        """
        Classify volatility regime into Low/Normal/High.

        Uses percentiles:
        - Low: < 33rd percentile
        - Normal: 33rd to 67th percentile
        - High: > 67th percentile

        Args:
            realized_vol_series: Series of realized volatility

        Returns:
            Series with regime classification {0: Low, 1: Normal, 2: High}
        """
        p33 = realized_vol_series.quantile(0.33)
        p67 = realized_vol_series.quantile(0.67)

        regime = pd.Series(index=realized_vol_series.index, dtype=float)
        regime[realized_vol_series < p33] = 0  # Low vol
        regime[(realized_vol_series >= p33) & (realized_vol_series <= p67)] = 1  # Normal
        regime[realized_vol_series > p67] = 2  # High vol

        # Keep NaN values as NaN (use nullable integer type)
        return regime.astype("Int64")

    @staticmethod
    def volatility_of_volatility(
        realized_vol_series: pd.Series, lookback: int = 10
    ) -> pd.Series:
        """
        Compute vol of vol: standard deviation of realized volatility.

        High vol-of-vol = volatility is changing rapidly = uncertain market
        Low vol-of-vol = volatility is stable = predictable market

        Args:
            realized_vol_series: Series of realized volatility
            lookback: Window size (default 10 bars)

        Returns:
            Series with vol-of-vol for each bar
        """
        vol_of_vol = realized_vol_series.rolling(window=lookback).std()
        return vol_of_vol

    @staticmethod
    def volatility_percentile(
        realized_vol_series: pd.Series, lookback: int = 252
    ) -> pd.Series:
        """
        Compute percentile rank of current vol vs historical.

        Range: 0-100
        - 0%: Vol is at lowest levels (historically)
        - 50%: Vol is median
        - 100%: Vol is at highest levels (historically)

        Args:
            realized_vol_series: Series of realized volatility
            lookback: Historical window (default 252 = 1 year)

        Returns:
            Series with vol percentile (0-100) for each bar
        """

        def compute_percentile(window: np.ndarray) -> float:
            if pd.isna(window[-1]):
                return np.nan
            return (window < window[-1]).sum() / len(window) * 100

        # Use smaller window for small datasets
        effective_lookback = min(lookback, max(20, len(realized_vol_series) // 2))
        vol_pct = realized_vol_series.rolling(window=effective_lookback).apply(
            compute_percentile, raw=True
        )
        return vol_pct

    @staticmethod
    def volatility_trend(realized_vol_series: pd.Series, lookback: int = 20) -> pd.Series:
        """
        Compute vol trend: is volatility increasing or decreasing?

        Returns:
        - Positive values: Vol is increasing (warning signal)
        - Negative values: Vol is decreasing (stabilizing)
        - Near 0: Vol is stable

        Args:
            realized_vol_series: Series of realized volatility
            lookback: Window for trend calculation

        Returns:
            Series with vol trend (slope of vol over time)
        """
        vol_trend = realized_vol_series.diff(lookback)
        return vol_trend

    @staticmethod
    def add_all_regime_features(ohlc_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all regime indicators to OHLC DataFrame.

        Args:
            ohlc_df: DataFrame with OHLC data

        Returns:
            DataFrame with added regime columns:
            - realized_vol_20d
            - volatility_regime
            - vol_of_vol
            - vol_percentile
            - vol_trend
        """
        df = ohlc_df.copy()

        # Compute realized volatility
        df["realized_vol_20d"] = RegimeIndicators.realized_volatility(df, lookback=20)

        # Volatility regime
        df["volatility_regime"] = RegimeIndicators.volatility_regime(df["realized_vol_20d"])

        # Vol of vol
        df["vol_of_vol"] = RegimeIndicators.volatility_of_volatility(
            df["realized_vol_20d"], lookback=10
        )

        # Vol percentile
        df["vol_percentile"] = RegimeIndicators.volatility_percentile(
            df["realized_vol_20d"], lookback=252
        )

        # Vol trend
        df["vol_trend"] = RegimeIndicators.volatility_trend(
            df["realized_vol_20d"], lookback=20
        )

        logger.info(f"Added 5 regime indicators. Shape: {df.shape}")

        return df


def add_regime_features_to_technical(
    features_df: pd.DataFrame, ohlc_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Add regime features to existing technical indicator DataFrame.

    Args:
        features_df: DataFrame with existing technical indicators (20 features)
        ohlc_df: Original OHLC DataFrame

    Returns:
        DataFrame with regime features added (20 + 5 = 25 features)
    """
    regime_df = RegimeIndicators.add_all_regime_features(ohlc_df)

    # Extract regime columns
    regime_cols = [
        "realized_vol_20d",
        "volatility_regime",
        "vol_of_vol",
        "vol_percentile",
        "vol_trend",
    ]

    for col in regime_cols:
        if col in regime_df.columns:
            features_df[col] = regime_df[col].values

    return features_df


if __name__ == "__main__":
    print("RegimeIndicators imported successfully")
