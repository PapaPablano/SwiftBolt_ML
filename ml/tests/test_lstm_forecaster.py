"""Unit tests for LSTM Forecaster."""

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


from src.models.lstm_forecaster import (  # noqa: E402
    TF_AVAILABLE,
    LSTMForecaster,
    is_tensorflow_available,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 300

    # Generate price data with momentum
    base_price = 100.0
    returns = np.random.randn(n) * 0.01
    # Add some momentum
    for i in range(1, n):
        returns[i] += 0.3 * returns[i - 1]
    prices = base_price * np.exp(np.cumsum(returns))

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


class TestLSTMForecasterInit:
    """Test LSTMForecaster initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        forecaster = LSTMForecaster()

        assert forecaster.lookback == 60
        assert forecaster.units == 64
        assert forecaster.n_layers == 2
        assert forecaster.dropout == 0.2
        assert forecaster.mc_iterations == 100
        assert forecaster.epochs == 50
        assert forecaster.batch_size == 32
        assert forecaster.bullish_threshold == 0.02
        assert forecaster.bearish_threshold == -0.02
        assert forecaster.is_trained is False

    def test_custom_architecture(self):
        """Test initialization with custom architecture."""
        forecaster = LSTMForecaster(
            lookback=30,
            units=128,
            n_layers=3,
            dropout=0.3,
        )

        assert forecaster.lookback == 30
        assert forecaster.units == 128
        assert forecaster.n_layers == 3
        assert forecaster.dropout == 0.3

    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        forecaster = LSTMForecaster(
            bullish_threshold=0.03,
            bearish_threshold=-0.03,
        )

        assert forecaster.bullish_threshold == 0.03
        assert forecaster.bearish_threshold == -0.03

    def test_custom_mc_iterations(self):
        """Test initialization with custom MC iterations."""
        forecaster = LSTMForecaster(mc_iterations=50)
        assert forecaster.mc_iterations == 50


class TestLSTMForecasterTraining:
    """Test model training."""

    def test_train_success(self, sample_ohlc_df):
        """Test successful training (works in fallback mode too)."""
        forecaster = LSTMForecaster(
            lookback=30,
            epochs=5,  # Fewer epochs for faster testing
        )
        forecaster.train(sample_ohlc_df)

        assert forecaster.is_trained is True
        assert "trained_at" in forecaster.training_stats
        assert "n_samples" in forecaster.training_stats

    def test_train_insufficient_data(self, minimal_ohlc_df):
        """Test training fails with insufficient data."""
        forecaster = LSTMForecaster()

        with pytest.raises(ValueError, match="Insufficient"):
            forecaster.train(minimal_ohlc_df, min_samples=100)

    def test_train_missing_close_column(self):
        """Test training fails without close column."""
        df = pd.DataFrame({"ts": [1, 2, 3], "open": [1, 2, 3]})
        forecaster = LSTMForecaster()

        with pytest.raises(ValueError, match="close"):
            forecaster.train(df)

    def test_training_stats_populated(self, sample_ohlc_df):
        """Test that training stats are populated."""
        forecaster = LSTMForecaster(lookback=30, epochs=5)
        forecaster.train(sample_ohlc_df)

        assert forecaster.training_stats["n_samples"] > 0
        assert "trained_at" in forecaster.training_stats


class TestLSTMForecasterPrediction:
    """Test prediction functionality."""

    def test_predict_success(self, sample_ohlc_df):
        """Test successful prediction."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict(df=sample_ohlc_df)

        assert "label" in prediction
        assert "confidence" in prediction
        assert "probabilities" in prediction
        assert "forecast_return" in prediction
        assert "forecast_volatility" in prediction

    def test_predict_label_values(self, sample_ohlc_df):
        """Test that labels are valid."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict(df=sample_ohlc_df)

        assert prediction["label"] in ["Bullish", "Neutral", "Bearish"]

    def test_predict_confidence_range(self, sample_ohlc_df):
        """Test that confidence is in valid range."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict(df=sample_ohlc_df)

        assert 0 <= prediction["confidence"] <= 1

    def test_predict_probabilities_sum(self, sample_ohlc_df):
        """Test that probabilities sum to 1."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict(df=sample_ohlc_df)
        probs = prediction["probabilities"]

        total = probs["bullish"] + probs["neutral"] + probs["bearish"]
        assert abs(total - 1.0) < 0.01

    def test_predict_before_training(self):
        """Test that prediction fails before training."""
        forecaster = LSTMForecaster()

        with pytest.raises(RuntimeError, match="not trained"):
            forecaster.predict()


class TestLSTMForecasterGenerateForecast:
    """Test full forecast generation."""

    def test_generate_forecast_structure(self, sample_ohlc_df):
        """Test forecast output structure."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
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
        """Test that model_type is LSTM."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        assert result["model_type"] == "LSTM"

    def test_forecast_points_count(self, sample_ohlc_df):
        """Test correct number of forecast points per horizon."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)

        horizons = {"1D": 1, "1W": 5, "1M": 21}

        for horizon, expected_days in horizons.items():
            result = forecaster.generate_forecast(sample_ohlc_df, horizon=horizon)
            assert len(result["points"]) == expected_days

    def test_forecast_points_structure(self, sample_ohlc_df):
        """Test forecast points have correct structure."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        point = result["points"][0]
        assert "ts" in point
        assert "value" in point
        assert "lower" in point
        assert "upper" in point

    def test_forecast_confidence_bounds(self, sample_ohlc_df):
        """Test that confidence bounds are valid."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        for point in result["points"]:
            assert point["lower"] <= point["value"] <= point["upper"]

    def test_forecast_values_reasonable(self, sample_ohlc_df):
        """Test that forecast values are reasonable."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        last_close = sample_ohlc_df["close"].iloc[-1]

        for point in result["points"]:
            # Forecast should be within 50% of last close
            assert point["value"] > last_close * 0.5
            assert point["value"] < last_close * 1.5


class TestLSTMForecasterModelInfo:
    """Test model info functionality."""

    def test_get_model_info(self, sample_ohlc_df):
        """Test get_model_info output."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        info = forecaster.get_model_info()

        assert info["name"] == "LSTM"
        assert info["is_trained"] is True
        assert "tensorflow_available" in info
        assert "config" in info
        assert "thresholds" in info
        assert "training_stats" in info

    def test_model_info_config(self, sample_ohlc_df):
        """Test model info config section."""
        forecaster = LSTMForecaster(
            lookback=30,
            units=128,
            n_layers=3,
            dropout=0.3,
            epochs=5,
            mc_iterations=10,
        )
        forecaster.train(sample_ohlc_df)

        info = forecaster.get_model_info()
        config = info["config"]

        assert config["lookback"] == 30
        assert config["units"] == 128
        assert config["n_layers"] == 3
        assert config["dropout"] == 0.3


class TestLSTMForecasterEdgeCases:
    """Test edge cases and error handling."""

    def test_horizon_parsing(self):
        """Test horizon string parsing."""
        forecaster = LSTMForecaster()

        assert forecaster._parse_horizon("1D") == 1
        assert forecaster._parse_horizon("1W") == 5
        assert forecaster._parse_horizon("1M") == 21
        assert forecaster._parse_horizon("2M") == 42
        assert forecaster._parse_horizon("invalid") == 1  # Default

    def test_null_prediction_on_error(self, sample_ohlc_df):
        """Test null prediction structure."""
        forecaster = LSTMForecaster()
        null_pred = forecaster._null_prediction("test error")

        assert null_pred["label"] == "Neutral"
        assert null_pred["confidence"] == 0.33
        assert "error" in null_pred
        assert null_pred["error"] == "test error"


class TestTensorFlowAvailability:
    """Test TensorFlow availability handling."""

    def test_is_tensorflow_available_function(self):
        """Test the is_tensorflow_available helper function."""
        result = is_tensorflow_available()
        assert isinstance(result, bool)
        assert result == TF_AVAILABLE

    def test_fallback_mode_when_unavailable(self, sample_ohlc_df):
        """Test that forecaster works in fallback mode."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        forecaster.train(sample_ohlc_df)

        # Should work regardless of TensorFlow availability
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        assert "label" in result
        assert "confidence" in result
        assert "points" in result


class TestIntegration:
    """Integration tests for LSTM Forecaster."""

    def test_full_pipeline(self, sample_ohlc_df):
        """Test full training and forecasting pipeline."""
        forecaster = LSTMForecaster(
            lookback=30,
            units=32,
            n_layers=1,
            epochs=5,
            mc_iterations=10,
        )

        forecaster.train(sample_ohlc_df)
        assert forecaster.is_trained

        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        assert result["label"] in ["Bullish", "Neutral", "Bearish"]
        assert 0 <= result["confidence"] <= 1
        assert len(result["points"]) == 5
        assert result["model_type"] == "LSTM"

    def test_consistency_across_runs(self, sample_ohlc_df):
        """Test basic consistency (may vary due to TF randomness)."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        # Just verify it produces valid output
        assert result["label"] in ["Bullish", "Neutral", "Bearish"]


class TestEnsembleCompatibility:
    """Test compatibility with existing ensemble framework."""

    def test_output_format_matches_baseline(self, sample_ohlc_df):
        """Test that output format is compatible with ensemble."""
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
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
        forecaster = LSTMForecaster(lookback=30, epochs=5, mc_iterations=10)
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
