"""
Support and Resistance Level Detection Module.

This module provides S/R detection using 3 modern indicators:
1. Pivot Levels - Multi-timeframe pivots with ATR-based coloring (BigBeluga style)
2. Polynomial Regression - Dynamic trending S/R with forecasts
3. Logistic Regression - ML-based S/R with probability predictions

DEPRECATED: The following legacy methods are still available for backwards
compatibility but will be removed in a future version:
- ZigZag
- Local Extrema
- K-Means Clustering
- Classical Pivot Points
- Fibonacci Retracement

Usage:
    from src.features.support_resistance_detector import SupportResistanceDetector

    sr = SupportResistanceDetector()

    # New method (recommended)
    result = sr.find_all_levels(df)

    # Access individual indicators
    pivot_result = sr.calculate_pivot_levels(df)
    poly_result = sr.calculate_polynomial_sr(df)
    logistic_result = sr.calculate_logistic_sr(df)
"""

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from src.features.logistic_sr_indicator import LogisticSRIndicator, LogisticSRSettings
from src.features.pivot_levels_detector import PivotLevelsDetector, PivotLevelsSettings
from src.features.polynomial_sr_indicator import PolynomialSRIndicator, PolynomialSRSettings
from src.features.sr_feature_builder import build_sr_feature_map

logger = logging.getLogger(__name__)


