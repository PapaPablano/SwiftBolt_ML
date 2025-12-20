"""Unit tests for multi-timeframe feature engineering."""

import numpy as np
import pandas as pd
import pytest

from src.features.multi_timeframe import (
    DEFAULT_TIMEFRAMES,
    MultiTimeframeFeatures,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 100

    base_price = 100.0
    returns = np.random.randn(n) * 0.02
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": prices * (1 + np.random.randn(n) * 0.005),
        "high": prices * (1 + np.abs(np.random.randn(n) * 0.01)),
        "low": prices * (1 - np.abs(np.random.randn(n) * 0.01)),
        "close": prices,
        "volume": np.random.randint(1000000, 10000000, n).astype(float),
    })

    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def sample_hourly_df():
    """Create sample hourly OHLC data."""
    np.random.seed(43)
    n = 500  # ~20 days of hourly data

    base_price = 100.0
    returns = np.random.randn(n) * 0.005
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": prices * (1 + np.random.randn(n) * 0.002),
        "high": prices * (1 + np.abs(np.random.randn(n) * 0.003)),
        "low": prices * (1 - np.abs(np.random.randn(n) * 0.003)),
        "close": prices,
        "volume": np.random.randint(100000, 1000000, n).astype(float),
    })

    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def sample_15min_df():
    """Create sample 15-minute OHLC data."""
    np.random.seed(44)
    n = 2000  # ~20 days of 15-min data

    base_price = 100.0
    returns = np.random.randn(n) * 0.001
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": prices * (1 + np.random.randn(n) * 0.001),
        "high": prices * (1 + np.abs(np.random.randn(n) * 0.002)),
        "low": prices * (1 - np.abs(np.random.randn(n) * 0.002)),
        "close": prices,
        "volume": np.random.randint(10000, 100000, n).astype(float),
    })

    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def sample_weekly_df():
    """Create sample weekly OHLC data."""
    np.random.seed(45)
    n = 52  # 1 year of weekly data

    base_price = 100.0
    returns = np.random.randn(n) * 0.03
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="W"),
        "open": prices * (1 + np.random.randn(n) * 0.01),
        "high": prices * (1 + np.abs(np.random.randn(n) * 0.02)),
        "low": prices * (1 - np.abs(np.random.randn(n) * 0.02)),
        "close": prices,
        "volume": np.random.randint(5000000, 50000000, n).astype(float),
    })

    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


