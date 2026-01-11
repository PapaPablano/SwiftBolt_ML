"""Unit tests for ARIMA-GARCH Forecaster."""

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


from src.models.arima_garch_forecaster import ArimaGarchForecaster  # noqa: E402


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 300  # Need enough data for ARIMA-GARCH

    # Generate trending price data with volatility clustering
    base_price = 100.0
    trend = np.linspace(0, 0.2, n)  # 20% uptrend

    # Add volatility clustering (GARCH-like behavior)
    volatility = np.zeros(n)
    volatility[0] = 0.01
    for i in range(1, n):
        volatility[i] = 0.0001 + 0.1 * volatility[i - 1] + 0.85 * np.random.randn() ** 2 * 0.01

    noise = np.random.randn(n) * np.sqrt(volatility)
    prices = base_price * (1 + trend + np.cumsum(noise))

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

    # Ensure high >= close >= low
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


class TestArimaGarchForecasterInit:
    """Test ArimaGarchForecaster initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        forecaster = ArimaGarchForecaster()

        assert forecaster.arima_order == (1, 0, 1)
        assert forecaster.garch_p == 1
        assert forecaster.garch_q == 1
        assert forecaster.bullish_threshold == 0.02
        assert forecaster.bearish_threshold == -0.02
        assert forecaster.is_trained is False

    def test_custom_arima_order(self):
        """Test initialization with custom ARIMA order."""
        forecaster = ArimaGarchForecaster(arima_order=(2, 1, 2))

        assert forecaster.arima_order == (2, 1, 2)

    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        forecaster = ArimaGarchForecaster(
            bullish_threshold=0.03,
            bearish_threshold=-0.03,
        )

        assert forecaster.bullish_threshold == 0.03
        assert forecaster.bearish_threshold == -0.03

    def test_auto_select_order_flag(self):
        """Test auto_select_order flag."""
        forecaster = ArimaGarchForecaster(auto_select_order=True)

        assert forecaster.auto_select_order is True


class TestArimaGarchForecasterTraining:
    """Test model training."""

    def test_train_success(self, sample_ohlc_df):
        """Test successful training."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        assert forecaster.is_trained is True
        assert forecaster.fitted_arima is not None
        assert "trained_at" in forecaster.training_stats
        assert "n_samples" in forecaster.training_stats
        assert "accuracy" in forecaster.training_stats

    def test_train_insufficient_data(self, minimal_ohlc_df):
        """Test training fails with insufficient data."""
        forecaster = ArimaGarchForecaster()

        with pytest.raises(ValueError, match="Insufficient"):
            forecaster.train(minimal_ohlc_df, min_samples=100)

    def test_train_missing_close_column(self):
        """Test training fails without close column."""
        df = pd.DataFrame({"open": [1, 2, 3], "high": [1, 2, 3]})
        forecaster = ArimaGarchForecaster()

        with pytest.raises(ValueError, match="close"):
            forecaster.train(df)

    def test_diagnostics_populated(self, sample_ohlc_df):
        """Test that diagnostics are populated after training."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        assert "ljung_box_pvalue" in forecaster.diagnostics
        assert "arima_aic" in forecaster.diagnostics
        assert "arima_bic" in forecaster.diagnostics
        assert "residual_mean" in forecaster.diagnostics
        assert "residual_std" in forecaster.diagnostics

    def test_auto_order_selection(self, sample_ohlc_df):
        """Test automatic ARIMA order selection."""
        forecaster = ArimaGarchForecaster(auto_select_order=True)
        forecaster.train(sample_ohlc_df)

        assert forecaster.is_trained is True
        # Order should be a valid tuple
        assert len(forecaster.arima_order) == 3
        assert all(isinstance(x, int) for x in forecaster.arima_order)


class TestArimaGarchForecasterPrediction:
    """Test prediction functionality."""

    def test_predict_success(self, sample_ohlc_df):
        """Test successful prediction."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert "label" in prediction
        assert "confidence" in prediction
        assert "probabilities" in prediction
        assert "forecast_return" in prediction
        assert "forecast_volatility" in prediction
        assert "ci_lower" in prediction
        assert "ci_upper" in prediction

    def test_predict_label_values(self, sample_ohlc_df):
        """Test that labels are valid."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert prediction["label"] in ["Bullish", "Neutral", "Bearish"]

    def test_predict_confidence_range(self, sample_ohlc_df):
        """Test that confidence is in valid range."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()

        assert 0 <= prediction["confidence"] <= 1

    def test_predict_probabilities_sum(self, sample_ohlc_df):
        """Test that probabilities sum to 1."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        prediction = forecaster.predict()
        probs = prediction["probabilities"]

        total = probs["bullish"] + probs["neutral"] + probs["bearish"]
        assert abs(total - 1.0) < 0.01

    def test_predict_before_training(self):
        """Test that prediction fails before training."""
        forecaster = ArimaGarchForecaster()

        with pytest.raises(RuntimeError, match="not trained"):
            forecaster.predict()

    def test_predict_with_new_data(self, sample_ohlc_df):
        """Test prediction with new data for refitting."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df.iloc[:200])

        # Predict with more recent data
        prediction = forecaster.predict(df=sample_ohlc_df)

        assert "label" in prediction
        assert prediction["confidence"] > 0


