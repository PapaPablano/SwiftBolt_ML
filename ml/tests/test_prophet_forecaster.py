"""Unit tests for Prophet Forecaster."""

import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Mock settings before importing
mock_settings = MagicMock()
mock_settings.min_bars_for_training = 50
sys.modules["config.settings"] = MagicMock()
sys.modules["config.settings"].settings = mock_settings


from src.models.prophet_forecaster import (  # noqa: E402
    ProphetForecaster,
    is_prophet_available,
    PROPHET_AVAILABLE,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 300

    # Generate trending price data with some seasonality
    base_price = 100.0
    trend = np.linspace(0, 0.2, n)
    # Add weekly pattern
    weekly = 0.01 * np.sin(2 * np.pi * np.arange(n) / 5)
    noise = np.random.randn(n) * 0.01
    prices = base_price * (1 + trend + weekly + np.cumsum(noise))

    df = pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n) * 0.01)),
            "low": prices * (1 - np.abs(np.random.randn(n) * 0.01)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, n).astype(float),
        }
    )

    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def minimal_ohlc_df():
    """Create minimal OHLC data (too small for training)."""
    np.random.seed(42)
    n = 50
    prices = 100 + np.cumsum(np.random.randn(n) * 0.5)

    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1000000, 5000000, n).astype(float),
        }
    )


class TestProphetForecasterInit:
    """Test ProphetForecaster initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        forecaster = ProphetForecaster()

        assert forecaster.weekly_seasonality is True
        assert forecaster.yearly_seasonality is False
        assert forecaster.daily_seasonality is False
        assert forecaster.changepoint_prior_scale == 0.05
        assert forecaster.seasonality_prior_scale == 10.0
        assert forecaster.interval_width == 0.95
        assert forecaster.bullish_threshold == 0.02
        assert forecaster.bearish_threshold == -0.02
        assert forecaster.is_trained is False

    def test_custom_seasonality(self):
        """Test initialization with custom seasonality."""
        forecaster = ProphetForecaster(
            weekly_seasonality=False,
            yearly_seasonality=True,
            daily_seasonality=True,
        )

        assert forecaster.weekly_seasonality is False
        assert forecaster.yearly_seasonality is True
        assert forecaster.daily_seasonality is True

    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        forecaster = ProphetForecaster(
            bullish_threshold=0.03,
            bearish_threshold=-0.03,
        )

        assert forecaster.bullish_threshold == 0.03
        assert forecaster.bearish_threshold == -0.03

    def test_custom_prior_scales(self):
        """Test initialization with custom prior scales."""
        forecaster = ProphetForecaster(
            changepoint_prior_scale=0.1,
            seasonality_prior_scale=5.0,
        )

        assert forecaster.changepoint_prior_scale == 0.1
        assert forecaster.seasonality_prior_scale == 5.0


class TestProphetForecasterTraining:
    """Test model training."""

    def test_train_success(self, sample_ohlc_df):
        """Test successful training (works in fallback mode too)."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        assert forecaster.is_trained is True
        assert "trained_at" in forecaster.training_stats
        assert "n_samples" in forecaster.training_stats

    def test_train_insufficient_data(self, minimal_ohlc_df):
        """Test training fails with insufficient data."""
        forecaster = ProphetForecaster()

        with pytest.raises(ValueError, match="Insufficient"):
            forecaster.train(minimal_ohlc_df, min_samples=100)

    def test_train_missing_close_column(self):
        """Test training fails without close column."""
        df = pd.DataFrame({"ts": [1, 2, 3], "open": [1, 2, 3]})
        forecaster = ProphetForecaster()

        with pytest.raises(ValueError, match="close"):
            forecaster.train(df)

    def test_train_missing_ts_column(self, sample_ohlc_df):
        """Test training fails without ts column."""
        df = sample_ohlc_df.drop(columns=["ts"])
        forecaster = ProphetForecaster()

        with pytest.raises(ValueError, match="ts"):
            forecaster.train(df)

    def test_training_stats_populated(self, sample_ohlc_df):
        """Test that training stats are populated."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        assert forecaster.training_stats["n_samples"] == len(sample_ohlc_df)
        assert "trained_at" in forecaster.training_stats


class TestProphetForecasterPrediction:
    """Test prediction functionality."""

    def test_predict_success(self, sample_ohlc_df):
        """Test successful prediction."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert "label" in prediction
        assert "confidence" in prediction
        assert "probabilities" in prediction
        assert "forecast_return" in prediction
        assert "forecast_volatility" in prediction

    def test_predict_label_values(self, sample_ohlc_df):
        """Test that labels are valid."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert prediction["label"] in ["Bullish", "Neutral", "Bearish"]

    def test_predict_confidence_range(self, sample_ohlc_df):
        """Test that confidence is in valid range."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert 0 <= prediction["confidence"] <= 1

    def test_predict_probabilities_sum(self, sample_ohlc_df):
        """Test that probabilities sum to 1."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()
        probs = prediction["probabilities"]

        total = probs["bullish"] + probs["neutral"] + probs["bearish"]
        assert abs(total - 1.0) < 0.01

    def test_predict_before_training(self):
        """Test that prediction fails before training."""
        forecaster = ProphetForecaster()

        with pytest.raises(RuntimeError, match="not trained"):
            forecaster.predict()

    def test_predict_with_new_data(self, sample_ohlc_df):
        """Test prediction with new data."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df.iloc[:200])

        prediction = forecaster.predict(df=sample_ohlc_df)

        assert "label" in prediction
        assert prediction["confidence"] > 0