class TestMultiTimeframeFeatures:
    """Test MultiTimeframeFeatures class."""

    def test_initialization_default(self):
        """Test default initialization."""
        mtf = MultiTimeframeFeatures()

        assert mtf.timeframes == DEFAULT_TIMEFRAMES
        assert mtf.indicators_func is not None

    def test_initialization_custom_timeframes(self):
        """Test initialization with custom timeframes."""
        custom_tf = ["d1", "w1"]
        mtf = MultiTimeframeFeatures(timeframes=custom_tf)

        assert mtf.timeframes == custom_tf

    def test_compute_single_timeframe(self, sample_ohlc_df):
        """Test computing indicators for a single timeframe."""
        mtf = MultiTimeframeFeatures()
        result = mtf.compute_single_timeframe(sample_ohlc_df, "d1")

        assert not result.empty

        # Check that columns are suffixed with timeframe
        suffixed_cols = [c for c in result.columns if c.endswith("_d1")]
        assert len(suffixed_cols) > 0, "Should have columns suffixed with _d1"

        # Check specific indicators
        assert "rsi_14_d1" in result.columns
        assert "macd_d1" in result.columns
        assert "adx_d1" in result.columns

    def test_compute_single_timeframe_empty(self):
        """Test handling of empty DataFrame."""
        mtf = MultiTimeframeFeatures()
        empty_df = pd.DataFrame()
        result = mtf.compute_single_timeframe(empty_df, "d1")

        assert result.empty

    def test_compute_all_timeframes(
        self, sample_ohlc_df, sample_hourly_df, sample_weekly_df
    ):
        """Test computing features across multiple timeframes."""
        mtf = MultiTimeframeFeatures(timeframes=["h1", "d1", "w1"])

        data_dict = {
            "h1": sample_hourly_df,
            "d1": sample_ohlc_df,
            "w1": sample_weekly_df,
        }

        result = mtf.compute_all_timeframes(data_dict, align_to="d1")

        assert not result.empty

        # Check for features from each timeframe
        assert any(c.endswith("_d1") for c in result.columns)
        assert any(c.endswith("_h1") for c in result.columns)
        assert any(c.endswith("_w1") for c in result.columns)

    def test_compute_all_timeframes_empty_dict(self):
        """Test handling of empty data dictionary."""
        mtf = MultiTimeframeFeatures()
        result = mtf.compute_all_timeframes({})

        assert result.empty

    def test_compute_alignment_score(self, sample_ohlc_df):
        """Test alignment score computation."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        # First compute features
        features = mtf.compute_single_timeframe(sample_ohlc_df, "d1")

        # Then compute alignment
        alignment = mtf.compute_alignment_score(features)

        assert len(alignment) == len(features)
        assert (alignment >= 0).all(), "Alignment should be >= 0"
        assert (alignment <= 1).all(), "Alignment should be <= 1"

    def test_compute_trend_strength(self, sample_ohlc_df):
        """Test trend strength computation."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        features = mtf.compute_single_timeframe(sample_ohlc_df, "d1")
        strength = mtf.compute_trend_strength(features)

        assert len(strength) == len(features)
        # ADX is typically 0-100
        valid_strength = strength.dropna()
        assert (valid_strength >= 0).all(), "Strength should be >= 0"

    def test_compute_volatility_regime(self, sample_ohlc_df):
        """Test volatility regime detection."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        features = mtf.compute_single_timeframe(sample_ohlc_df, "d1")
        regime = mtf.compute_volatility_regime(features)

        assert len(regime) == len(features)
        assert set(regime.unique()).issubset({"low", "normal", "high"})

    def test_get_feature_columns(self, sample_ohlc_df):
        """Test feature column extraction."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        features = mtf.compute_single_timeframe(sample_ohlc_df, "d1")
        feature_cols = mtf.get_feature_columns(features)

        # Should not include raw OHLCV columns
        assert "ts" not in feature_cols
        assert "open" not in feature_cols
        assert "close" not in feature_cols

        # Should include indicator columns
        assert len(feature_cols) > 0

    def test_prepare_for_ml(self, sample_ohlc_df):
        """Test ML preparation."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        features = mtf.compute_single_timeframe(sample_ohlc_df, "d1")
        ml_ready = mtf.prepare_for_ml(features, dropna=True)

        # Should have ts and close for reference
        assert "ts" in ml_ready.columns
        assert "close" in ml_ready.columns

        # Should have no NaN values
        assert not ml_ready.isna().any().any()


class TestTimeframeAlignment:
    """Test timeframe alignment functionality."""

    def test_higher_to_lower_frequency(
        self, sample_ohlc_df, sample_hourly_df
    ):
        """Test aligning hourly data to daily."""
        mtf = MultiTimeframeFeatures(timeframes=["h1", "d1"])

        data_dict = {
            "h1": sample_hourly_df,
            "d1": sample_ohlc_df,
        }

        result = mtf.compute_all_timeframes(data_dict, align_to="d1")

        # Result should have same length as daily data
        assert len(result) == len(sample_ohlc_df)

    def test_lower_to_higher_frequency(
        self, sample_ohlc_df, sample_weekly_df
    ):
        """Test aligning weekly data to daily (forward-fill)."""
        mtf = MultiTimeframeFeatures(timeframes=["d1", "w1"])

        data_dict = {
            "d1": sample_ohlc_df,
            "w1": sample_weekly_df,
        }

        result = mtf.compute_all_timeframes(data_dict, align_to="d1")

        # Result should have same length as daily data
        assert len(result) == len(sample_ohlc_df)


class TestEdgeCases:
    """Test edge cases."""

    def test_missing_timeframe_in_data(self, sample_ohlc_df):
        """Test handling when a timeframe is missing from data."""
        mtf = MultiTimeframeFeatures(timeframes=["m15", "h1", "d1", "w1"])

        # Only provide d1 data
        data_dict = {"d1": sample_ohlc_df}

        result = mtf.compute_all_timeframes(data_dict, align_to="d1")

        # Should still work with available data
        assert not result.empty
        assert any(c.endswith("_d1") for c in result.columns)

    def test_align_to_missing_timeframe(self, sample_ohlc_df):
        """Test when align_to timeframe is not in data."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        data_dict = {"d1": sample_ohlc_df}

        # Try to align to h1 which is not in data
        result = mtf.compute_all_timeframes(data_dict, align_to="h1")

        # Should fall back to first available timeframe
        assert not result.empty

    def test_no_trend_indicators(self):
        """Test alignment score when no trend indicators exist."""
        mtf = MultiTimeframeFeatures(timeframes=["d1"])

        # Create DataFrame without trend indicators
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=10, freq="D"),
            "random_col": range(10),
        })

        alignment = mtf.compute_alignment_score(df)

        # Should return default 0.5
        assert (alignment == 0.5).all()


