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
- Extracts detailed signal metadata with confidence scores
- Calculates stop levels and target prices

Usage:
    supertrend = SuperTrendAI(df)
    result_df, info = supertrend.calculate()
    # result_df contains 'supertrend', 'trend', 'signal', 'signal_confidence' columns
    # info contains 'target_factor', 'performance_index', 'signal_strength', 'signals'
"""

import logging
from typing import Any, Dict, List, Tuple

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

    def calculate_supertrend(self, atr: pd.Series, factor: float) -> Tuple[pd.Series, pd.Series]:
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
            supertrend.iloc[i] = final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]

        return supertrend, trend

    def calculate_performance(self, supertrend: pd.Series, trend: pd.Series) -> float:
        """
        Calculate performance metric for a SuperTrend configuration.

        Implements LuxAlgo formula:
        P(t, factor) = P(t-1) + α × (ΔC(t) × S(t-1, factor) - P(t-1))

        Where:
        - P(t) = performance at time t
        - α = smoothing factor (2 / (perf_alpha + 1))
        - ΔC(t) = price change (close[t] - close[t-1])
        - S(t-1, factor) = signal from previous bar (+1 bullish, -1 bearish)

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
            curr_close = close.iloc[i]
            prev_close = close.iloc[i - 1]
            prev_trend = trend.iloc[i - 1]

            # S(t-1, factor): Signal direction from previous bar
            # Convert trend (1=bullish, 0=bearish) to signal (+1, -1)
            signal = 1 if prev_trend == 1 else -1

            # ΔC(t): Price change
            price_change = curr_close - prev_close

            # LuxAlgo formula: P(t) = P(t-1) + α × (ΔC(t) × S(t-1) - P(t-1))
            perf = perf + alpha * (price_change * signal - perf)

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
        target_label = [k for k, v in cluster_mapping.items() if v == self.from_cluster][0]
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
                self.df.loc[self.df.index[i], "supertrend_signal"] = 1
            elif prev_trend == 1 and curr_trend == 0:
                self.df.loc[self.df.index[i], "supertrend_signal"] = -1

        # Calculate per-bar confidence scores
        self.df["signal_confidence"] = self.calculate_signal_confidence(perf_idx)

        # Extract signal metadata
        signals = self.extract_signal_metadata(perf_idx)

        # Get current state
        current_state = self.get_current_state()

        info = {
            "target_factor": target_factor,
            "cluster_mapping": cluster_mapping,
            "performance_index": perf_idx,
            "signal_strength": int(perf_idx * 10),  # 0-10 score
            "factors_tested": self.factors.tolist(),
            "performances": all_performances,
            # NEW: Enhanced output
            "signals": signals,
            "current_trend": current_state.get("current_trend", "UNKNOWN"),
            "current_stop_level": current_state.get("current_stop_level", 0),
            "trend_duration_bars": current_state.get("trend_duration_bars", 0),
            "total_signals": len(signals),
            "buy_signals": len([s for s in signals if s["type"] == "BUY"]),
            "sell_signals": len([s for s in signals if s["type"] == "SELL"]),
        }

        logger.info(
            f"SuperTrend AI complete: factor={target_factor:.2f}, "
            f"perf={perf_idx:.3f}, strength={info['signal_strength']}/10, "
            f"signals={len(signals)}"
        )

        return self.df, info

    def calculate_signal_confidence(self, perf_idx: float) -> pd.Series:
        """
        Calculate per-bar confidence score based on multiple factors.

        Confidence is derived from:
        - Base performance index (0-1)
        - Price distance from SuperTrend (confirmation strength)
        - Trend duration (longer trends = higher confidence)

        Args:
            perf_idx: Overall performance index (0-1)

        Returns:
            Series of confidence scores (0-10)
        """
        close = self.df["close"]
        st = self.df["supertrend"]
        trend = self.df["supertrend_trend"]

        # Base confidence from performance index
        base_confidence = perf_idx * 7  # Max 7 from performance

        # Distance bonus: higher when price clearly above/below SuperTrend
        distance_pct = ((close - st) / close).abs() * 100
        distance_bonus = np.clip(distance_pct / 2, 0, 1.5)

        # Trend duration bonus: longer trends get slight boost
        trend_duration = pd.Series(0, index=self.df.index)
        duration = 0
        for i in range(1, len(self.df)):
            if trend.iloc[i] == trend.iloc[i - 1]:
                duration += 1
            else:
                duration = 0
            trend_duration.iloc[i] = duration

        duration_bonus = np.clip(trend_duration / 20, 0, 1.5)

        # Combine and clip to 0-10
        confidence = base_confidence + distance_bonus + duration_bonus
        confidence = np.clip(confidence, 0, 10).astype(int)

        return pd.Series(confidence, index=self.df.index)

    def extract_signal_metadata(
        self, perf_idx: float, risk_reward_ratio: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Extract detailed metadata for each signal candle.

        For each BUY/SELL signal, calculates:
        - Entry price
        - Stop level (SuperTrend value)
        - Target price (based on risk:reward ratio)
        - Confidence score (0-10)
        - ATR at signal time

        Args:
            perf_idx: Performance index for confidence calculation
            risk_reward_ratio: Target profit / risk ratio (default 2.0)

        Returns:
            List of signal dictionaries with full metadata
        """
        signals = []
        atr = self.df["atr"]
        confidence = self.calculate_signal_confidence(perf_idx)

        for i in range(1, len(self.df)):
            signal = self.df["supertrend_signal"].iloc[i]
            if signal != 0:
                entry_price = float(self.df["close"].iloc[i])
                stop_level = float(self.df["supertrend"].iloc[i])
                atr_val = float(atr.iloc[i])

                # Calculate risk (distance to stop)
                risk = abs(entry_price - stop_level)

                # Calculate target based on risk:reward ratio
                if signal == 1:  # BUY
                    target_price = entry_price + (risk * risk_reward_ratio)
                else:  # SELL
                    target_price = entry_price - (risk * risk_reward_ratio)

                # Get date - prioritize 'ts' column over index
                if "ts" in self.df.columns:
                    ts_val = self.df["ts"].iloc[i]
                    if hasattr(ts_val, "isoformat"):
                        date_str = ts_val.isoformat()
                    elif hasattr(ts_val, "strftime"):
                        date_str = ts_val.strftime("%Y-%m-%dT%H:%M:%S")
                    else:
                        # If ts is a timestamp integer, convert it
                        import datetime

                        date_str = datetime.datetime.fromtimestamp(ts_val).isoformat()
                else:
                    # Fallback to index
                    idx = self.df.index[i]
                    if hasattr(idx, "isoformat"):
                        date_str = idx.isoformat()
                    elif hasattr(idx, "strftime"):
                        date_str = idx.strftime("%Y-%m-%dT%H:%M:%S")
                    else:
                        # Use current time as fallback
                        import datetime

                        date_str = datetime.datetime.now().isoformat()

                signals.append(
                    {
                        "date": date_str,
                        "type": "BUY" if signal == 1 else "SELL",
                        "price": entry_price,
                        "confidence": int(confidence.iloc[i]),
                        "stop_level": stop_level,
                        "target_price": float(target_price),
                        "atr_at_signal": atr_val,
                        "risk_amount": float(risk),
                        "reward_amount": float(risk * risk_reward_ratio),
                    }
                )

        return signals

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get the current state of the SuperTrend indicator.

        Returns:
            Dictionary with current trend info, stop level, duration
        """
        if len(self.df) == 0:
            return {}

        current_trend = self.df["supertrend_trend"].iloc[-1]
        current_stop = self.df["supertrend"].iloc[-1]

        # Calculate trend duration (bars since last signal)
        trend_duration = 0
        for i in range(len(self.df) - 1, 0, -1):
            if self.df["supertrend_signal"].iloc[i] != 0:
                break
            trend_duration += 1

        return {
            "current_trend": "BULLISH" if current_trend == 1 else "BEARISH",
            "current_stop_level": float(current_stop),
            "trend_duration_bars": trend_duration,
            "current_price": float(self.df["close"].iloc[-1]),
            "distance_to_stop_pct": float(
                abs(self.df["close"].iloc[-1] - current_stop) / self.df["close"].iloc[-1] * 100
            ),
        }

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
        self.df["atr"] = atr

        return self.df