class SupportResistanceDetector:
    """
    Comprehensive support and resistance level detector.

    Uses 3 modern indicators for robust S/R detection:
    - Pivot Levels: Multi-timeframe pivots with ATR-based status (BigBeluga style)
    - Polynomial Regression: Dynamic trending S/R with forecasts
    - Logistic Regression: ML-based S/R with probability predictions

    Legacy methods (deprecated, for backwards compatibility):
    - ZigZag: Filters noise, identifies significant swings
    - Local Extrema: Mathematical peak/trough detection
    - K-Means Clustering: Statistical price zone identification
    - Pivot Points: Classical standard levels
    - Fibonacci: Natural retracement targets

    Attributes:
        pivot_detector: Multi-timeframe pivot levels detector
        polynomial_indicator: Polynomial regression S/R indicator
        logistic_indicator: Logistic regression S/R indicator
    """

    def __init__(
        self,
        default_zigzag_threshold: float = 5.0,
        default_extrema_order: int = 5,
        default_n_clusters: int = 5,
        pivot_settings: Optional[PivotLevelsSettings] = None,
        polynomial_settings: Optional[PolynomialSRSettings] = None,
        logistic_settings: Optional[LogisticSRSettings] = None,
    ):
        """
        Initialize the SupportResistanceDetector.

        Args:
            default_zigzag_threshold: Default percentage threshold for ZigZag (deprecated)
            default_extrema_order: Default order for scipy argrelextrema (deprecated)
            default_n_clusters: Default number of clusters for K-Means (deprecated)
            pivot_settings: Settings for pivot levels detector
            polynomial_settings: Settings for polynomial S/R indicator
            logistic_settings: Settings for logistic S/R indicator
        """
        # Legacy settings (deprecated)
        self.default_zigzag_threshold = default_zigzag_threshold
        self.default_extrema_order = default_extrema_order
        self.default_n_clusters = default_n_clusters

        # New indicators
        self.pivot_detector = PivotLevelsDetector(pivot_settings)
        self.polynomial_indicator = PolynomialSRIndicator(polynomial_settings)
        self.logistic_indicator = LogisticSRIndicator(logistic_settings)

        logger.info(
            "SupportResistanceDetector initialized with 3 indicators: "
            "PivotLevels, PolynomialSR, LogisticSR"
        )

    # =========================================================================
    # NEW INDICATOR METHODS (RECOMMENDED)
    # =========================================================================

    def calculate_pivot_levels(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate multi-timeframe pivot levels.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with pivot levels for each timeframe, nearest S/R, distances
        """
        return self.pivot_detector.calculate(df)

    def calculate_polynomial_sr(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate polynomial regression S/R levels.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with current support/resistance, slopes, forecasts, signals
        """
        return self.polynomial_indicator.calculate(df)

    def calculate_logistic_sr(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate logistic regression S/R levels.

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with ML-detected levels, probabilities, signals
        """
        return self.logistic_indicator.calculate(df)

    # =========================================================================
    # METHOD 1: ZIGZAG INDICATOR
    # =========================================================================

    def zigzag(
        self,
        df: pd.DataFrame,
        threshold_pct: Optional[float] = None,
        price_col: str = "close",
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Calculate ZigZag indicator for identifying significant price swings.

        ZigZag filters out noise by only considering price movements
        greater than the threshold percentage. Excellent for:
        - Identifying trend reversals
        - Finding swing highs/lows
        - Filtering market noise

        Args:
            df: DataFrame with OHLC data
            threshold_pct: Minimum percentage move to register (default: 5%)
            price_col: Column to use for price (default: "close")

        Returns:
            Tuple of:
            - DataFrame with zigzag column added
            - List of swing points with type, price, index, timestamp
        """
        threshold_pct = threshold_pct or self.default_zigzag_threshold
        df = df.copy()

        prices = df[price_col].values
        n = len(prices)

        if n < 3:
            df["zigzag"] = np.nan
            return df, []

        # Initialize zigzag array
        zigzag = np.full(n, np.nan)
        swings: List[Dict[str, Any]] = []

        # Find initial direction
        last_pivot_idx = 0
        last_pivot_price = prices[0]
        zigzag[0] = prices[0]

        # Determine initial trend direction
        direction = 0  # 1 = up, -1 = down
        for i in range(1, min(n, 20)):
            pct_change = (prices[i] - last_pivot_price) / last_pivot_price * 100
            if abs(pct_change) >= threshold_pct:
                direction = 1 if pct_change > 0 else -1
                break

        if direction == 0:
            direction = 1 if prices[-1] > prices[0] else -1

        # Process each bar
        for i in range(1, n):
            pct_change = (prices[i] - last_pivot_price) / last_pivot_price * 100

            if direction == 1:  # Looking for high
                if prices[i] > last_pivot_price:
                    last_pivot_price = prices[i]
                    last_pivot_idx = i
                elif pct_change <= -threshold_pct:
                    # Reversal detected - mark the high
                    zigzag[last_pivot_idx] = last_pivot_price
                    ts = df["ts"].iloc[last_pivot_idx] if "ts" in df.columns else last_pivot_idx
                    swings.append(
                        {
                            "type": "high",
                            "price": float(last_pivot_price),
                            "index": last_pivot_idx,
                            "ts": ts,
                        }
                    )
                    # Start looking for low
                    direction = -1
                    last_pivot_price = prices[i]
                    last_pivot_idx = i

            else:  # Looking for low
                if prices[i] < last_pivot_price:
                    last_pivot_price = prices[i]
                    last_pivot_idx = i
                elif pct_change >= threshold_pct:
                    # Reversal detected - mark the low
                    zigzag[last_pivot_idx] = last_pivot_price
                    ts = df["ts"].iloc[last_pivot_idx] if "ts" in df.columns else last_pivot_idx
                    swings.append(
                        {
                            "type": "low",
                            "price": float(last_pivot_price),
                            "index": last_pivot_idx,
                            "ts": ts,
                        }
                    )
                    # Start looking for high
                    direction = 1
                    last_pivot_price = prices[i]
                    last_pivot_idx = i

        # Mark the last pivot
        zigzag[last_pivot_idx] = last_pivot_price
        ts = df["ts"].iloc[last_pivot_idx] if "ts" in df.columns else last_pivot_idx
        swings.append(
            {
                "type": "high" if direction == 1 else "low",
                "price": float(last_pivot_price),
                "index": last_pivot_idx,
                "ts": ts,
            }
        )

        df["zigzag"] = zigzag

        # Extract support and resistance from swings
        highs = [s["price"] for s in swings if s["type"] == "high"]
        lows = [s["price"] for s in swings if s["type"] == "low"]

        logger.info(
            f"ZigZag: {len(swings)} swings detected " f"({len(highs)} highs, {len(lows)} lows)"
        )

        return df, swings

    # =========================================================================
    # METHOD 2: LOCAL EXTREMA (SCIPY)
    # =========================================================================

    def local_extrema(
        self,
        df: pd.DataFrame,
        order: Optional[int] = None,
        price_col: str = "close",
    ) -> Dict[str, Any]:
        """
        Find local minima and maxima using scipy's argrelextrema.

        Uses mathematical peak/trough detection with configurable
        neighborhood size. Good for:
        - Precise peak/trough identification
        - Short-term S/R levels
        - Algorithmic trading signals

        Args:
            df: DataFrame with OHLC data
            order: Number of points on each side to compare (default: 5)
            price_col: Column to use for price (default: "close")

        Returns:
            Dict with:
            - local_maxima: List of (index, price) tuples for peaks
            - local_minima: List of (index, price) tuples for troughs
            - resistance_levels: Unique resistance prices
            - support_levels: Unique support prices
        """
        order = order or self.default_extrema_order
        prices = df[price_col].values

        if len(prices) < order * 2 + 1:
            return {
                "local_maxima": [],
                "local_minima": [],
                "resistance_levels": [],
                "support_levels": [],
            }

        # Find local maxima (resistance)
        max_indices = argrelextrema(prices, np.greater, order=order)[0]
        local_maxima = [(int(i), float(prices[i])) for i in max_indices]

        # Find local minima (support)
        min_indices = argrelextrema(prices, np.less, order=order)[0]
        local_minima = [(int(i), float(prices[i])) for i in min_indices]

        # Extract unique levels (rounded to reduce noise)
        resistance_levels = sorted(set(round(p, 2) for _, p in local_maxima), reverse=True)
        support_levels = sorted(set(round(p, 2) for _, p in local_minima))

        logger.info(f"Local Extrema: {len(local_maxima)} maxima, {len(local_minima)} minima")

        return {
            "local_maxima": local_maxima,
            "local_minima": local_minima,
            "resistance_levels": resistance_levels,
            "support_levels": support_levels,
        }

    # =========================================================================
    # METHOD 3: K-MEANS CLUSTERING
    # =========================================================================

    def kmeans_clustering(
        self,
        df: pd.DataFrame,
        n_clusters: Optional[int] = None,
        price_col: str = "close",
    ) -> Dict[str, Any]:
        """
        Identify support/resistance zones using K-Means clustering.

        Groups price levels into clusters to identify zones where
        price has historically concentrated. Good for:
        - Identifying price zones (not just lines)
        - Statistical significance of levels
        - Long-term S/R identification

        Args:
            df: DataFrame with OHLC data
            n_clusters: Number of clusters (default: 5)
            price_col: Column to use for price (default: "close")

        Returns:
            Dict with:
            - cluster_centers: List of cluster center prices
            - support_zones: Clusters below current price
            - resistance_zones: Clusters above current price
            - cluster_labels: Array of cluster assignments
        """
        n_clusters = n_clusters or self.default_n_clusters

        try:
            from sklearn.cluster import KMeans
        except ImportError:
            logger.warning("sklearn not available, K-Means clustering disabled")
            return {
                "cluster_centers": [],
                "support_zones": [],
                "resistance_zones": [],
                "cluster_labels": [],
            }

        prices = df[price_col].values.reshape(-1, 1)
        current_price = prices[-1][0]

        if len(prices) < n_clusters:
            n_clusters = max(2, len(prices) // 2)

        # Fit K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(prices)
        centers = sorted(kmeans.cluster_centers_.flatten())

        # Classify as support or resistance
        support_zones = [float(c) for c in centers if c < current_price]
        resistance_zones = [float(c) for c in centers if c > current_price]

        logger.info(
            f"K-Means: {len(support_zones)} support zones, "
            f"{len(resistance_zones)} resistance zones"
        )

        return {
            "cluster_centers": [float(c) for c in centers],
            "support_zones": support_zones,
            "resistance_zones": resistance_zones,
            "cluster_labels": labels.tolist(),
        }

    # =========================================================================
    # METHOD 4: PIVOT POINTS (CLASSICAL)
    # =========================================================================

    def pivot_points_classical(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Calculate classical pivot points from the most recent period.

        Standard pivot point formula used by professional traders:
        PP = (High + Low + Close) / 3
        R1 = 2*PP - Low
        S1 = 2*PP - High
        R2 = PP + (High - Low)
        S2 = PP - (High - Low)
        R3 = High + 2*(PP - Low)
        S3 = Low - 2*(High - PP)

        Args:
            df: DataFrame with high, low, close columns

        Returns:
            Dict with PP, R1, R2, R3, S1, S2, S3 levels
        """
        if len(df) < 1:
            return {}

        # Use the most recent complete period
        high = df["high"].iloc[-1]
        low = df["low"].iloc[-1]
        close = df["close"].iloc[-1]

        # Calculate pivot point
        pp = (high + low + close) / 3

        # Calculate support and resistance levels
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = high + 2 * (pp - low)
        s3 = low - 2 * (high - pp)

        pivots = {
            "PP": round(pp, 2),
            "R1": round(r1, 2),
            "R2": round(r2, 2),
            "R3": round(r3, 2),
            "S1": round(s1, 2),
            "S2": round(s2, 2),
            "S3": round(s3, 2),
        }

        logger.info(f"Pivot Points: PP={pp:.2f}, R1={r1:.2f}, S1={s1:.2f}")

        return pivots

    def pivot_points_from_range(
        self,
        df: pd.DataFrame,
        lookback: int = 20,
    ) -> Dict[str, float]:
        """
        Calculate pivot points from a lookback range.

        Uses the high/low/close from a specified lookback period
        for more stable pivot calculations.

        Args:
            df: DataFrame with high, low, close columns
            lookback: Number of periods to look back (default: 20)

        Returns:
            Dict with PP, R1, R2, R3, S1, S2, S3 levels
        """
        if len(df) < lookback:
            lookback = len(df)

        recent = df.tail(lookback)
        high = recent["high"].max()
        low = recent["low"].min()
        close = recent["close"].iloc[-1]

        pp = (high + low + close) / 3

        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = high + 2 * (pp - low)
        s3 = low - 2 * (high - pp)

        return {
            "PP": round(pp, 2),
            "R1": round(r1, 2),
            "R2": round(r2, 2),
            "R3": round(r3, 2),
            "S1": round(s1, 2),
            "S2": round(s2, 2),
            "S3": round(s3, 2),
            "period_high": round(high, 2),
            "period_low": round(low, 2),
        }

    # =========================================================================
    # METHOD 5: FIBONACCI RETRACEMENT
    # =========================================================================

    def fibonacci_retracement(
        self,
        df: pd.DataFrame,
        lookback: int = 50,
    ) -> Dict[str, Any]:
        """
        Calculate Fibonacci retracement levels.

        Uses the high/low range from the lookback period to calculate
        standard Fibonacci levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

        Args:
            df: DataFrame with high, low columns
            lookback: Number of periods to determine range (default: 50)

        Returns:
            Dict with:
            - levels: Dict of level name to price
            - trend: "uptrend" or "downtrend"
            - range_high: Highest price in range
            - range_low: Lowest price in range
        """
        if len(df) < lookback:
            lookback = len(df)

        recent = df.tail(lookback)
        range_high = recent["high"].max()
        range_low = recent["low"].min()

        # Determine trend direction
        first_close = recent["close"].iloc[0]
        last_close = recent["close"].iloc[-1]
        trend = "uptrend" if last_close > first_close else "downtrend"

        # Fibonacci ratios
        fib_ratios = {
            "0.0": 0.0,
            "23.6": 0.236,
            "38.2": 0.382,
            "50.0": 0.5,
            "61.8": 0.618,
            "78.6": 0.786,
            "100.0": 1.0,
        }

        diff = range_high - range_low

        if trend == "uptrend":
            # In uptrend, retracements are measured from high
            levels = {
                name: round(range_high - diff * ratio, 2) for name, ratio in fib_ratios.items()
            }
        else:
            # In downtrend, retracements are measured from low
            levels = {
                name: round(range_low + diff * ratio, 2) for name, ratio in fib_ratios.items()
            }

        logger.info(f"Fibonacci: {trend}, range={range_low:.2f}-{range_high:.2f}")

        return {
            "levels": levels,
            "trend": trend,
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
        }

    # =========================================================================
    # COMBINED ANALYSIS
    # =========================================================================

    def find_all_levels(
        self,
        df: pd.DataFrame,
        zigzag_threshold: Optional[float] = None,
        extrema_order: Optional[int] = None,
        n_clusters: Optional[int] = None,
        fib_lookback: int = 50,
        use_new_indicators: bool = True,
    ) -> Dict[str, Any]:
        """
        Find all support and resistance levels using modern indicators.

        Uses 3 modern indicators by default:
        - Pivot Levels (multi-timeframe)
        - Polynomial Regression
        - Logistic Regression

        Legacy methods are only used if use_new_indicators=False.

        Args:
            df: DataFrame with OHLC data
            zigzag_threshold: ZigZag threshold percentage (deprecated)
            extrema_order: Order for local extrema detection (deprecated)
            n_clusters: Number of K-Means clusters (deprecated)
            fib_lookback: Lookback for Fibonacci calculation (deprecated)
            use_new_indicators: Use modern indicators (default True)

        Returns:
            Comprehensive dict with all S/R levels and analysis
        """
        if df.empty:
            return self._empty_result()

        current_price = float(df["close"].iloc[-1])

        if use_new_indicators:
            return self._find_levels_with_new_indicators(df, current_price)
        else:
            # Legacy mode for backwards compatibility
            warnings.warn(
                "Legacy S/R methods are deprecated. Use use_new_indicators=True.",
                DeprecationWarning,
            )
            return self._find_levels_legacy(
                df, current_price, zigzag_threshold, extrema_order, n_clusters, fib_lookback
            )

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "current_price": None,
            "nearest_support": None,
            "nearest_resistance": None,
            "support_distance_pct": None,
            "resistance_distance_pct": None,
            "all_supports": [],
            "all_resistances": [],
            "indicators": {},
            "methods": {},  # Legacy key for backwards compatibility
        }

    def _find_levels_with_new_indicators(
        self,
        df: pd.DataFrame,
        current_price: float,
    ) -> Dict[str, Any]:
        """
        Find S/R levels using the 3 modern indicators.

        Args:
            df: DataFrame with OHLC data
            current_price: Current closing price

        Returns:
            Dict with comprehensive S/R analysis
        """
        # Run all 3 indicators
        pivot_result = self.calculate_pivot_levels(df)
        poly_result = self.calculate_polynomial_sr(df)
        logistic_result = self.calculate_logistic_sr(df)

        # Collect all support candidates
        all_supports = []
        all_resistances = []

        # From Pivot Levels
        if pivot_result.get("nearest_support"):
            all_supports.append(pivot_result["nearest_support"])

        if pivot_result.get("nearest_resistance"):
            all_resistances.append(pivot_result["nearest_resistance"])

        # Add all pivot level values
        for pl in pivot_result.get("pivot_levels", []):
            if pl.get("level_low") and pl["level_low"] > 0 and pl["level_low"] < current_price:
                all_supports.append(pl["level_low"])
            if pl.get("level_high") and pl["level_high"] > 0 and pl["level_high"] > current_price:
                all_resistances.append(pl["level_high"])

        # From Polynomial Regression
        if poly_result.get("current_support") and poly_result["current_support"] < current_price:
            all_supports.append(poly_result["current_support"])

        if (
            poly_result.get("current_resistance")
            and poly_result["current_resistance"] > current_price
        ):
            all_resistances.append(poly_result["current_resistance"])

        # From Logistic Regression
        if logistic_result.get("nearest_support"):
            all_supports.append(logistic_result["nearest_support"])

        if logistic_result.get("nearest_resistance"):
            all_resistances.append(logistic_result["nearest_resistance"])

        # Add all logistic levels
        for level in logistic_result.get("support_levels", []):
            if level.get("level") and level["level"] < current_price:
                all_supports.append(level["level"])

        for level in logistic_result.get("resistance_levels", []):
            if level.get("level") and level["level"] > current_price:
                all_resistances.append(level["level"])

        # Filter and sort (remove duplicates)
        supports_below = sorted(
            list(set(s for s in all_supports if s and s < current_price)), reverse=True
        )
        resistances_above = sorted(list(set(r for r in all_resistances if r and r > current_price)))

        # Find nearest levels
        nearest_support = supports_below[0] if supports_below else None
        nearest_resistance = resistances_above[0] if resistances_above else None

        # Calculate distances
        support_distance_pct = None
        resistance_distance_pct = None

        if nearest_support:
            support_distance_pct = round((current_price - nearest_support) / current_price * 100, 2)
        if nearest_resistance:
            resistance_distance_pct = round(
                (nearest_resistance - current_price) / current_price * 100, 2
            )

        sr_ratio = None
        if nearest_support and nearest_resistance:
            support_gap = current_price - nearest_support
            resistance_gap = nearest_resistance - current_price
            if support_gap > 0:
                sr_ratio = round(resistance_gap / support_gap, 4)

        # Collect signals from all indicators
        all_signals = []
        all_signals.extend(poly_result.get("signals", []))
        all_signals.extend([{"type": s} for s in logistic_result.get("signals", [])])

        legacy_pivot_points = self._build_legacy_pivot_map(
            pivot_result.get("pivot_levels", []), current_price
        )

        computed_at = None
        if "ts" in df.columns and len(df["ts"]):
            computed_at = pd.to_datetime(df["ts"].iloc[-1])
        else:
            computed_at = pd.Timestamp.utcnow()

        support_hold_prob = self._extract_hold_probability(
            logistic_result.get("support_levels", [])
        )
        resistance_hold_prob = self._extract_hold_probability(
            logistic_result.get("resistance_levels", [])
        )

        logistic_support_slope, logistic_resistance_slope = self._compute_logistic_slopes(
            logistic_result.get("support_levels", []),
            logistic_result.get("resistance_levels", []),
        )

        support_methods_agreeing = self._count_method_agreement(
            nearest_support,
            [
                pivot_result.get("nearest_support"),
                poly_result.get("current_support"),
                logistic_result.get("nearest_support"),
            ],
            current_price,
        )
        resistance_methods_agreeing = self._count_method_agreement(
            nearest_resistance,
            [
                pivot_result.get("nearest_resistance"),
                poly_result.get("current_resistance"),
                logistic_result.get("nearest_resistance"),
            ],
            current_price,
        )

        pivot_confidence = self._compute_pivot_confidence(
            pivot_result.get("pivot_levels", []),
            nearest_support,
            nearest_resistance,
            current_price,
        )

        period_high = float(df["high"].max()) if "high" in df.columns else None
        period_low = float(df["low"].min()) if "low" in df.columns else None
        lookback_bars = len(df)

        result = {
            "current_price": round(current_price, 2),
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "support_distance_pct": support_distance_pct,
            "resistance_distance_pct": resistance_distance_pct,
            "sr_ratio": sr_ratio,
            "all_supports": supports_below[:10],
            "all_resistances": resistances_above[:10],
            "signals": all_signals,
            "support_hold_probability": support_hold_prob,
            "resistance_hold_probability": resistance_hold_prob,
            "support_methods_agreeing": support_methods_agreeing,
            "resistance_methods_agreeing": resistance_methods_agreeing,
            "pivot_confidence": pivot_confidence,
            "logistic_support_slope": logistic_support_slope,
            "logistic_resistance_slope": logistic_resistance_slope,
            "bar_count": lookback_bars,
            "lookback_bars": lookback_bars,
            "period_high": period_high,
            "period_low": period_low,
            "computed_at": computed_at,
            "indicators": {
                "pivot_levels": pivot_result,
                "polynomial": poly_result,
                "logistic": logistic_result,
            },
            # Legacy key for backwards compatibility
            "methods": {
                "pivot_levels": pivot_result.get("pivot_levels", []),
                "pivot_points": legacy_pivot_points,
                "polynomial": {
                    "support": poly_result.get("current_support"),
                    "resistance": poly_result.get("current_resistance"),
                    "support_slope": poly_result.get("support_slope"),
                    "resistance_slope": poly_result.get("resistance_slope"),
                },
                "logistic": {
                    "support_levels": logistic_result.get("support_levels", []),
                    "resistance_levels": logistic_result.get("resistance_levels", []),
                },
            },
        }

        logger.info(
            f"S/R Analysis (new): price={current_price:.2f}, "
            f"support={nearest_support}, resistance={nearest_resistance}, "
            f"signals={len(all_signals)}"
        )

        return result

    def _build_legacy_pivot_map(
        self, pivot_levels: List[Dict[str, Any]], current_price: float
    ) -> Dict[str, Optional[float]]:
        """Translate modern pivot levels into legacy PP/S1/S2/R1/R2 map."""

        if current_price is None:
            return {}

        supports = [
            float(level["level_low"])
            for level in pivot_levels
            if level.get("level_low") and float(level["level_low"]) < current_price
        ]
        resistances = [
            float(level["level_high"])
            for level in pivot_levels
            if level.get("level_high") and float(level["level_high"]) > current_price
        ]

        supports = sorted(set(round(s, 2) for s in supports), reverse=True)
        resistances = sorted(set(round(r, 2) for r in resistances))

        legacy_map: Dict[str, Optional[float]] = {"PP": round(current_price, 2)}

        for key, value in zip(["S1", "S2", "S3"], supports):
            legacy_map[key] = value

        for key, value in zip(["R1", "R2", "R3"], resistances):
            legacy_map[key] = value

        return legacy_map

    def _find_levels_legacy(
        self,
        df: pd.DataFrame,
        current_price: float,
        zigzag_threshold: Optional[float],
        extrema_order: Optional[int],
        n_clusters: Optional[int],
        fib_lookback: int,
    ) -> Dict[str, Any]:
        """
        Legacy method using old 5 indicators.

        DEPRECATED: Use find_all_levels with use_new_indicators=True.
        """
        # Run all legacy methods
        zigzag_df, zigzag_swings = self.zigzag(df, zigzag_threshold)
        extrema = self.local_extrema(df, extrema_order)
        clusters = self.kmeans_clustering(df, n_clusters)
        pivots = self.pivot_points_classical(df)
        pivots_range = self.pivot_points_from_range(df)
        fib = self.fibonacci_retracement(df, fib_lookback)

        # Collect all support levels
        all_supports = []

        # From ZigZag lows
        zigzag_lows = [s["price"] for s in zigzag_swings if s["type"] == "low"]
        all_supports.extend(zigzag_lows)

        # From local minima
        all_supports.extend(extrema["support_levels"])

        # From K-Means
        all_supports.extend(clusters["support_zones"])

        # From pivots
        for key in ["S1", "S2", "S3"]:
            if key in pivots:
                all_supports.append(pivots[key])

        # From Fibonacci (levels below current price)
        for level_price in fib["levels"].values():
            if level_price < current_price:
                all_supports.append(level_price)

        # Collect all resistance levels
        all_resistances = []

        # From ZigZag highs
        zigzag_highs = [s["price"] for s in zigzag_swings if s["type"] == "high"]
        all_resistances.extend(zigzag_highs)

        # From local maxima
        all_resistances.extend(extrema["resistance_levels"])

        # From K-Means
        all_resistances.extend(clusters["resistance_zones"])

        # From pivots
        for key in ["R1", "R2", "R3"]:
            if key in pivots:
                all_resistances.append(pivots[key])

        # From Fibonacci (levels above current price)
        for level_price in fib["levels"].values():
            if level_price > current_price:
                all_resistances.append(level_price)

        # Filter and sort
        supports_below = sorted([s for s in all_supports if s < current_price], reverse=True)
        resistances_above = sorted([r for r in all_resistances if r > current_price])

        # Find nearest levels
        nearest_support = supports_below[0] if supports_below else None
        nearest_resistance = resistances_above[0] if resistances_above else None

        # Calculate distances
        support_distance_pct = None
        resistance_distance_pct = None

        if nearest_support:
            support_distance_pct = (current_price - nearest_support) / current_price * 100
        if nearest_resistance:
            resistance_distance_pct = (nearest_resistance - current_price) / current_price * 100

        result = {
            "current_price": round(current_price, 2),
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "support_distance_pct": (
                round(support_distance_pct, 2) if support_distance_pct else None
            ),
            "resistance_distance_pct": (
                round(resistance_distance_pct, 2) if resistance_distance_pct else None
            ),
            "all_supports": supports_below[:10],
            "all_resistances": resistances_above[:10],
            "indicators": {},  # Empty for legacy mode
            "methods": {
                "zigzag": {
                    "swings": zigzag_swings,
                    "highs": zigzag_highs,
                    "lows": zigzag_lows,
                },
                "local_extrema": extrema,
                "kmeans": clusters,
                "pivot_points": pivots,
                "pivot_points_range": pivots_range,
                "fibonacci": fib,
            },
        }

        logger.info(
            f"S/R Analysis (legacy): price={current_price:.2f}, "
            f"support={nearest_support}, resistance={nearest_resistance}"
        )

        return result

    # =========================================================================
    # FEATURE ENGINEERING HELPERS
    # =========================================================================

    def add_sr_features(
        self,
        df: pd.DataFrame,
        zigzag_threshold: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Add support/resistance features to DataFrame for ML.

        Adds columns:
        - distance_to_support_pct: % distance to nearest support
        - distance_to_resistance_pct: % distance to nearest resistance
        - sr_ratio: Ratio of distances (>1 = closer to support)
        - pivot_pp: Pivot point level
        - fib_nearest: Nearest Fibonacci level

        Args:
            df: DataFrame with OHLC data
            zigzag_threshold: ZigZag threshold percentage

        Returns:
            DataFrame with S/R features added
        """
        df = df.copy()

        # Get all levels
        levels = self.find_all_levels(df, zigzag_threshold=zigzag_threshold)

        current_price = levels["current_price"]
        nearest_support = levels["nearest_support"]
        nearest_resistance = levels["nearest_resistance"]

        # Distance features
        if nearest_support:
            df["distance_to_support_pct"] = (df["close"] - nearest_support) / df["close"] * 100
        else:
            df["distance_to_support_pct"] = np.nan

        if nearest_resistance:
            df["distance_to_resistance_pct"] = (
                (nearest_resistance - df["close"]) / df["close"] * 100
            )
        else:
            df["distance_to_resistance_pct"] = np.nan

        # S/R ratio (>1 means closer to support, <1 means closer to resistance)
        if nearest_support and nearest_resistance:
            support_dist = current_price - nearest_support
            resistance_dist = nearest_resistance - current_price
            df["sr_ratio"] = resistance_dist / support_dist if support_dist > 0 else np.nan
        else:
            df["sr_ratio"] = np.nan

        # Pivot point
        methods = levels.get("methods") or {}
        pivots = methods.get("pivot_points") or {}
        df["pivot_pp"] = pivots.get("PP", np.nan)

        # Price position relative to pivot
        if "PP" in pivots:
            df["price_vs_pivot_pct"] = (df["close"] - pivots["PP"]) / pivots["PP"] * 100
        else:
            df["price_vs_pivot_pct"] = np.nan

        # Fibonacci levels
        fib = methods.get("fibonacci") or {}
        fib_levels_dict = fib.get("levels") or {}
        if isinstance(fib_levels_dict, dict):
            fib_levels = list(fib_levels_dict.values())
        elif isinstance(fib_levels_dict, list):
            fib_levels = fib_levels_dict
        else:
            fib_levels = []

        # Find nearest Fibonacci level
        if fib_levels:
            nearest_fib = min(fib_levels, key=lambda x: abs(x - current_price))
            df["fib_nearest"] = nearest_fib
            df["distance_to_fib_pct"] = (df["close"] - nearest_fib) / df["close"] * 100
        else:
            df["fib_nearest"] = np.nan
            df["distance_to_fib_pct"] = np.nan

        # Add rich feature bundle derived from the latest detector output
        sr_feature_map = build_sr_feature_map(levels)
        for feature_name, value in sr_feature_map.items():
            df[feature_name] = value

        logger.info(
            f"Added S/R features: support_dist={levels['support_distance_pct']}%, "
            f"resistance_dist={levels['resistance_distance_pct']}%"
        )

        return df

    def get_level_strength(
        self,
        df: pd.DataFrame,
        level: float,
        tolerance_pct: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate the strength of a support/resistance level.

        Strength is determined by:
        - Number of touches (price approaching the level)
        - Recency of touches
        - Volume at touches

        Args:
            df: DataFrame with OHLC and volume data
            level: Price level to analyze
            tolerance_pct: Percentage tolerance for "touch" detection

        Returns:
            Dict with strength metrics
        """
        tolerance = level * tolerance_pct / 100

        # Find touches (price within tolerance of level)
        touches = df[(df["low"] <= level + tolerance) & (df["high"] >= level - tolerance)]

        n_touches = len(touches)

        # Calculate recency score (more recent = higher score)
        if n_touches > 0 and "ts" in df.columns:
            last_touch_idx = touches.index[-1]
            total_bars = len(df)
            recency_score = (last_touch_idx + 1) / total_bars
        else:
            recency_score = 0.0

        # Calculate volume score
        if n_touches > 0 and "volume" in df.columns:
            avg_touch_volume = touches["volume"].mean()
            avg_total_volume = df["volume"].mean()
            volume_score = avg_touch_volume / avg_total_volume if avg_total_volume > 0 else 1.0
        else:
            volume_score = 1.0

        # Combined strength score (0-100)
        strength = min(100, n_touches * 10 * recency_score * volume_score)

        return {
            "level": level,
            "n_touches": n_touches,
            "recency_score": round(recency_score, 3),
            "volume_score": round(volume_score, 3),
            "strength": round(strength, 1),
        }

    # =========================================================================
    # VOLUME-BASED STRENGTH ANALYSIS (Phase 1)
    # =========================================================================

    def calculate_volume_strength(
        self,
        df: pd.DataFrame,
        level: float,
        tolerance_pct: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate volume-based strength for a support/resistance level.

        Measures:
        - Average volume when price touched the level
        - Volume ratio vs overall average
        - Volume trend at touches (increasing = stronger)
        - Touch count for level durability

        Args:
            df: DataFrame with OHLC and volume data
            level: Price level to analyze
            tolerance_pct: Percentage tolerance for touch detection

        Returns:
            Dict with volume strength metrics:
            - volume_strength: Composite score (0-100)
            - touch_count: Number of times price touched level
            - volume_ratio: Volume at touches vs average
            - volume_trend: Ratio of recent vs early touch volume
        """
        tolerance = level * tolerance_pct / 100

        # Find bars that touched this level
        touches = df[(df["low"] <= level + tolerance) & (df["high"] >= level - tolerance)]

        if len(touches) == 0:
            return {
                "volume_strength": 0.0,
                "touch_count": 0,
                "volume_ratio": 0.0,
                "volume_trend": 1.0,
            }

        # Calculate volume metrics
        avg_touch_volume = touches["volume"].mean() if "volume" in touches.columns else 0
        avg_total_volume = df["volume"].mean() if "volume" in df.columns else 1
        volume_ratio = avg_touch_volume / avg_total_volume if avg_total_volume > 0 else 1.0

        # Volume trend at touches (are later touches with higher volume?)
        if len(touches) >= 2:
            half_len = len(touches) // 2
            first_half_vol = (
                touches.head(half_len)["volume"].mean() if "volume" in touches.columns else 1
            )
            second_half_vol = (
                touches.tail(half_len)["volume"].mean() if "volume" in touches.columns else 1
            )
            volume_trend = second_half_vol / first_half_vol if first_half_vol > 0 else 1.0
        else:
            volume_trend = 1.0

        # Composite strength score (0-100)
        # Weight: 30% volume ratio, 50% touch count (capped at 10), 20% volume trend
        touch_factor = min(10, len(touches)) * 5  # 0-50 points
        volume_factor = min(30, volume_ratio * 30)  # 0-30 points
        trend_factor = min(20, volume_trend * 10)  # 0-20 points

        volume_strength = touch_factor + volume_factor + trend_factor

        return {
            "volume_strength": round(volume_strength, 2),
            "touch_count": len(touches),
            "volume_ratio": round(volume_ratio, 3),
            "volume_trend": round(volume_trend, 3),
        }

    def _compute_composite_strength(
        self,
        volume_strength: float,
        touch_count: int,
        distance_pct: float,
    ) -> float:
        """
        Compute composite strength score from multiple factors.

        Combines:
        - Volume strength (40% weight)
        - Touch count factor (30% weight)
        - Distance factor - closer = stronger (30% weight)

        Args:
            volume_strength: Volume-based strength score (0-100)
            touch_count: Number of touches at level
            distance_pct: Distance from current price as percentage

        Returns:
            Composite strength score (0-100)
        """
        # Closer levels are considered stronger (inverse of distance)
        distance_factor = max(0, 100 - distance_pct * 10)  # 0-100

        # Touch count factor (capped at 10 touches for max score)
        touch_factor = min(100, touch_count * 10)  # 0-100

        # Weighted composite
        composite = volume_strength * 0.4 + touch_factor * 0.3 + distance_factor * 0.3
        return round(composite, 2)

    def add_volume_strength_features(
        self,
        df: pd.DataFrame,
        sr_levels: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Add volume-based S/R strength features to DataFrame.

        Adds columns:
        - support_volume_strength: Volume strength at nearest support (0-100)
        - resistance_volume_strength: Volume strength at nearest resistance (0-100)
        - support_touches_count: Number of touches at support
        - resistance_touches_count: Number of touches at resistance
        - support_strength_score: Composite strength (volume + touches + distance)
        - resistance_strength_score: Composite strength

        Args:
            df: DataFrame with OHLC and volume data
            sr_levels: Pre-computed S/R levels (optional, will compute if not provided)

        Returns:
            DataFrame with volume strength features added
        """
        df = df.copy()

        # Get S/R levels if not provided
        if sr_levels is None:
            sr_levels = self.find_all_levels(df)

        nearest_support = sr_levels.get("nearest_support")
        nearest_resistance = sr_levels.get("nearest_resistance")
        support_dist_pct = sr_levels.get("support_distance_pct") or 100
        resistance_dist_pct = sr_levels.get("resistance_distance_pct") or 100

        # Calculate support volume strength
        if nearest_support:
            support_metrics = self.calculate_volume_strength(df, nearest_support)
            support_volume_strength = support_metrics["volume_strength"]
            support_touches = support_metrics["touch_count"]
        else:
            support_volume_strength = 0.0
            support_touches = 0

        # Calculate resistance volume strength
        if nearest_resistance:
            resistance_metrics = self.calculate_volume_strength(df, nearest_resistance)
            resistance_volume_strength = resistance_metrics["volume_strength"]
            resistance_touches = resistance_metrics["touch_count"]
        else:
            resistance_volume_strength = 0.0
            resistance_touches = 0

        # Add features (broadcast to all rows)
        df["support_volume_strength"] = support_volume_strength
        df["resistance_volume_strength"] = resistance_volume_strength
        df["support_touches_count"] = support_touches
        df["resistance_touches_count"] = resistance_touches

        # Compute composite strength scores
        df["support_strength_score"] = self._compute_composite_strength(
            support_volume_strength,
            support_touches,
            support_dist_pct,
        )
        df["resistance_strength_score"] = self._compute_composite_strength(
            resistance_volume_strength,
            resistance_touches,
            resistance_dist_pct,
        )

        logger.info(
            f"Added volume strength features: "
            f"support_strength={df['support_strength_score'].iloc[-1]:.1f}, "
            f"resistance_strength={df['resistance_strength_score'].iloc[-1]:.1f}"
        )

        return df


def add_support_resistance_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to add S/R features to a DataFrame.

    Args:
        df: DataFrame with OHLC data

    Returns:
        DataFrame with S/R features added
    """
    detector = SupportResistanceDetector()
    return detector.add_sr_features(df)
