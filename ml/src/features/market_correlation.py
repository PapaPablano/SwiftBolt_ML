"""
Market Correlation Features
===========================

Implements SPY correlation features from STOCK_FORECASTING_FRAMEWORK.md:
- Rolling correlation to SPY (market benchmark)
- Relative strength vs market
- Beta calculation (systematic risk)
- Market-relative momentum

These features provide crucial context:
- High SPY correlation = moves with market
- Low SPY correlation = idiosyncratic/sector-specific moves
- Beta > 1 = amplifies market moves
- Relative strength = outperforming/underperforming market
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketCorrelationFeatures:
    """
    Calculate market correlation features for a given symbol.

    Features are computed relative to SPY (S&P 500 ETF) as the market benchmark.
    """

    def __init__(
        self,
        spy_data: Optional[pd.DataFrame] = None,
        correlation_windows: list = [20, 60, 120],
    ):
        """
        Initialize with SPY benchmark data.

        Args:
            spy_data: DataFrame with SPY OHLC data (ts, close required)
            correlation_windows: Windows for rolling correlation [short, medium, long]
        """
        self.spy_data = spy_data
        self.correlation_windows = correlation_windows
        self.spy_returns: Optional[pd.Series] = None

        if spy_data is not None:
            self._prepare_spy_returns()

    def _prepare_spy_returns(self) -> None:
        """Prepare SPY returns series with timestamp index."""
        if self.spy_data is None:
            return

        df = self.spy_data.copy()

        # Ensure timestamp index
        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.set_index("ts")

        # Calculate returns
        self.spy_returns = df["close"].pct_change()
        self.spy_close = df["close"]

        logger.info("Prepared SPY returns: %d observations", len(self.spy_returns))

    def set_spy_data(self, spy_data: pd.DataFrame) -> None:
        """Set or update SPY benchmark data."""
        self.spy_data = spy_data
        self._prepare_spy_returns()

    def calculate_features(
        self,
        df: pd.DataFrame,
        include_all: bool = True,
    ) -> pd.DataFrame:
        """
        Calculate all market correlation features.

        Args:
            df: Symbol DataFrame with ts, close columns
            include_all: Include all feature types (correlation, beta, RS)

        Returns:
            DataFrame with correlation features added
        """
        df = df.copy()

        if self.spy_returns is None:
            logger.warning("SPY data not set. Adding placeholder features.")
            return self._add_placeholder_features(df)

        # Prepare symbol returns
        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"])

        symbol_returns = df["close"].pct_change()

        # Align data by timestamp
        if "ts" in df.columns:
            df_aligned = self._align_with_spy(df, symbol_returns)
        else:
            df_aligned = df
            df_aligned["symbol_returns"] = symbol_returns
            df_aligned["spy_returns"] = self.spy_returns.reindex(df.index).values

        # Calculate features
        if include_all:
            df_aligned = self._add_correlation_features(df_aligned)
            df_aligned = self._add_beta_features(df_aligned)
            df_aligned = self._add_relative_strength_features(df_aligned)
            df_aligned = self._add_momentum_spread_features(df_aligned)

        # Drop intermediate columns
        cols_to_drop = ["symbol_returns", "spy_returns", "spy_close_aligned"]
        for col in cols_to_drop:
            if col in df_aligned.columns:
                df_aligned = df_aligned.drop(columns=[col])

        logger.info("Added %d market correlation features",
                   len([c for c in df_aligned.columns if c.startswith("spy_") or c.startswith("market_")]))

        return df_aligned

    def _align_with_spy(
        self,
        df: pd.DataFrame,
        symbol_returns: pd.Series,
    ) -> pd.DataFrame:
        """Align symbol data with SPY by timestamp."""
        df_aligned = df.copy()
        df_aligned["symbol_returns"] = symbol_returns

        # Create alignment mapping
        spy_returns_map = self.spy_returns.to_dict()
        spy_close_map = self.spy_close.to_dict() if hasattr(self, "spy_close") else {}

        # Map SPY data to symbol timestamps
        df_aligned["spy_returns"] = df_aligned["ts"].map(
            lambda x: spy_returns_map.get(pd.Timestamp(x), np.nan)
        )
        df_aligned["spy_close_aligned"] = df_aligned["ts"].map(
            lambda x: spy_close_map.get(pd.Timestamp(x), np.nan)
        )

        return df_aligned

    def _add_correlation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add rolling correlation to SPY.

        Features:
        - spy_correlation_20d: Short-term correlation (recent relationship)
        - spy_correlation_60d: Medium-term correlation (quarterly)
        - spy_correlation_120d: Long-term correlation (semi-annual)
        """
        symbol_returns = df["symbol_returns"]
        spy_returns = df["spy_returns"]

        for window in self.correlation_windows:
            col_name = f"spy_correlation_{window}d"
            df[col_name] = symbol_returns.rolling(window).corr(spy_returns)

            # Fill NaNs with 0 (uncorrelated assumption)
            df[col_name] = df[col_name].fillna(0)

        # Correlation change (trend in correlation)
        if len(self.correlation_windows) >= 2:
            short_window = self.correlation_windows[0]
            long_window = self.correlation_windows[-1]
            df["spy_correlation_change"] = (
                df[f"spy_correlation_{short_window}d"] -
                df[f"spy_correlation_{long_window}d"]
            )

        return df

    def _add_beta_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add rolling beta (systematic risk measure).

        Beta = Cov(symbol, market) / Var(market)

        Features:
        - market_beta_20d: Short-term beta
        - market_beta_60d: Medium-term beta (standard measure)
        - market_beta_momentum: Change in beta (increasing/decreasing risk)
        """
        symbol_returns = df["symbol_returns"]
        spy_returns = df["spy_returns"]

        for window in [20, 60]:
            # Rolling covariance and variance
            rolling_cov = symbol_returns.rolling(window).cov(spy_returns)
            rolling_var = spy_returns.rolling(window).var()

            # Beta = Cov / Var
            beta = rolling_cov / rolling_var.replace(0, np.nan)
            df[f"market_beta_{window}d"] = beta.fillna(1.0)  # Fill with market-neutral

        # Beta momentum (is beta increasing or decreasing?)
        df["market_beta_momentum"] = (
            df["market_beta_20d"] - df["market_beta_60d"]
        )

        # Beta regime (categorical)
        df["market_beta_regime"] = pd.cut(
            df["market_beta_60d"],
            bins=[-np.inf, 0.5, 1.0, 1.5, np.inf],
            labels=[0, 1, 2, 3]  # defensive, neutral, aggressive, very aggressive
        ).astype(float)

        return df

    def _add_relative_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add relative strength vs market.

        RS = (Symbol performance / SPY performance) over period

        Features:
        - market_rs_20d: 20-day relative strength
        - market_rs_60d: 60-day relative strength
        - market_rs_trend: Is RS improving or deteriorating?
        """
        symbol_returns = df["symbol_returns"]
        spy_returns = df["spy_returns"]

        for window in [20, 60]:
            # Cumulative returns over window
            symbol_cum = (1 + symbol_returns).rolling(window).apply(
                lambda x: x.prod() - 1, raw=True
            )
            spy_cum = (1 + spy_returns).rolling(window).apply(
                lambda x: x.prod() - 1, raw=True
            )

            # Relative strength (ratio of cumulative returns)
            # Positive = outperforming, Negative = underperforming
            df[f"market_rs_{window}d"] = symbol_cum - spy_cum

        # RS trend (momentum of relative strength)
        df["market_rs_trend"] = (
            df["market_rs_20d"] - df["market_rs_60d"]
        )

        # RS percentile (where does current RS rank historically?)
        df["market_rs_percentile"] = (
            df["market_rs_20d"]
            .rolling(252)
            .apply(lambda x: (x.iloc[-1] > x[:-1]).mean() if len(x) > 1 else 0.5, raw=False)
        ).fillna(0.5)

        return df

    def _add_momentum_spread_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add momentum spread features (symbol momentum vs market momentum).

        Features:
        - momentum_spread_5d: 5-day momentum difference
        - momentum_spread_20d: 20-day momentum difference
        - momentum_alignment: Are symbol and market moving same direction?
        """
        for window in [5, 20]:
            symbol_mom = df["close"].pct_change(window, fill_method=None)

            if "spy_close_aligned" in df.columns:
                spy_mom = df["spy_close_aligned"].pct_change(window, fill_method=None)
            else:
                spy_mom = df["spy_returns"].rolling(window).sum()

            # Momentum spread
            df[f"momentum_spread_{window}d"] = symbol_mom - spy_mom

        # Momentum alignment (are they moving same direction?)
        symbol_dir = np.sign(df["close"].pct_change(5, fill_method=None))
        spy_dir = np.sign(df["spy_returns"].rolling(5).sum())
        df["momentum_alignment"] = (symbol_dir == spy_dir).astype(float)

        return df

    def _add_placeholder_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add placeholder features when SPY data is not available."""
        placeholder_features = [
            "spy_correlation_20d",
            "spy_correlation_60d",
            "spy_correlation_120d",
            "spy_correlation_change",
            "market_beta_20d",
            "market_beta_60d",
            "market_beta_momentum",
            "market_beta_regime",
            "market_rs_20d",
            "market_rs_60d",
            "market_rs_trend",
            "market_rs_percentile",
            "momentum_spread_5d",
            "momentum_spread_20d",
            "momentum_alignment",
        ]

        for col in placeholder_features:
            if "beta" in col:
                df[col] = 1.0  # Market-neutral assumption
            elif "alignment" in col:
                df[col] = 0.5  # Assume 50% alignment
            elif "percentile" in col:
                df[col] = 0.5  # Middle percentile
            elif "regime" in col:
                df[col] = 1.0  # Neutral regime
            else:
                df[col] = 0.0  # No correlation/spread

        logger.warning("Using placeholder market correlation features (SPY data not available)")
        return df


