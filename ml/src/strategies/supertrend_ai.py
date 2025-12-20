"""
SuperTrend AI with K-means Clustering for adaptive factor selection.

This module implements an adaptive SuperTrend indicator that uses ML (K-means clustering)
to find the optimal ATR multiplier factor based on historical performance.

Key Features:
- Tests multiple ATR factors (1.0 to 5.0)
- Clusters factors by performance using K-means
- Selects optimal factor from 'Best' cluster
- Generates performance-adaptive signals
- Outputs signal strength score (0-10)

Usage:
    supertrend = SuperTrendAI(df)
    result_df, info = supertrend.calculate()
    # result_df contains 'supertrend', 'trend', 'signal' columns
    # info contains 'target_factor', 'performance_index', 'signal_strength'
"""

import logging
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)


class SuperTrendAI:
    """
    SuperTrend AI with K-means Clustering for adaptive factor selection.

    The indicator tests multiple ATR multipliers (factors), measures their
    historical performance, clusters them using K-means, and selects the
    optimal factor from the best-performing cluster.

    Args:
        df: DataFrame with OHLCV data (columns: high, low, close, volume)
        atr_length: Period for ATR calculation (default: 10)
        min_mult: Minimum ATR multiplier to test (default: 1.0)
        max_mult: Maximum ATR multiplier to test (default: 5.0)
        step: Step size between multipliers (default: 0.5)
        perf_alpha: Smoothing factor for performance calculation (default: 10)
        from_cluster: Which cluster to select from ('Best', 'Average', 'Worst')
        max_iter: Maximum iterations for K-means (default: 1000)
        max_data: Maximum data points for clustering (default: 10000)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        atr_length: int = 10,
        min_mult: float = 1.0,
        max_mult: float = 5.0,
        step: float = 0.5,
        perf_alpha: int = 10,
        from_cluster: str = "Best",
        max_iter: int = 1000,
        max_data: int = 10000,
    ):
        self.df = df.copy()
        self.atr_length = atr_length
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.step = step
        self.perf_alpha = perf_alpha
        self.from_cluster = from_cluster
        self.max_iter = max_iter
        self.max_data = max_data

        if min_mult > max_mult:
            raise ValueError("Minimum multiplier cannot be greater than maximum")

        self.factors = np.arange(min_mult, max_mult + step, step)
        logger.info(
            f"SuperTrendAI initialized: ATR={atr_length}, "
            f"factors={min_mult}-{max_mult}, cluster={from_cluster}"
        )

    def calculate_atr(self) -> pd.Series:
        """Calculate Average True Range using EMA smoothing."""
        high, low, close = self.df["high"], self.df["low"], self.df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=self.atr_length, adjust=False).mean()

    def calculate_supertrend(
        self, atr: pd.Series, factor: float
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate SuperTrend for a given ATR multiplier.

        Args:
            atr: ATR series
            factor: ATR multiplier

        Returns:
            Tuple of (supertrend values, trend direction)
        """
        high, low, close = self.df["high"], self.df["low"], self.df["close"]
        hl2 = (high + low) / 2

        upper_band = hl2 + (atr * factor)
        lower_band = hl2 - (atr * factor)

        final_upper = pd.Series(0.0, index=self.df.index)
        final_lower = pd.Series(0.0, index=self.df.index)
        supertrend = pd.Series(0.0, index=self.df.index)
        trend = pd.Series(0, index=self.df.index)

        # Initialize first values
        final_upper.iloc[0] = upper_band.iloc[0]
        final_lower.iloc[0] = lower_band.iloc[0]
        supertrend.iloc[0] = lower_band.iloc[0]
        trend.iloc[0] = 1

        for i in range(1, len(self.df)):
            # Final upper band logic
            if (
                upper_band.iloc[i] < final_upper.iloc[i - 1]
                or close.iloc[i - 1] > final_upper.iloc[i - 1]
            ):
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

            # Final lower band logic
            if (
                lower_band.iloc[i] > final_lower.iloc[i - 1]
                or close.iloc[i - 1] < final_lower.iloc[i - 1]
            ):
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]

            # Trend determination
            if close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1  # Bullish
            elif close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = 0  # Bearish
            else:
                trend.iloc[i] = trend.iloc[i - 1]

            # SuperTrend output
            supertrend.iloc[i] = (
                final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]
            )

        return supertrend, trend

    def calculate_performance(
        self, supertrend: pd.Series, trend: pd.Series
    ) -> float:
        """
        Calculate performance metric for a SuperTrend configuration.

        Uses EMA-smoothed returns aligned with trend direction.

        Args:
            supertrend: SuperTrend values
            trend: Trend direction (1=bullish, 0=bearish)

        Returns:
            Performance score (higher is better)
        """
        close = self.df["close"]
        alpha = 2 / (self.perf_alpha + 1)

        perf = 0.0
        for i in range(1, len(self.df)):
            prev_close = close.iloc[i - 1]
            curr_close = close.iloc[i]
            prev_st = supertrend.iloc[i - 1]

            # Direction: +1 if price above supertrend, -1 if below
            diff = np.sign(prev_close - prev_st) if prev_st > 0 else 0
            price_change = curr_close - prev_close

            # EMA of direction-aligned returns
            perf = perf + alpha * (price_change * diff - perf)

        return perf

    def run_kmeans_clustering(
        self, performances: list, factors: list
    ) -> Tuple[float, Dict[int, str]]:
        """
        Perform K-means clustering to find optimal factor.

        Clusters factors into Best/Average/Worst based on performance.

        Args:
            performances: List of performance scores
            factors: List of corresponding factors

        Returns:
            Tuple of (optimal factor, cluster mapping)
        """
        data_limit = min(len(performances), self.max_data)
        perf_array = np.array(performances[-data_limit:]).reshape(-1, 1)
        factor_array = np.array(factors[-data_limit:])

        if len(perf_array) < 3:
            return self.min_mult, {}

        # Initialize centroids using quartiles for stability
        q25, q50, q75 = np.percentile(perf_array, [25, 50, 75])
        initial_centroids = np.array([[q25], [q50], [q75]])

        kmeans = KMeans(
            n_clusters=3,
            init=initial_centroids,
            max_iter=self.max_iter,
            n_init=1,
            random_state=42,
        )
        labels = kmeans.fit_predict(perf_array)

        # Group factors by cluster
        clusters: Dict[int, list] = {0: [], 1: [], 2: []}
        perf_clusters: Dict[int, list] = {0: [], 1: [], 2: []}

        for i, label in enumerate(labels):
            clusters[label].append(factor_array[i])
            perf_clusters[label].append(perf_array[i][0])

        # Sort clusters by average performance
        cluster_means = {k: np.mean(v) if v else 0 for k, v in perf_clusters.items()}
        sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1])

        cluster_mapping = {
            sorted_clusters[0][0]: "Worst",
            sorted_clusters[1][0]: "Average",
            sorted_clusters[2][0]: "Best",
        }

        # Get target cluster factors
        target_label = [
            k for k, v in cluster_mapping.items() if v == self.from_cluster
        ][0]
        target_factors = clusters[target_label]

        optimal_factor = np.mean(target_factors) if target_factors else self.min_mult

        logger.info(
            f"K-means clustering: Best cluster mean={sorted_clusters[2][1]:.4f}, "
            f"optimal factor={optimal_factor:.2f}"
        )

        return optimal_factor, cluster_mapping

    def calculate(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Main calculation - returns DataFrame with SuperTrend and info dict.

        Returns:
            Tuple of:
            - DataFrame with added columns: supertrend, trend, perf_ama,
              target_factor, atr, signal
            - Dict with: target_factor, cluster_mapping, performance_index,
              signal_strength
        """
        atr = self.calculate_atr()

        # Test all factors
        all_performances = []
        for factor in self.factors:
            st, trend = self.calculate_supertrend(atr, factor)
            perf = self.calculate_performance(st, trend)
            all_performances.append(perf)

        # Find optimal factor via clustering
        target_factor, cluster_mapping = self.run_kmeans_clustering(
            all_performances, self.factors.tolist()
        )

        # Calculate final SuperTrend with optimal factor
        final_st, final_trend = self.calculate_supertrend(atr, target_factor)

        # Performance index (0-1 normalized)
        close = self.df["close"]
        den = close.diff().abs().ewm(span=self.perf_alpha, adjust=False).mean()
        perf_idx = max(self.calculate_performance(final_st, final_trend), 0) / (
            den.iloc[-1] + 1e-10
        )
        perf_idx = min(max(perf_idx, 0), 1)

        # Performance-adaptive MA
        perf_ama = pd.Series(final_st.iloc[0], index=self.df.index)
        for i in range(1, len(self.df)):
            perf_ama.iloc[i] = perf_ama.iloc[i - 1] + perf_idx * (
                final_st.iloc[i] - perf_ama.iloc[i - 1]
            )

        # Store results
        self.df["supertrend"] = final_st
        self.df["supertrend_trend"] = final_trend
        self.df["perf_ama"] = perf_ama
        self.df["target_factor"] = target_factor
        self.df["atr"] = atr

        # Generate signals (trend changes)
        self.df["supertrend_signal"] = 0
        for i in range(1, len(self.df)):
            prev_trend = self.df["supertrend_trend"].iloc[i - 1]
            curr_trend = self.df["supertrend_trend"].iloc[i]
            if prev_trend == 0 and curr_trend == 1:
                self.df.loc[self.df.index[i], "supertrend_signal"] = 1  # Buy
            elif prev_trend == 1 and curr_trend == 0:
                self.df.loc[self.df.index[i], "supertrend_signal"] = -1  # Sell

        info = {
            "target_factor": target_factor,
            "cluster_mapping": cluster_mapping,
            "performance_index": perf_idx,
            "signal_strength": int(perf_idx * 10),  # 0-10 score
            "factors_tested": self.factors.tolist(),
            "performances": all_performances,
        }

        logger.info(
            f"SuperTrend AI complete: factor={target_factor:.2f}, "
            f"perf_idx={perf_idx:.3f}, signal_strength={info['signal_strength']}/10"
        )

        return self.df, info

    def predict(self, new_df: pd.DataFrame, target_factor: float) -> pd.DataFrame:
        """
        Generate SuperTrend signals using a pre-fitted optimal factor.

        Useful for applying a trained factor to new data without re-clustering.

        Args:
            new_df: New OHLCV DataFrame
            target_factor: Pre-determined optimal factor

        Returns:
            DataFrame with supertrend columns added
        """
        self.df = new_df.copy()
        atr = self.calculate_atr()
        supertrend, trend = self.calculate_supertrend(atr, target_factor)

        self.df["supertrend"] = supertrend
        self.df["supertrend_trend"] = trend
        self.df["supertrend_signal"] = trend.diff().fillna(0)

        return self.df