class TestProphetForecasterGenerateForecast:
    """Test full forecast generation."""

    def test_generate_forecast_structure(self, sample_ohlc_df):
        """Test forecast output structure."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        assert "label" in result
        assert "confidence" in result
        assert "raw_confidence" in result
        assert "horizon" in result
        assert "points" in result
        assert "probabilities" in result
        assert "model_type" in result
        assert "forecast_return" in result
        assert "forecast_volatility" in result

    def test_generate_forecast_model_type(self, sample_ohlc_df):
        """Test that model_type is Prophet."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        assert result["model_type"] == "Prophet"

    def test_forecast_points_count(self, sample_ohlc_df):
        """Test correct number of forecast points per horizon."""
        forecaster = ProphetForecaster()

        horizons = {"1D": 1, "1W": 5, "1M": 21}

        for horizon, expected_days in horizons.items():
            result = forecaster.generate_forecast(sample_ohlc_df, horizon=horizon)
            assert len(result["points"]) == expected_days

    def test_forecast_points_structure(self, sample_ohlc_df):
        """Test forecast points have correct structure."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        point = result["points"][0]
        assert "ts" in point
        assert "value" in point
        assert "lower" in point
        assert "upper" in point

    def test_forecast_confidence_bounds(self, sample_ohlc_df):
        """Test that confidence bounds are valid."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        for point in result["points"]:
            assert point["lower"] <= point["value"] <= point["upper"]

    def test_forecast_values_reasonable(self, sample_ohlc_df):
        """Test that forecast values are reasonable."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        last_close = sample_ohlc_df["close"].iloc[-1]

        for point in result["points"]:
            # Forecast should be within 50% of last close
            assert point["value"] > last_close * 0.5
            assert point["value"] < last_close * 1.5


class TestProphetForecasterModelInfo:
    """Test model info functionality."""

    def test_get_model_info(self, sample_ohlc_df):
        """Test get_model_info output."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        info = forecaster.get_model_info()

        assert info["name"] == "Prophet"
        assert info["is_trained"] is True
        assert "prophet_available" in info
        assert "config" in info
        assert "thresholds" in info
        assert "training_stats" in info

    def test_model_info_config(self, sample_ohlc_df):
        """Test model info config section."""
        forecaster = ProphetForecaster(
            weekly_seasonality=True,
            changepoint_prior_scale=0.1,
        )
        forecaster.train(sample_ohlc_df)

        info = forecaster.get_model_info()
        config = info["config"]

        assert config["weekly_seasonality"] is True
        assert config["changepoint_prior_scale"] == 0.1