def add_spy_correlation_features(
    df: pd.DataFrame,
    spy_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Convenience function to add SPY correlation features.

    Args:
        df: Symbol DataFrame with ts, close columns
        spy_df: Optional SPY DataFrame (will try to fetch if not provided)

    Returns:
        DataFrame with SPY correlation features added
    """
    calculator = MarketCorrelationFeatures(spy_data=spy_df)
    return calculator.calculate_features(df)


def fetch_spy_data(
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch SPY data from database.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with SPY OHLC data or None if not available
    """
    try:
        from src.data.supabase_db import db

        spy_data = db.fetch_ohlc_bars("SPY", timeframe="d1", limit=500)

        if spy_data is not None and len(spy_data) > 0:
            logger.info("Fetched SPY data: %d rows", len(spy_data))
            return spy_data
        else:
            logger.warning("No SPY data available in database")
            return None

    except Exception as e:
        logger.warning("Failed to fetch SPY data: %s", e)
        return None


if __name__ == "__main__":
    # Test with synthetic data
    import numpy as np

    np.random.seed(42)
    n = 200

    # Create synthetic SPY data
    spy_prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))
    spy_df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
        "close": spy_prices,
    })

    # Create synthetic symbol data (correlated with SPY)
    noise = np.random.randn(n) * 0.01
    symbol_prices = 50 * np.exp(np.cumsum(
        0.7 * np.diff(np.log(spy_prices), prepend=np.log(spy_prices[0])) +
        0.3 * noise +
        0.002  # slight outperformance
    ))
    symbol_df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
        "close": symbol_prices,
    })

    print("Testing MarketCorrelationFeatures...")

    # Calculate features
    calculator = MarketCorrelationFeatures(spy_data=spy_df)
    result = calculator.calculate_features(symbol_df)

    print(f"\nFeatures added: {[c for c in result.columns if c not in ['ts', 'close']]}")
    print(f"\nSample values (last row):")
    for col in result.columns:
        if col not in ["ts", "close"]:
            print(f"  {col}: {result[col].iloc[-1]:.4f}")

    print("\nSUCCESS: MarketCorrelationFeatures working!")
