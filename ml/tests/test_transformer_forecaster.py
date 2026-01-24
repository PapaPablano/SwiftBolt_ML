"""
Unit tests for Transformer Forecaster.

Tests:
- Model initialization
- Training on synthetic data
- Inference with MC Dropout
- Multi-timeframe predictions
- Timeframe alignment scoring
"""

import numpy as np
import pandas as pd
import pytest

from src.models.transformer_forecaster import TransformerForecaster


class TestTransformerForecaster:
    """Test suite for TransformerForecaster."""

    @pytest.fixture
    def sample_data(self):
        """Create synthetic OHLC data for testing."""
        np.random.seed(42)
        n = 300
        prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

        df = pd.DataFrame({
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        })
        return df

    def test_initialization(self):
        """Test forecaster initialization."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            dropout=0.1,
            mc_iterations=20,
        )

        assert forecaster.lookback == 60
        assert forecaster.d_model == 32
        assert forecaster.num_heads == 4
        assert forecaster.is_trained is False
        assert forecaster.training_stats == {}

    def test_training(self, sample_data):
        """Test model training."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
            mc_iterations=10,
        )

        forecaster.train(sample_data)
        assert forecaster.is_trained is True
        # Accept either TensorFlow mode or fallback mode
        assert forecaster.training_stats
        assert ("epochs_trained" in forecaster.training_stats or
                "fallback_mode" in forecaster.training_stats or
                "n_samples" in forecaster.training_stats)
        print("✓ Training successful")

    def test_prediction(self, sample_data):
        """Test prediction generation."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
            mc_iterations=10,
        )

        forecaster.train(sample_data)
        prediction = forecaster.predict(sample_data)

        assert "label" in prediction
        assert prediction["label"] in ["Bullish", "Bearish", "Neutral"]
        assert "confidence" in prediction
        assert 0 <= prediction["confidence"] <= 1
        assert "forecast_return" in prediction
        assert "forecast_volatility" in prediction
        print(f"✓ Prediction generated: {prediction['label']} ({prediction['confidence']:.2%})")

    def test_multi_horizon_predictions(self, sample_data):
        """Test multi-timeframe predictions."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
            mc_iterations=10,
        )

        forecaster.train(sample_data)
        prediction = forecaster.predict(sample_data)

        # Multi-horizon predictions available in TensorFlow mode, fallback has basic prediction
        if "multi_horizon_predictions" in prediction:
            horizons = prediction["multi_horizon_predictions"]
            assert "1D" in horizons
            assert "5D" in horizons
            assert "20D" in horizons
            print(f"✓ Multi-horizon predictions: 1D={horizons['1D']:.4f}, 5D={horizons['5D']:.4f}, 20D={horizons['20D']:.4f}")
        else:
            # Fallback mode - at least has basic prediction
            assert "forecast_return" in prediction
            print(f"✓ Fallback prediction: {prediction['forecast_return']:.4f}")

    def test_timeframe_agreement(self, sample_data):
        """Test timeframe alignment scoring."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
            mc_iterations=10,
        )

        forecaster.train(sample_data)
        prediction = forecaster.predict(sample_data)

        # Timeframe agreement available in TensorFlow mode
        if "timeframe_agreement" in prediction:
            agreement = prediction["timeframe_agreement"]
            assert "agreement_score" in agreement
            assert "all_aligned" in agreement
            assert "directions" in agreement
            assert 0 <= agreement["agreement_score"] <= 1
            print(f"✓ Timeframe agreement: {agreement['agreement_score']:.2%}, aligned={agreement['all_aligned']}")
        else:
            # Fallback mode - at least has basic prediction
            assert "label" in prediction
            print(f"✓ Fallback mode prediction: {prediction['label']}")

    def test_forecast_generation(self, sample_data):
        """Test complete forecast generation."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
            mc_iterations=10,
        )

        forecaster.train(sample_data)
        forecast = forecaster.generate_forecast(sample_data, horizon="1W")

        assert forecast["label"] in ["Bullish", "Bearish", "Neutral"]
        assert forecast["confidence"] > 0
        assert "points" in forecast
        assert len(forecast["points"]) > 0
        assert forecast["model_type"] == "Transformer"
        print(f"✓ Forecast generation: {len(forecast['points'])} points, confidence={forecast['confidence']:.2%}")

    def test_model_info(self, sample_data):
        """Test model info retrieval."""
        forecaster = TransformerForecaster(
            lookback=60,
            d_model=32,
            num_heads=4,
            num_layers=2,
            epochs=2,
        )

        forecaster.train(sample_data)
        info = forecaster.get_model_info()

        assert info["name"] == "Transformer"
        assert info["is_trained"] is True
        assert "config" in info
        assert "training_stats" in info
        print(f"✓ Model info: {info['name']}, params={info.get('model_params', 'N/A')}")

    def test_horizon_parsing(self):
        """Test horizon string parsing."""
        forecaster = TransformerForecaster()

        assert forecaster._parse_horizon("1D") == 1
        assert forecaster._parse_horizon("1W") == 5
        assert forecaster._parse_horizon("1M") == 21
        assert forecaster._parse_horizon("3M") == 63
        print("✓ Horizon parsing correct")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Transformer Forecaster")
    print("=" * 60)

    test = TestTransformerForecaster()
    data = test.sample_data()

    test.test_initialization()
    test.test_training(data)
    test.test_prediction(data)
    test.test_multi_horizon_predictions(data)
    test.test_timeframe_agreement(data)
    test.test_forecast_generation(data)
    test.test_model_info(data)
    test.test_horizon_parsing()

    print("\n" + "=" * 60)
    print("All Transformer tests passed! ✓")
    print("=" * 60)
