"""
Unit tests for enhanced SuperTrend AI with signal metadata and confidence.

Tests cover:
- Basic SuperTrend calculation
- K-means clustering for factor selection
- Signal metadata extraction
- Confidence score calculation
- Current state retrieval
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from src.strategies.supertrend_ai import SuperTrendAI  # noqa: E402


class TestSuperTrendAIBasics:
    """Test basic SuperTrend AI functionality."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data for testing."""
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        # Generate trending data with some volatility
        base_price = 100
        returns = np.random.randn(n) * 0.02
        close = base_price * np.cumprod(1 + returns)

        high = close * (1 + np.abs(np.random.randn(n)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(n)) * 0.01)
        open_price = close * (1 + np.random.randn(n) * 0.005)
        volume = np.random.randint(1000000, 10000000, n)

        return pd.DataFrame(
            {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=dates,
        )

    def test_initialization(self, sample_data):
        """Test SuperTrendAI initialization."""
        st = SuperTrendAI(sample_data)

        assert st.atr_length == 10
        assert st.min_mult == 1.0
        assert st.max_mult == 5.0
        assert st.step == 0.5
        assert len(st.factors) == 9  # 1.0 to 5.0 step 0.5

    def test_initialization_custom_params(self, sample_data):
        """Test SuperTrendAI with custom parameters."""
        st = SuperTrendAI(
            sample_data,
            atr_length=14,
            min_mult=2.0,
            max_mult=4.0,
            step=1.0,
        )

        assert st.atr_length == 14
        assert st.min_mult == 2.0
        assert st.max_mult == 4.0
        assert len(st.factors) == 3  # 2.0, 3.0, 4.0

    def test_invalid_multiplier_range(self, sample_data):
        """Test that invalid multiplier range raises error."""
        with pytest.raises(ValueError):
            SuperTrendAI(sample_data, min_mult=5.0, max_mult=1.0)


class TestSuperTrendCalculation:
    """Test SuperTrend calculation methods."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        close = 100 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_calculate_returns_dataframe(self, sample_data):
        """Test that calculate returns proper DataFrame."""
        st = SuperTrendAI(sample_data)
        result_df, info = st.calculate()

        assert "supertrend" in result_df.columns
        assert "supertrend_trend" in result_df.columns
        assert "supertrend_signal" in result_df.columns
        assert "perf_ama" in result_df.columns
        assert "signal_confidence" in result_df.columns
        assert "atr" in result_df.columns

    def test_supertrend_values_valid(self, sample_data):
        """Test that SuperTrend values are valid."""
        st = SuperTrendAI(sample_data)
        result_df, _ = st.calculate()

        # SuperTrend should be positive
        assert (result_df["supertrend"] > 0).all()

        # Trend should be 0 or 1
        assert result_df["supertrend_trend"].isin([0, 1]).all()

    def test_signals_generated(self, sample_data):
        """Test that signals are generated on trend changes."""
        st = SuperTrendAI(sample_data)
        result_df, info = st.calculate()

        # Should have some signals
        signals = result_df[result_df["supertrend_signal"] != 0]
        assert len(signals) > 0

        # Signals should be -1 or 1
        assert signals["supertrend_signal"].isin([-1, 1]).all()


class TestInfoDict:
    """Test the info dictionary returned by calculate()."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        close = 100 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_info_contains_required_fields(self, sample_data):
        """Test that info dict contains all required fields."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        required_fields = [
            "target_factor",
            "performance_index",
            "signal_strength",
            "cluster_mapping",
            "factors_tested",
            "performances",
            "signals",
            "current_trend",
            "current_stop_level",
            "trend_duration_bars",
            "total_signals",
            "buy_signals",
            "sell_signals",
        ]

        for field in required_fields:
            assert field in info, f"Missing field: {field}"

    def test_performance_index_range(self, sample_data):
        """Test that performance index is in valid range."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        assert 0 <= info["performance_index"] <= 1

    def test_signal_strength_range(self, sample_data):
        """Test that signal strength is in valid range."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        assert 0 <= info["signal_strength"] <= 10

    def test_current_trend_valid(self, sample_data):
        """Test that current trend is valid."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        assert info["current_trend"] in ["BULLISH", "BEARISH"]


class TestSignalMetadata:
    """Test signal metadata extraction."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data with clear trend changes."""
        np.random.seed(42)
        n = 200

        # Create data with clear up and down trends
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        # Uptrend then downtrend pattern
        close = np.concatenate(
            [
                100 + np.arange(50) * 0.5,  # Uptrend
                125 - np.arange(50) * 0.5,  # Downtrend
                100 + np.arange(50) * 0.3,  # Uptrend
                115 - np.arange(50) * 0.3,  # Downtrend
            ]
        )

        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_signals_have_required_fields(self, sample_data):
        """Test that each signal has required metadata fields."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        required_fields = [
            "date",
            "type",
            "price",
            "confidence",
            "stop_level",
            "target_price",
            "atr_at_signal",
            "risk_amount",
            "reward_amount",
        ]

        for signal in info["signals"]:
            for field in required_fields:
                assert field in signal, f"Missing field: {field}"

    def test_signal_types_valid(self, sample_data):
        """Test that signal types are valid."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        for signal in info["signals"]:
            assert signal["type"] in ["BUY", "SELL"]

    def test_confidence_range(self, sample_data):
        """Test that confidence scores are in valid range."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        for signal in info["signals"]:
            assert 0 <= signal["confidence"] <= 10

    def test_stop_level_valid(self, sample_data):
        """Test that stop levels are valid."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        for signal in info["signals"]:
            assert signal["stop_level"] > 0
            # For BUY, stop should be below price
            # For SELL, stop should be above price
            if signal["type"] == "BUY":
                assert signal["stop_level"] < signal["price"]
            else:
                assert signal["stop_level"] > signal["price"]

    def test_target_price_valid(self, sample_data):
        """Test that target prices are calculated correctly."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        for signal in info["signals"]:
            # Default risk:reward is 2:1
            expected_reward = signal["risk_amount"] * 2
            assert abs(signal["reward_amount"] - expected_reward) < 0.01


class TestKMeansClustering:
    """Test K-means clustering functionality."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 200
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        close = 100 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_cluster_mapping_has_all_clusters(self, sample_data):
        """Test that cluster mapping contains all three clusters."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        cluster_values = set(info["cluster_mapping"].values())
        assert "Best" in cluster_values
        assert "Average" in cluster_values
        assert "Worst" in cluster_values

    def test_target_factor_in_range(self, sample_data):
        """Test that target factor is within specified range."""
        st = SuperTrendAI(sample_data)
        _, info = st.calculate()

        assert st.min_mult <= info["target_factor"] <= st.max_mult

    def test_from_cluster_selection(self, sample_data):
        """Test that from_cluster parameter works."""
        # Test with 'Best' cluster (default)
        st_best = SuperTrendAI(sample_data, from_cluster="Best")
        _, info_best = st_best.calculate()

        # Test with 'Average' cluster
        st_avg = SuperTrendAI(sample_data, from_cluster="Average")
        _, info_avg = st_avg.calculate()

        # Factors should be different (usually)
        # Note: They could be the same in edge cases
        assert info_best["target_factor"] is not None
        assert info_avg["target_factor"] is not None


class TestCurrentState:
    """Test current state retrieval."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        close = 100 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_get_current_state_after_calculate(self, sample_data):
        """Test get_current_state returns valid data after calculate."""
        st = SuperTrendAI(sample_data)
        st.calculate()
        state = st.get_current_state()

        assert "current_trend" in state
        assert "current_stop_level" in state
        assert "trend_duration_bars" in state
        assert "current_price" in state
        assert "distance_to_stop_pct" in state

    def test_current_state_values_valid(self, sample_data):
        """Test that current state values are valid."""
        st = SuperTrendAI(sample_data)
        st.calculate()
        state = st.get_current_state()

        assert state["current_trend"] in ["BULLISH", "BEARISH"]
        assert state["current_stop_level"] > 0
        assert state["trend_duration_bars"] >= 0
        assert state["current_price"] > 0
        assert state["distance_to_stop_pct"] >= 0


class TestPredict:
    """Test predict method for applying pre-fitted factor."""

    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="D")

        close = 100 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n))
        low = close - np.abs(np.random.randn(n))

        return pd.DataFrame(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(1000000, 10000000, n),
            },
            index=dates,
        )

    def test_predict_with_factor(self, sample_data):
        """Test predict method with a specific factor."""
        st = SuperTrendAI(sample_data)

        # First calculate to get optimal factor
        _, info = st.calculate()
        target_factor = info["target_factor"]

        # Create new data
        new_data = sample_data.copy()
        new_data["close"] = new_data["close"] * 1.1  # Simulate price change

        # Predict with the fitted factor
        result = st.predict(new_data, target_factor)

        assert "supertrend" in result.columns
        assert "supertrend_trend" in result.columns
        assert "supertrend_signal" in result.columns
        assert "atr" in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
