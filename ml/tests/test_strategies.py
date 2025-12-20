"""Unit tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

from src.features.technical_indicators import add_all_technical_features
from src.strategies.multi_indicator_signals import MultiIndicatorSignalGenerator
from src.strategies.supertrend_ai import SuperTrendAI


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 200  # Need enough data for SuperTrend AI clustering

    # Generate trending price data
    base_price = 100.0
    trend = np.linspace(0, 0.3, n)  # 30% uptrend
    noise = np.random.randn(n) * 0.01
    prices = base_price * (1 + trend + np.cumsum(noise))

    df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n) * 0.01)),
            "low": prices * (1 - np.abs(np.random.randn(n) * 0.01)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, n).astype(float),
        }
    )

    # Ensure high >= close >= low
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


class TestSuperTrendAI:
    """Test SuperTrend AI strategy."""

    def test_supertrend_initialization(self, sample_ohlc_df):
        """Test SuperTrend AI initialization."""
        st = SuperTrendAI(sample_ohlc_df)

        assert st.atr_length == 10
        assert st.min_mult == 1.0
        assert st.max_mult == 5.0
        assert st.from_cluster == "Best"
        assert len(st.factors) > 0

    def test_supertrend_calculate(self, sample_ohlc_df):
        """Test SuperTrend AI calculation."""
        st = SuperTrendAI(sample_ohlc_df)
        result_df, info = st.calculate()

        # Check result DataFrame has expected columns
        assert "supertrend" in result_df.columns
        assert "supertrend_trend" in result_df.columns
        assert "supertrend_signal" in result_df.columns
        assert "perf_ama" in result_df.columns

        # Check info dict has expected keys
        assert "target_factor" in info
        assert "performance_index" in info
        assert "signal_strength" in info

        # Check values are reasonable
        assert 1.0 <= info["target_factor"] <= 5.0
        assert 0 <= info["performance_index"] <= 1
        assert 0 <= info["signal_strength"] <= 10

    def test_supertrend_trend_values(self, sample_ohlc_df):
        """Test that trend values are 0 or 1."""
        st = SuperTrendAI(sample_ohlc_df)
        result_df, _ = st.calculate()

        trend_values = result_df["supertrend_trend"].unique()
        assert all(t in [0, 1] for t in trend_values)

    def test_supertrend_signal_values(self, sample_ohlc_df):
        """Test that signal values are -1, 0, or 1."""
        st = SuperTrendAI(sample_ohlc_df)
        result_df, _ = st.calculate()

        signal_values = result_df["supertrend_signal"].unique()
        assert all(s in [-1, 0, 1] for s in signal_values)

    def test_supertrend_predict(self, sample_ohlc_df):
        """Test SuperTrend predict with pre-determined factor."""
        st = SuperTrendAI(sample_ohlc_df)
        result_df = st.predict(sample_ohlc_df, target_factor=2.5)

        assert "supertrend" in result_df.columns
        assert "supertrend_trend" in result_df.columns
        assert "supertrend_signal" in result_df.columns

    def test_supertrend_invalid_multipliers(self, sample_ohlc_df):
        """Test that invalid multiplier range raises error."""
        with pytest.raises(ValueError):
            SuperTrendAI(sample_ohlc_df, min_mult=5.0, max_mult=1.0)


class TestMultiIndicatorSignalGenerator:
    """Test Multi-Indicator Signal Generator."""

    def test_signal_generator_initialization(self):
        """Test signal generator initialization."""
        gen = MultiIndicatorSignalGenerator()

        assert len(gen.indicator_weights) > 0
        assert gen.buy_threshold == 0.3
        assert gen.sell_threshold == -0.3

    def test_signal_generator_custom_weights(self):
        """Test signal generator with custom weights."""
        custom_weights = {"rsi": 0.5, "macd": 0.5}
        gen = MultiIndicatorSignalGenerator(indicator_weights=custom_weights)

        assert gen.indicator_weights == custom_weights

    def test_generate_signal_structure(self, sample_ohlc_df):
        """Test generate_signal returns expected structure."""
        df = add_all_technical_features(sample_ohlc_df)

        gen = MultiIndicatorSignalGenerator()
        result = gen.generate_signal(df)

        assert "signal" in result
        assert "confidence" in result
        assert "composite_score" in result
        assert "components" in result

        assert result["signal"] in ["Buy", "Sell", "Hold"]
        assert 0 <= result["confidence"] <= 1
        assert -1 <= result["composite_score"] <= 1

    def test_generate_signal_with_supertrend(self, sample_ohlc_df):
        """Test signal generation with SuperTrend data."""
        # Add all indicators
        df = add_all_technical_features(sample_ohlc_df)

        # Add SuperTrend
        st = SuperTrendAI(df)
        df, _ = st.calculate()

        gen = MultiIndicatorSignalGenerator()
        result = gen.generate_signal(df)

        # SuperTrend should be in components
        assert "supertrend" in result["components"]

    def test_generate_signal_series(self, sample_ohlc_df):
        """Test generating signal series for entire DataFrame."""
        df = add_all_technical_features(sample_ohlc_df)

        gen = MultiIndicatorSignalGenerator()
        result_df = gen.generate_signal_series(df)

        assert len(result_df) == len(df)
        assert "signal" in result_df.columns
        assert "confidence" in result_df.columns
        assert "composite_score" in result_df.columns

    def test_get_trend_analysis(self, sample_ohlc_df):
        """Test trend analysis function."""
        df = add_all_technical_features(sample_ohlc_df)

        gen = MultiIndicatorSignalGenerator()
        analysis = gen.get_trend_analysis(df)

        assert "trend" in analysis
        assert "composite_signal" in analysis
        assert "confidence" in analysis
        assert analysis["trend"] in ["bullish", "bearish", "neutral"]

    def test_signal_thresholds(self, sample_ohlc_df):
        """Test that signals respect thresholds."""
        df = add_all_technical_features(sample_ohlc_df)

        gen = MultiIndicatorSignalGenerator(buy_threshold=0.3, sell_threshold=-0.3)
        result = gen.generate_signal(df)

        score = result["composite_score"]
        signal = result["signal"]

        if signal == "Buy":
            assert score > 0.3
        elif signal == "Sell":
            assert score < -0.3
        else:
            assert -0.3 <= score <= 0.3


class TestIntegration:
    """Integration tests for strategies."""

    def test_full_pipeline(self, sample_ohlc_df):
        """Test full pipeline: indicators -> SuperTrend -> signals."""
        # 1. Add all technical indicators
        df = add_all_technical_features(sample_ohlc_df)

        # 2. Add SuperTrend AI
        st = SuperTrendAI(df)
        df, st_info = st.calculate()

        # 3. Generate signals
        gen = MultiIndicatorSignalGenerator()
        signal = gen.generate_signal(df)

        # 4. Get trend analysis
        analysis = gen.get_trend_analysis(df)

        # Verify all components work together
        assert st_info["target_factor"] > 0
        assert signal["signal"] in ["Buy", "Sell", "Hold"]
        assert analysis["trend"] in ["bullish", "bearish", "neutral"]

        # SuperTrend should align with overall trend in trending data
        latest_trend = df["supertrend_trend"].iloc[-1]
        if signal["signal"] == "Buy" and signal["confidence"] > 0.5:
            # High confidence buy should align with bullish SuperTrend
            assert latest_trend == 1 or analysis["composite_signal"] > 0


class TestEdgeCases:
    """Test edge cases for strategies."""

    def test_supertrend_insufficient_data(self):
        """Test SuperTrend with insufficient data."""
        df = pd.DataFrame(
            {
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.0] * 5,
                "volume": [1000000.0] * 5,
            }
        )

        st = SuperTrendAI(df)
        result_df, info = st.calculate()

        # Should handle gracefully
        assert len(result_df) == 5

    def test_signal_generator_missing_columns(self):
        """Test signal generator with missing indicator columns."""
        df = pd.DataFrame(
            {
                "close": [100.0] * 10,
                "rsi_14": [50.0] * 10,
            }
        )

        gen = MultiIndicatorSignalGenerator()
        result = gen.generate_signal(df)

        # Should still work with available indicators
        assert "signal" in result
        assert result["signal"] in ["Buy", "Sell", "Hold"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