class TestProphetForecasterEdgeCases:
    """Test edge cases and error handling."""

    def test_horizon_parsing(self):
        """Test horizon string parsing."""
        forecaster = ProphetForecaster()

        assert forecaster._parse_horizon("1D") == 1
        assert forecaster._parse_horizon("1W") == 5
        assert forecaster._parse_horizon("1M") == 21
        assert forecaster._parse_horizon("2M") == 42
        assert forecaster._parse_horizon("invalid") == 1  # Default

    def test_classify_returns(self, sample_ohlc_df):
        """Test return classification."""
        forecaster = ProphetForecaster(
            bullish_threshold=0.02,
            bearish_threshold=-0.02,
        )

        returns = pd.Series([0.05, -0.05, 0.01, -0.01, 0.0])
        labels = forecaster._classify_returns(returns)

        assert labels.iloc[0] == "bullish"
        assert labels.iloc[1] == "bearish"
        assert labels.iloc[2] == "neutral"
        assert labels.iloc[3] == "neutral"
        assert labels.iloc[4] == "neutral"

    def test_probability_calculation(self, sample_ohlc_df):
        """Test probability calculation."""
        forecaster = ProphetForecaster()

        # Strong bullish signal
        probs = forecaster._calculate_probabilities(0.05, 0.01)
        assert probs["bullish"] > probs["bearish"]

        # Strong bearish signal
        probs = forecaster._calculate_probabilities(-0.05, 0.01)
        assert probs["bearish"] > probs["bullish"]

        # Neutral signal
        probs = forecaster._calculate_probabilities(0.0, 0.01)
        assert probs["neutral"] > 0


class TestProphetAvailability:
    """Test Prophet availability handling."""

    def test_is_prophet_available_function(self):
        """Test the is_prophet_available helper function."""
        result = is_prophet_available()
        assert isinstance(result, bool)
        assert result == PROPHET_AVAILABLE

    def test_fallback_mode_when_unavailable(self, sample_ohlc_df):
        """Test that forecaster works in fallback mode."""
        forecaster = ProphetForecaster()
        forecaster.train(sample_ohlc_df)

        # Should work regardless of Prophet availability
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        assert "label" in result
        assert "confidence" in result
        assert "points" in result


class TestIntegration:
    """Integration tests for Prophet Forecaster."""

    def test_full_pipeline(self, sample_ohlc_df):
        """Test full training and forecasting pipeline."""
        forecaster = ProphetForecaster(
            weekly_seasonality=True,
            yearly_seasonality=False,
        )

        forecaster.train(sample_ohlc_df)
        assert forecaster.is_trained

        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        assert result["label"] in ["Bullish", "Neutral", "Bearish"]
        assert 0 <= result["confidence"] <= 1
        assert len(result["points"]) == 5
        assert result["model_type"] == "Prophet"

    def test_consistency_across_runs(self, sample_ohlc_df):
        """Test that results are consistent with same data."""
        forecaster1 = ProphetForecaster()
        result1 = forecaster1.generate_forecast(sample_ohlc_df, horizon="1D")

        forecaster2 = ProphetForecaster()
        result2 = forecaster2.generate_forecast(sample_ohlc_df, horizon="1D")

        # Labels should be the same
        assert result1["label"] == result2["label"]


class TestEnsembleCompatibility:
    """Test compatibility with existing ensemble framework."""

    def test_output_format_matches_baseline(self, sample_ohlc_df):
        """Test that output format is compatible with ensemble."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        # Required fields for ensemble compatibility
        assert "label" in result
        assert "confidence" in result
        assert "probabilities" in result
        assert "points" in result
        assert "horizon" in result

        # Probabilities should have all three classes
        probs = result["probabilities"]
        assert "bullish" in probs
        assert "neutral" in probs
        assert "bearish" in probs

    def test_probability_dict_format(self, sample_ohlc_df):
        """Test probability dict format matches ensemble expectations."""
        forecaster = ProphetForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        probs = result["probabilities"]

        # Values should be floats
        assert isinstance(probs["bullish"], float)
        assert isinstance(probs["neutral"], float)
        assert isinstance(probs["bearish"], float)

        # Values should be valid probabilities
        for val in probs.values():
            assert 0 <= val <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
