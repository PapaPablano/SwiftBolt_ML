"""
Unit tests for Support and Resistance Level Detection.

Tests all 5 methods:
1. ZigZag
2. Local Extrema
3. K-Means Clustering
4. Pivot Points
5. Fibonacci Retracement
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.support_resistance_detector import (
    SupportResistanceDetector,
    add_support_resistance_features,
)


def generate_sample_ohlc(
    n_bars: int = 100,
    start_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0001,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate sample OHLC data for testing."""
    np.random.seed(seed)

    dates = [datetime.now() - timedelta(days=n_bars - i) for i in range(n_bars)]
    returns = np.random.normal(trend, volatility, n_bars)

    close = start_price * np.cumprod(1 + returns)
    high = close * (1 + np.abs(np.random.normal(0, volatility / 2, n_bars)))
    low = close * (1 - np.abs(np.random.normal(0, volatility / 2, n_bars)))
    open_price = (close + np.roll(close, 1)) / 2
    open_price[0] = start_price
    volume = np.random.randint(1000000, 10000000, n_bars)

    return pd.DataFrame(
        {
            "ts": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def generate_trending_data(
    n_bars: int = 100,
    start_price: float = 100.0,
    direction: str = "up",
) -> pd.DataFrame:
    """Generate trending OHLC data with clear swings."""
    np.random.seed(42)

    dates = [datetime.now() - timedelta(days=n_bars - i) for i in range(n_bars)]

    if direction == "up":
        base_trend = np.linspace(0, 0.3, n_bars)
    else:
        base_trend = np.linspace(0, -0.3, n_bars)

    noise = np.sin(np.linspace(0, 8 * np.pi, n_bars)) * 0.05
    close = start_price * (1 + base_trend + noise)

    high = close * 1.01
    low = close * 0.99
    open_price = np.roll(close, 1)
    open_price[0] = start_price
    volume = np.random.randint(1000000, 10000000, n_bars)

    return pd.DataFrame(
        {
            "ts": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


class TestSupportResistanceDetector:
    """Test suite for SupportResistanceDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        return SupportResistanceDetector()

    @pytest.fixture
    def sample_df(self):
        """Generate sample OHLC data."""
        return generate_sample_ohlc(n_bars=100)

    @pytest.fixture
    def trending_df(self):
        """Generate trending OHLC data."""
        return generate_trending_data(n_bars=100, direction="up")

    # =========================================================================
    # ZIGZAG TESTS
    # =========================================================================

    def test_zigzag_basic(self, detector, sample_df):
        """Test basic ZigZag functionality."""
        df, swings = detector.zigzag(sample_df, threshold_pct=3)

        assert "zigzag" in df.columns
        assert len(swings) > 0
        assert all(s["type"] in ["high", "low"] for s in swings)
        assert all("price" in s for s in swings)
        assert all("index" in s for s in swings)

    def test_zigzag_alternating_swings(self, detector, trending_df):
        """Test that ZigZag produces alternating highs and lows."""
        _, swings = detector.zigzag(trending_df, threshold_pct=2)

        if len(swings) >= 2:
            for i in range(1, len(swings)):
                assert (
                    swings[i]["type"] != swings[i - 1]["type"]
                ), "Swings should alternate between high and low"

    def test_zigzag_threshold_sensitivity(self, detector, sample_df):
        """Test that higher threshold produces fewer swings."""
        _, swings_low = detector.zigzag(sample_df, threshold_pct=2)
        _, swings_high = detector.zigzag(sample_df, threshold_pct=10)

        assert len(swings_low) >= len(swings_high), "Higher threshold should produce fewer swings"

    def test_zigzag_empty_df(self, detector):
        """Test ZigZag with minimal data."""
        df = pd.DataFrame(
            {
                "ts": [datetime.now()],
                "close": [100.0],
            }
        )
        result_df, swings = detector.zigzag(df)
        assert len(swings) == 0

    # =========================================================================
    # LOCAL EXTREMA TESTS
    # =========================================================================

    def test_local_extrema_basic(self, detector, sample_df):
        """Test basic local extrema detection."""
        result = detector.local_extrema(sample_df, order=5)

        assert "local_maxima" in result
        assert "local_minima" in result
        assert "resistance_levels" in result
        assert "support_levels" in result

    def test_local_extrema_maxima_above_minima(self, detector, sample_df):
        """Test that maxima are generally above minima."""
        result = detector.local_extrema(sample_df, order=5)

        if result["local_maxima"] and result["local_minima"]:
            avg_max = np.mean([p for _, p in result["local_maxima"]])
            avg_min = np.mean([p for _, p in result["local_minima"]])
            assert avg_max > avg_min, "Average maxima should be above minima"

    def test_local_extrema_order_sensitivity(self, detector, sample_df):
        """Test that higher order produces fewer extrema."""
        result_low = detector.local_extrema(sample_df, order=3)
        result_high = detector.local_extrema(sample_df, order=10)

        assert len(result_low["local_maxima"]) >= len(result_high["local_maxima"])

    # =========================================================================
    # K-MEANS CLUSTERING TESTS
    # =========================================================================

    def test_kmeans_basic(self, detector, sample_df):
        """Test basic K-Means clustering."""
        result = detector.kmeans_clustering(sample_df, n_clusters=5)

        assert "cluster_centers" in result
        assert "support_zones" in result
        assert "resistance_zones" in result
        assert len(result["cluster_centers"]) == 5

    def test_kmeans_zones_classification(self, detector, sample_df):
        """Test that zones are correctly classified as support/resistance."""
        result = detector.kmeans_clustering(sample_df, n_clusters=5)
        current_price = sample_df["close"].iloc[-1]

        for zone in result["support_zones"]:
            assert zone < current_price, "Support zones should be below price"

        for zone in result["resistance_zones"]:
            assert zone > current_price, "Resistance zones should be above price"

    def test_kmeans_cluster_count(self, detector, sample_df):
        """Test different cluster counts."""
        for n in [3, 5, 7]:
            result = detector.kmeans_clustering(sample_df, n_clusters=n)
            assert len(result["cluster_centers"]) == n

    # =========================================================================
    # PIVOT POINTS TESTS
    # =========================================================================

    def test_pivot_points_classical(self, detector, sample_df):
        """Test classical pivot point calculation."""
        pivots = detector.pivot_points_classical(sample_df)

        assert "PP" in pivots
        assert "R1" in pivots
        assert "R2" in pivots
        assert "R3" in pivots
        assert "S1" in pivots
        assert "S2" in pivots
        assert "S3" in pivots

    def test_pivot_points_ordering(self, detector, sample_df):
        """Test that pivot levels are correctly ordered."""
        pivots = detector.pivot_points_classical(sample_df)

        assert pivots["S3"] < pivots["S2"] < pivots["S1"]
        assert pivots["R1"] < pivots["R2"] < pivots["R3"]
        assert pivots["S1"] < pivots["PP"] < pivots["R1"]

    def test_pivot_points_formula(self, detector):
        """Test pivot point formula with known values."""
        df = pd.DataFrame(
            {
                "high": [110.0],
                "low": [90.0],
                "close": [100.0],
            }
        )
        pivots = detector.pivot_points_classical(df)

        expected_pp = (110 + 90 + 100) / 3
        assert abs(pivots["PP"] - expected_pp) < 0.01

        expected_r1 = 2 * expected_pp - 90
        assert abs(pivots["R1"] - expected_r1) < 0.01

        expected_s1 = 2 * expected_pp - 110
        assert abs(pivots["S1"] - expected_s1) < 0.01

    def test_pivot_points_from_range(self, detector, sample_df):
        """Test pivot points calculated from range."""
        pivots = detector.pivot_points_from_range(sample_df, lookback=20)

        assert "PP" in pivots
        assert "period_high" in pivots
        assert "period_low" in pivots
        assert pivots["period_high"] > pivots["period_low"]

    # =========================================================================
    # FIBONACCI RETRACEMENT TESTS
    # =========================================================================

    def test_fibonacci_basic(self, detector, sample_df):
        """Test basic Fibonacci retracement."""
        result = detector.fibonacci_retracement(sample_df, lookback=50)

        assert "levels" in result
        assert "trend" in result
        assert "range_high" in result
        assert "range_low" in result

    def test_fibonacci_levels(self, detector, sample_df):
        """Test that all standard Fibonacci levels are present."""
        result = detector.fibonacci_retracement(sample_df)
        levels = result["levels"]

        expected_keys = ["0.0", "23.6", "38.2", "50.0", "61.8", "78.6", "100.0"]
        for key in expected_keys:
            assert key in levels, f"Missing Fibonacci level: {key}"

    def test_fibonacci_level_ordering_uptrend(self, detector):
        """Test Fibonacci level ordering in uptrend."""
        df = generate_trending_data(n_bars=50, direction="up")
        result = detector.fibonacci_retracement(df)

        if result["trend"] == "uptrend":
            levels = result["levels"]
            assert levels["0.0"] > levels["100.0"], "In uptrend, 0% should be at high"

    def test_fibonacci_level_ordering_downtrend(self, detector):
        """Test Fibonacci level ordering in downtrend."""
        df = generate_trending_data(n_bars=50, direction="down")
        result = detector.fibonacci_retracement(df)

        if result["trend"] == "downtrend":
            levels = result["levels"]
            assert levels["100.0"] > levels["0.0"], "In downtrend, 100% should be at high"

    # =========================================================================
    # COMBINED ANALYSIS TESTS
    # =========================================================================

    def test_find_all_levels(self, detector, sample_df):
        """Test combined S/R level detection."""
        result = detector.find_all_levels(sample_df)

        assert "current_price" in result
        assert "nearest_support" in result
        assert "nearest_resistance" in result
        assert "all_supports" in result
        assert "all_resistances" in result
        assert "methods" in result

    def test_find_all_levels_nearest(self, detector, sample_df):
        """Test that nearest levels are correctly identified."""
        result = detector.find_all_levels(sample_df)
        current = result["current_price"]

        if result["nearest_support"]:
            assert result["nearest_support"] < current
            for s in result["all_supports"]:
                assert s <= result["nearest_support"] or s >= current

        if result["nearest_resistance"]:
            assert result["nearest_resistance"] > current
            for r in result["all_resistances"]:
                assert r >= result["nearest_resistance"] or r <= current

    def test_find_all_levels_methods_present(self, detector, sample_df):
        """Test that all method results are included."""
        result = detector.find_all_levels(sample_df)
        methods = result["methods"]

        assert "zigzag" in methods
        assert "local_extrema" in methods
        assert "kmeans" in methods
        assert "pivot_points" in methods
        assert "fibonacci" in methods

    # =========================================================================
    # FEATURE ENGINEERING TESTS
    # =========================================================================

    def test_add_sr_features(self, detector, sample_df):
        """Test S/R feature addition."""
        result_df = detector.add_sr_features(sample_df)

        expected_cols = [
            "distance_to_support_pct",
            "distance_to_resistance_pct",
            "sr_ratio",
            "pivot_pp",
        ]
        for col in expected_cols:
            assert col in result_df.columns, f"Missing feature: {col}"

    def test_add_sr_features_values(self, detector, sample_df):
        """Test S/R feature values are reasonable."""
        result_df = detector.add_sr_features(sample_df)

        support_dist = result_df["distance_to_support_pct"].iloc[-1]
        if not pd.isna(support_dist):
            assert support_dist >= 0, "Distance to support should be positive"

        resistance_dist = result_df["distance_to_resistance_pct"].iloc[-1]
        if not pd.isna(resistance_dist):
            assert resistance_dist >= 0, "Distance to resistance should be positive"

    # =========================================================================
    # LEVEL STRENGTH TESTS
    # =========================================================================

    def test_level_strength(self, detector, sample_df):
        """Test level strength calculation."""
        current_price = sample_df["close"].iloc[-1]
        result = detector.get_level_strength(sample_df, current_price, tolerance_pct=2)

        assert "level" in result
        assert "n_touches" in result
        assert "strength" in result
        assert result["strength"] >= 0

    def test_level_strength_more_touches(self, detector):
        """Test that more touches increase strength."""
        df = pd.DataFrame(
            {
                "ts": [datetime.now() - timedelta(days=i) for i in range(20)],
                "high": [102] * 20,
                "low": [98] * 20,
                "close": [100] * 20,
                "volume": [1000000] * 20,
            }
        )

        result = detector.get_level_strength(df, 100.0, tolerance_pct=3)
        assert result["n_touches"] == 20


class TestConvenienceFunction:
    """Test the convenience function."""

    def test_add_support_resistance_features(self):
        """Test the module-level convenience function."""
        df = generate_sample_ohlc(n_bars=100)
        result_df = add_support_resistance_features(df)

        assert "distance_to_support_pct" in result_df.columns
        assert "distance_to_resistance_pct" in result_df.columns


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def detector(self):
        return SupportResistanceDetector()

    def test_small_dataset(self, detector):
        """Test with very small dataset."""
        df = pd.DataFrame(
            {
                "ts": [datetime.now()],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000000],
            }
        )

        pivots = detector.pivot_points_classical(df)
        assert "PP" in pivots

    def test_constant_prices(self, detector):
        """Test with constant prices (no volatility)."""
        df = pd.DataFrame(
            {
                "ts": [datetime.now() - timedelta(days=i) for i in range(50)],
                "open": [100.0] * 50,
                "high": [100.0] * 50,
                "low": [100.0] * 50,
                "close": [100.0] * 50,
                "volume": [1000000] * 50,
            }
        )

        result = detector.find_all_levels(df)
        assert result["current_price"] == 100.0

    def test_extreme_volatility(self, detector):
        """Test with extreme price swings."""
        np.random.seed(42)
        n = 100
        close = 100 * np.cumprod(1 + np.random.uniform(-0.1, 0.1, n))

        df = pd.DataFrame(
            {
                "ts": [datetime.now() - timedelta(days=i) for i in range(n)],
                "open": close * 0.99,
                "high": close * 1.05,
                "low": close * 0.95,
                "close": close,
                "volume": [1000000] * n,
            }
        )

        result = detector.find_all_levels(df)
        assert "nearest_support" in result
        assert "nearest_resistance" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
