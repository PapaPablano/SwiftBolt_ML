"""Unit tests for Enhanced Forecaster (Phase 3)."""

import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Mock the settings before importing (required for CI without env vars)
mock_settings = MagicMock()
mock_settings.min_bars_for_training = 50
sys.modules['config.settings'] = MagicMock()
sys.modules['config.settings'].settings = mock_settings

# noqa: E402 - imports must be after mock setup
from src.models.enhanced_forecaster import (  # noqa: E402
    EnhancedForecaster,
    ENHANCED_FEATURES,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 200  # Need enough data for training

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


class TestEnhancedForecasterInit:
    """Test EnhancedForecaster initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        forecaster = EnhancedForecaster()

        assert forecaster.classification_thresholds == (-0.02, 0.02)
        assert forecaster.min_training_samples == 100
        assert forecaster.is_trained is False
        assert forecaster.signal_generator is not None

    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        forecaster = EnhancedForecaster(
            classification_thresholds=(-0.03, 0.03),
            min_training_samples=50,
        )

        assert forecaster.classification_thresholds == (-0.03, 0.03)
        assert forecaster.min_training_samples == 50


class TestEnhancedForecasterFeatures:
    """Test feature preparation."""

    def test_prepare_features(self, sample_ohlc_df):
        """Test that prepare_features adds all indicators."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)

        # Check basic indicators
        assert "rsi_14" in df.columns
        assert "macd" in df.columns
        assert "bb_upper" in df.columns

        # Check new momentum indicators
        assert "stoch_k" in df.columns
        assert "kdj_j" in df.columns
        assert "adx" in df.columns

        # Check volume indicators
        assert "obv" in df.columns
        assert "mfi" in df.columns

        # Check SuperTrend
        assert "supertrend" in df.columns
        assert "supertrend_trend" in df.columns

    def test_supertrend_info_populated(self, sample_ohlc_df):
        """Test that SuperTrend info is populated."""
        forecaster = EnhancedForecaster()
        forecaster.prepare_features(sample_ohlc_df)

        assert "target_factor" in forecaster.supertrend_info
        assert "performance_index" in forecaster.supertrend_info

    def test_prepare_training_data(self, sample_ohlc_df):
        """Test training data preparation."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)

        X, y = forecaster.prepare_training_data(df, horizon_days=5)

        assert len(X) > 0
        assert len(y) == len(X)
        assert len(forecaster.feature_columns) > 0

    def test_classification_labels(self, sample_ohlc_df):
        """Test that classification labels are correct."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)

        X, y = forecaster.prepare_training_data(
            df, horizon_days=5, mode="classification"
        )

        # Check label values
        unique_labels = y.unique()
        for label in unique_labels:
            assert label in ["bullish", "neutral", "bearish"]


class TestEnhancedForecasterTraining:
    """Test model training."""

    def test_train_classification(self, sample_ohlc_df):
        """Test classification training."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)
        X, y = forecaster.prepare_training_data(df, horizon_days=5)

        metrics = forecaster.train(X, y, mode="classification")

        assert forecaster.is_trained is True
        assert "n_samples" in metrics
        assert "n_features" in metrics
        assert metrics["n_samples"] > 0

    def test_train_insufficient_data(self, sample_ohlc_df):
        """Test that training fails with insufficient data."""
        forecaster = EnhancedForecaster(min_training_samples=1000)
        df = forecaster.prepare_features(sample_ohlc_df)
        X, y = forecaster.prepare_training_data(df, horizon_days=5)

        with pytest.raises(ValueError, match="Insufficient"):
            forecaster.train(X, y)


class TestEnhancedForecasterPrediction:
    """Test prediction functionality."""

    def test_predict_classification(self, sample_ohlc_df):
        """Test classification prediction."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)
        X, y = forecaster.prepare_training_data(df, horizon_days=5)
        forecaster.train(X, y, mode="classification")

        label, confidence, proba = forecaster.predict(X.tail(1))

        assert label in ["bullish", "neutral", "bearish"]
        assert 0 <= confidence <= 1
        assert len(proba) > 0

    def test_predict_before_training(self, sample_ohlc_df):
        """Test that prediction fails before training."""
        forecaster = EnhancedForecaster()
        df = forecaster.prepare_features(sample_ohlc_df)
        X, _ = forecaster.prepare_training_data(df, horizon_days=5)

        with pytest.raises(ValueError, match="trained"):
            forecaster.predict(X.tail(1))


class TestEnhancedForecasterForecast:
    """Test full forecast generation."""

    def test_generate_forecast(self, sample_ohlc_df):
        """Test full forecast generation."""
        forecaster = EnhancedForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        # Check result structure
        assert "label" in result
        assert "confidence" in result
        assert "horizon" in result
        assert "points" in result
        assert "trend_analysis" in result
        assert "supertrend_info" in result

        # Check values
        assert result["label"] in ["bullish", "neutral", "bearish"]
        assert 0 <= result["confidence"] <= 1
        assert result["horizon"] == "1W"
        assert len(result["points"]) == 5  # 1W = 5 trading days

    def test_forecast_points_structure(self, sample_ohlc_df):
        """Test forecast points have correct structure."""
        forecaster = EnhancedForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        points = result["points"]
        assert len(points) == 1

        point = points[0]
        assert "ts" in point
        assert "value" in point
        assert "lower" in point
        assert "upper" in point

        # Lower <= value <= upper
        assert point["lower"] <= point["value"] <= point["upper"]

    def test_forecast_horizons(self, sample_ohlc_df):
        """Test different forecast horizons."""
        forecaster = EnhancedForecaster()

        horizons = {"1D": 1, "1W": 5, "2W": 10, "1M": 20}

        for horizon, expected_days in horizons.items():
            result = forecaster.generate_forecast(
                sample_ohlc_df, horizon=horizon
            )
            assert len(result["points"]) == expected_days

    def test_invalid_horizon(self, sample_ohlc_df):
        """Test that invalid horizon raises error."""
        forecaster = EnhancedForecaster()

        with pytest.raises(ValueError, match="Unknown horizon"):
            forecaster.generate_forecast(sample_ohlc_df, horizon="1Y")


class TestEnhancedForecasterFeatureImportance:
    """Test feature importance functionality."""

    def test_get_feature_importance(self, sample_ohlc_df):
        """Test feature importance retrieval."""
        forecaster = EnhancedForecaster()
        forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        importance = forecaster.get_feature_importance()

        assert len(importance) > 0
        assert all(isinstance(v, (int, float)) for v in importance.values())

    def test_get_top_features(self, sample_ohlc_df):
        """Test top features retrieval."""
        forecaster = EnhancedForecaster()
        forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        top_features = forecaster.get_top_features(n=5)

        assert len(top_features) <= 5
        assert all(isinstance(f, tuple) for f in top_features)
        assert all(len(f) == 2 for f in top_features)

        # Should be sorted by importance (descending)
        if len(top_features) > 1:
            importances = [f[1] for f in top_features]
            assert importances == sorted(importances, reverse=True)


class TestEnhancedFeaturesList:
    """Test the ENHANCED_FEATURES constant."""

    def test_enhanced_features_list(self):
        """Test that ENHANCED_FEATURES contains expected indicators."""
        # Basic indicators
        assert "rsi_14" in ENHANCED_FEATURES
        assert "macd" in ENHANCED_FEATURES
        assert "bb_upper" in ENHANCED_FEATURES

        # New momentum indicators
        assert "stoch_k" in ENHANCED_FEATURES
        assert "kdj_j" in ENHANCED_FEATURES
        assert "adx" in ENHANCED_FEATURES

        # Volume indicators
        assert "obv" in ENHANCED_FEATURES
        assert "mfi" in ENHANCED_FEATURES

        # SuperTrend
        assert "supertrend" in ENHANCED_FEATURES
        assert "supertrend_trend" in ENHANCED_FEATURES

    def test_enhanced_features_count(self):
        """Test that we have a comprehensive feature set."""
        # Should have 25+ features
        assert len(ENHANCED_FEATURES) >= 25


class TestIntegration:
    """Integration tests for EnhancedForecaster."""

    def test_full_pipeline_with_trend_analysis(self, sample_ohlc_df):
        """Test full pipeline including trend analysis."""
        forecaster = EnhancedForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        # Trend analysis should be populated
        trend_analysis = result["trend_analysis"]
        assert "trend" in trend_analysis
        assert "composite_signal" in trend_analysis
        assert "confidence" in trend_analysis

        # SuperTrend info should be populated
        st_info = result["supertrend_info"]
        assert "target_factor" in st_info
        assert "performance_index" in st_info
        assert "signal_strength" in st_info

    def test_consistency_across_runs(self, sample_ohlc_df):
        """Test that results are consistent with same seed."""
        forecaster1 = EnhancedForecaster()
        result1 = forecaster1.generate_forecast(sample_ohlc_df, horizon="1W")

        forecaster2 = EnhancedForecaster()
        result2 = forecaster2.generate_forecast(sample_ohlc_df, horizon="1W")

        # Labels should be the same (deterministic with seed)
        assert result1["label"] == result2["label"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
