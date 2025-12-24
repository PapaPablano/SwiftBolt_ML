"""
Support and Resistance Level Detection Module.

This module provides 5 methods for detecting support and resistance levels:
1. ZigZag - Filters noise, identifies significant swings
2. Local Extrema - Mathematical peaks/troughs using scipy
3. K-Means Clustering - Statistical price zones
4. Pivot Points - Classical standard levels
5. Fibonacci Retracement - Natural retracement levels

Usage:
    from src.features.support_resistance_detector import SupportResistanceDetector
    
    sr = SupportResistanceDetector()
    all_levels = sr.find_all_levels(df)
    
    # Access individual methods
    zigzag_df, swings = sr.zigzag(df, threshold_pct=5)
    pivots = sr.pivot_points_classical(df)
    fib_levels = sr.fibonacci_retracement(df)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

logger = logging.getLogger(__name__)


class SupportResistanceDetector:
    """
    Comprehensive support and resistance level detector.
    
    Combines multiple methods for robust S/R detection:
    - ZigZag: Best for intraday/swing trading, filters noise
    - Local Extrema: Mathematical peak/trough detection
    - K-Means Clustering: Statistical price zone identification
    - Pivot Points: Industry standard daily levels
    - Fibonacci: Natural retracement targets
    
    Attributes:
        default_zigzag_threshold: Default ZigZag threshold percentage
        default_extrema_order: Default order for local extrema detection
        default_n_clusters: Default number of clusters for K-Means
    """
    
    def __init__(
        self,
        default_zigzag_threshold: float = 5.0,
        default_extrema_order: int = 5,
        default_n_clusters: int = 5,
    ):
        """
        Initialize the SupportResistanceDetector.
        
        Args:
            default_zigzag_threshold: Default percentage threshold for ZigZag
            default_extrema_order: Default order for scipy argrelextrema
            default_n_clusters: Default number of clusters for K-Means
        """
        self.default_zigzag_threshold = default_zigzag_threshold
        self.default_extrema_order = default_extrema_order
        self.default_n_clusters = default_n_clusters
        
        logger.info(
            f"SupportResistanceDetector initialized: "
            f"zigzag_threshold={default_zigzag_threshold}%, "
            f"extrema_order={default_extrema_order}, "
            f"n_clusters={default_n_clusters}"
        )
    
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
                    swings.append({
                        "type": "high",
                        "price": float(last_pivot_price),
                        "index": last_pivot_idx,
                        "ts": ts,
                    })
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
                    swings.append({
                        "type": "low",
                        "price": float(last_pivot_price),
                        "index": last_pivot_idx,
                        "ts": ts,
                    })
                    # Start looking for high
                    direction = 1
                    last_pivot_price = prices[i]
                    last_pivot_idx = i
        
        # Mark the last pivot
        zigzag[last_pivot_idx] = last_pivot_price
        ts = df["ts"].iloc[last_pivot_idx] if "ts" in df.columns else last_pivot_idx
        swings.append({
            "type": "high" if direction == 1 else "low",
            "price": float(last_pivot_price),
            "index": last_pivot_idx,
            "ts": ts,
        })
        
        df["zigzag"] = zigzag
        
        # Extract support and resistance from swings
        highs = [s["price"] for s in swings if s["type"] == "high"]
        lows = [s["price"] for s in swings if s["type"] == "low"]
        
        logger.info(
            f"ZigZag: {len(swings)} swings detected "
            f"({len(highs)} highs, {len(lows)} lows)"
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
        
        logger.info(
            f"Local Extrema: {len(local_maxima)} maxima, {len(local_minima)} minima"
        )
        
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
                name: round(range_high - diff * ratio, 2)
                for name, ratio in fib_ratios.items()
            }
        else:
            # In downtrend, retracements are measured from low
            levels = {
                name: round(range_low + diff * ratio, 2)
                for name, ratio in fib_ratios.items()
            }
        
        logger.info(
            f"Fibonacci: {trend}, range={range_low:.2f}-{range_high:.2f}"
        )
        
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
    ) -> Dict[str, Any]:
        """
        Find all support and resistance levels using all methods.
        
        Combines results from all 5 methods and identifies the
        nearest support and resistance to current price.
        
        Args:
            df: DataFrame with OHLC data
            zigzag_threshold: ZigZag threshold percentage
            extrema_order: Order for local extrema detection
            n_clusters: Number of K-Means clusters
            fib_lookback: Lookback for Fibonacci calculation
            
        Returns:
            Comprehensive dict with all S/R levels and analysis
        """
        current_price = df["close"].iloc[-1]
        
        # Run all methods
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
        supports_below = sorted(
            [s for s in all_supports if s < current_price],
            reverse=True
        )
        resistances_above = sorted(
            [r for r in all_resistances if r > current_price]
        )
        
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
            "support_distance_pct": round(support_distance_pct, 2) if support_distance_pct else None,
            "resistance_distance_pct": round(resistance_distance_pct, 2) if resistance_distance_pct else None,
            "all_supports": supports_below[:10],  # Top 10 nearest
            "all_resistances": resistances_above[:10],  # Top 10 nearest
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
            f"S/R Analysis: price={current_price:.2f}, "
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
            df["distance_to_support_pct"] = (
                (df["close"] - nearest_support) / df["close"] * 100
            )
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
        pivots = levels["methods"]["pivot_points"]
        df["pivot_pp"] = pivots.get("PP", np.nan)
        
        # Price position relative to pivot
        if "PP" in pivots:
            df["price_vs_pivot_pct"] = (df["close"] - pivots["PP"]) / pivots["PP"] * 100
        else:
            df["price_vs_pivot_pct"] = np.nan
        
        # Fibonacci levels
        fib = levels["methods"]["fibonacci"]
        fib_levels = list(fib["levels"].values())
        
        # Find nearest Fibonacci level
        if fib_levels:
            nearest_fib = min(fib_levels, key=lambda x: abs(x - current_price))
            df["fib_nearest"] = nearest_fib
            df["distance_to_fib_pct"] = (df["close"] - nearest_fib) / df["close"] * 100
        else:
            df["fib_nearest"] = np.nan
            df["distance_to_fib_pct"] = np.nan
        
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
        touches = df[
            (df["low"] <= level + tolerance) & 
            (df["high"] >= level - tolerance)
        ]
        
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