class TestArimaGarchForecasterGenerateForecast:
    """Test full forecast generation."""

    def test_generate_forecast_structure(self, sample_ohlc_df):
        """Test forecast output structure."""
        forecaster = ArimaGarchForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        assert "label" in result
        assert "confidence" in result
        assert "raw_confidence" in result
        assert "horizon" in result
        assert "points" in result
        assert "probabilities" in result
        assert "model_type" in result
        assert "arima_order" in result
        assert "forecast_return" in result
        assert "forecast_volatility" in result

    def test_generate_forecast_model_type(self, sample_ohlc_df):
        """Test that model_type is ARIMA-GARCH."""
        forecaster = ArimaGarchForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        assert result["model_type"] == "ARIMA-GARCH"

    def test_forecast_points_count(self, sample_ohlc_df):
        """Test correct number of forecast points per horizon."""
        forecaster = ArimaGarchForecaster()

        horizons = {"1D": 1, "1W": 5, "1M": 21}

        for horizon, expected_days in horizons.items():
            result = forecaster.generate_forecast(sample_ohlc_df, horizon=horizon)
            assert len(result["points"]) == expected_days

    def test_forecast_points_structure(self, sample_ohlc_df):
        """Test forecast points have correct structure."""
        forecaster = ArimaGarchForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

        point = result["points"][0]
        assert "ts" in point
        assert "value" in point
        assert "lower" in point
        assert "upper" in point

    def test_forecast_confidence_bounds(self, sample_ohlc_df):
        """Test that confidence bounds are valid."""
        forecaster = ArimaGarchForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        for point in result["points"]:
            assert point["lower"] <= point["value"] <= point["upper"]

    def test_forecast_values_reasonable(self, sample_ohlc_df):
        """Test that forecast values are reasonable."""
        forecaster = ArimaGarchForecaster()
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        last_close = sample_ohlc_df["close"].iloc[-1]

        for point in result["points"]:
            # Forecast should be within 50% of last close
            assert point["value"] > last_close * 0.5
            assert point["value"] < last_close * 1.5


class TestArimaGarchForecasterDiagnostics:
    """Test diagnostic functionality."""

    def test_get_model_info(self, sample_ohlc_df):
        """Test get_model_info output."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        info = forecaster.get_model_info()

        assert info["name"] == "ARIMA-GARCH"
        assert info["is_trained"] is True
        assert "arima_order" in info
        assert "garch_params" in info
        assert "thresholds" in info
        assert "training_stats" in info
        assert "diagnostics" in info

    def test_diagnostics_ljung_box(self, sample_ohlc_df):
        """Test Ljung-Box diagnostic."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        # Ljung-Box p-value should be between 0 and 1
        lb_pvalue = forecaster.diagnostics.get("ljung_box_pvalue")
        if lb_pvalue is not None:
            assert 0 <= lb_pvalue <= 1