class TestIntegration:
    """Integration tests for multi-timeframe features."""

    def test_full_pipeline(self):
        """Test full feature computation pipeline."""
        np.random.seed(42)

        # Create larger datasets to ensure enough data after warmup
        n_daily = 200
        n_hourly = 1000
        n_weekly = 100

        base_price = 100.0

        # Daily data
        returns_d = np.random.randn(n_daily) * 0.02
        prices_d = base_price * np.cumprod(1 + returns_d)
        daily_df = pd.DataFrame({
            "ts": pd.date_range("2023-01-01", periods=n_daily, freq="D"),
            "open": prices_d * (1 + np.random.randn(n_daily) * 0.005),
            "high": prices_d * (1 + np.abs(np.random.randn(n_daily) * 0.01)),
            "low": prices_d * (1 - np.abs(np.random.randn(n_daily) * 0.01)),
            "close": prices_d,
            "volume": np.random.randint(1000000, 10000000, n_daily).astype(float),
        })
        daily_df["high"] = daily_df[["open", "high", "close"]].max(axis=1)
        daily_df["low"] = daily_df[["open", "low", "close"]].min(axis=1)

        # Hourly data
        returns_h = np.random.randn(n_hourly) * 0.005
        prices_h = base_price * np.cumprod(1 + returns_h)
        hourly_df = pd.DataFrame({
            "ts": pd.date_range("2023-01-01", periods=n_hourly, freq="h"),
            "open": prices_h * (1 + np.random.randn(n_hourly) * 0.002),
            "high": prices_h * (1 + np.abs(np.random.randn(n_hourly) * 0.003)),
            "low": prices_h * (1 - np.abs(np.random.randn(n_hourly) * 0.003)),
            "close": prices_h,
            "volume": np.random.randint(100000, 1000000, n_hourly).astype(float),
        })
        hourly_df["high"] = hourly_df[["open", "high", "close"]].max(axis=1)
        hourly_df["low"] = hourly_df[["open", "low", "close"]].min(axis=1)

        # Weekly data
        returns_w = np.random.randn(n_weekly) * 0.03
        prices_w = base_price * np.cumprod(1 + returns_w)
        weekly_df = pd.DataFrame({
            "ts": pd.date_range("2022-01-01", periods=n_weekly, freq="W"),
            "open": prices_w * (1 + np.random.randn(n_weekly) * 0.01),
            "high": prices_w * (1 + np.abs(np.random.randn(n_weekly) * 0.02)),
            "low": prices_w * (1 - np.abs(np.random.randn(n_weekly) * 0.02)),
            "close": prices_w,
            "volume": np.random.randint(5000000, 50000000, n_weekly).astype(float),
        })
        weekly_df["high"] = weekly_df[["open", "high", "close"]].max(axis=1)
        weekly_df["low"] = weekly_df[["open", "low", "close"]].min(axis=1)

        mtf = MultiTimeframeFeatures(timeframes=["h1", "d1", "w1"])

        data_dict = {
            "h1": hourly_df,
            "d1": daily_df,
            "w1": weekly_df,
        }

        # Compute all features
        features = mtf.compute_all_timeframes(data_dict, align_to="d1")

        # Add derived scores
        features["alignment"] = mtf.compute_alignment_score(features)
        features["trend_strength"] = mtf.compute_trend_strength(features)
        features["volatility_regime"] = mtf.compute_volatility_regime(features)

        # Prepare for ML
        ml_ready = mtf.prepare_for_ml(features, dropna=True)

        # Verify output
        assert not ml_ready.empty, "ML-ready DataFrame should not be empty"
        assert "ts" in ml_ready.columns
        assert "close" in ml_ready.columns
        assert not ml_ready.isna().any().any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