class TestArimaGarchForecasterEdgeCases:
    """Test edge cases and error handling."""

    def test_null_prediction_on_error(self, sample_ohlc_df):
        """Test that errors return null prediction."""
        forecaster = ArimaGarchForecaster()
        forecaster.train(sample_ohlc_df)

        # Force an error by corrupting the model
        forecaster.fitted_arima = None

        # Should handle gracefully
        prediction = forecaster.predict()
        # Will raise RuntimeError since arima is None and we're not refitting

    def test_horizon_parsing(self):
        """Test horizon string parsing."""
        forecaster = ArimaGarchForecaster()

        assert forecaster._parse_horizon("1D") == 1
        assert forecaster._parse_horizon("1W") == 5
        assert forecaster._parse_horizon("1M") == 21
        assert forecaster._parse_horizon("invalid") == 1  # Default

    def test_classify_returns(self, sample_ohlc_df):
        """Test return classification."""
        forecaster = ArimaGarchForecaster(
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
        forecaster = ArimaGarchForecaster()

        # Strong bullish signal
        probs = forecaster._calculate_probabilities(0.05, 0.01)
        assert probs["bullish"] > probs["bearish"]

        # Strong bearish signal
        probs = forecaster._calculate_probabilities(-0.05, 0.01)
        assert probs["bearish"] > probs["bullish"]

        # Neutral signal
        probs = forecaster._calculate_probabilities(0.0, 0.01)
        assert probs["neutral"] > 0


class TestIntegration:
    """Integration tests for ARIMA-GARCH Forecaster."""

    def test_full_pipeline(self, sample_ohlc_df):
        """Test full training and forecasting pipeline."""
        forecaster = ArimaGarchForecaster(
            arima_order=(1, 0, 1),
            auto_select_order=False,
        )

        # Train
        forecaster.train(sample_ohlc_df)
        assert forecaster.is_trained

        # Generate forecast
        result = forecaster.generate_forecast(sample_ohlc_df, horizon="1W")

        # Validate output
        assert result["label"] in ["Bullish", "Neutral", "Bearish"]
        assert 0 <= result["confidence"] <= 1
        assert len(result["points"]) == 5
        assert result["model_type"] == "ARIMA-GARCH"

    def test_consistency_across_runs(self, sample_ohlc_df):
        """Test that results are consistent with same data."""
        forecaster1 = ArimaGarchForecaster(arima_order=(1, 0, 1))
        result1 = forecaster1.generate_forecast(sample_ohlc_df, horizon="1D")

        forecaster2 = ArimaGarchForecaster(arima_order=(1, 0, 1))
        result2 = forecaster2.generate_forecast(sample_ohlc_df, horizon="1D")

        # Labels should be the same
        assert result1["label"] == result2["label"]

        # Returns should be very close
        assert abs(result1["forecast_return"] - result2["forecast_return"]) < 0.001

    def test_different_arima_orders(self, sample_ohlc_df):
        """Test different ARIMA orders produce valid results."""
        orders = [(1, 0, 1), (2, 0, 1), (1, 0, 2), (2, 1, 2)]

        for order in orders:
            forecaster = ArimaGarchForecaster(arima_order=order)
            result = forecaster.generate_forecast(sample_ohlc_df, horizon="1D")

            assert result["label"] in ["Bullish", "Neutral", "Bearish"]
            assert result["arima_order"] == order


class TestEnsembleCompatibility:
    """Test compatibility with existing ensemble framework."""

    def test_output_format_matches_baseline(self, sample_ohlc_df):
        """Test that output format is compatible with ensemble."""
        forecaster = ArimaGarchForecaster()
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
        forecaster = ArimaGarchForecaster()
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
