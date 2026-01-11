"""Unit tests for Ensemble Manager."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.ensemble_manager import (
    EnsembleManager,
    ForecastResult,
    ErrorRecord,
)


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    np.random.seed(42)
    n = 150

    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    ohlc_df = pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        }
    )

    # Features
    ohlc_df["return_1d"] = ohlc_df["close"].pct_change()
    ohlc_df["return_5d"] = ohlc_df["close"].pct_change(5)
    ohlc_df["sma_20"] = ohlc_df["close"].rolling(20).mean()
    ohlc_df["vol_20"] = ohlc_df["return_1d"].rolling(20).std()
    ohlc_df = ohlc_df.dropna()

    features_df = ohlc_df[["return_1d", "return_5d", "sma_20", "vol_20"]]

    # Labels
    fwd = ohlc_df["close"].pct_change().shift(-1)
    labels = fwd.apply(
        lambda x: "bullish" if x > 0.01 else "bearish" if x < -0.01 else "neutral"
    ).iloc[:-1]
    features_df = features_df.iloc[:-1]
    ohlc_df = ohlc_df.iloc[:-1]

    return ohlc_df, features_df, labels


@pytest.fixture
def trained_manager(sample_data):
    """Create a trained ensemble manager."""
    ohlc_df, features_df, labels = sample_data

    manager = EnsembleManager(
        horizon="1D",
        enable_rf=True,
        enable_gb=True,
        enable_arima_garch=True,
        enable_prophet=False,
        enable_lstm=False,
    )

    manager.train(ohlc_df, features_df, labels)
    return manager, ohlc_df, features_df, labels


class TestEnsembleManagerInit:
    """Test initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        manager = EnsembleManager()

        assert manager.horizon == "1D"
        assert manager.confidence_level == 0.95
        assert manager.is_trained is False

    def test_custom_initialization(self):
        """Test custom initialization."""
        manager = EnsembleManager(
            horizon="1W",
            enable_rf=True,
            enable_gb=False,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=False,
            confidence_level=0.99,
        )

        assert manager.horizon == "1W"
        assert manager.confidence_level == 0.99

    def test_adaptive_weights(self):
        """Test adaptive weight optimizer."""
        manager = EnsembleManager(adaptive_weights=True)

        from src.models.weight_optimizer import AdaptiveWeightOptimizer

        assert isinstance(manager.weight_optimizer, AdaptiveWeightOptimizer)


class TestTraining:
    """Test model training."""

    def test_train_returns_status(self, sample_data):
        """Test that train returns status dict."""
        ohlc_df, features_df, labels = sample_data

        manager = EnsembleManager(
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=False,
        )

        status = manager.train(ohlc_df, features_df, labels)

        assert isinstance(status, dict)
        assert all(isinstance(v, bool) for v in status.values())

    def test_train_sets_is_trained(self, sample_data):
        """Test that train sets is_trained flag."""
        ohlc_df, features_df, labels = sample_data

        manager = EnsembleManager(
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=False,
            enable_prophet=False,
            enable_lstm=False,
        )

        assert manager.is_trained is False
        manager.train(ohlc_df, features_df, labels)
        assert manager.is_trained is True

    def test_train_sets_timestamp(self, sample_data):
        """Test that train sets training timestamp."""
        ohlc_df, features_df, labels = sample_data

        manager = EnsembleManager(
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=False,
            enable_prophet=False,
            enable_lstm=False,
        )

        manager.train(ohlc_df, features_df, labels)
        assert manager.training_timestamp is not None


class TestPrediction:
    """Test prediction methods."""

    def test_predict_requires_training(self, sample_data):
        """Test that predict requires training first."""
        ohlc_df, features_df, _ = sample_data
        manager = EnsembleManager()

        with pytest.raises(RuntimeError, match="not trained"):
            manager.predict(ohlc_df, features_df)

    def test_predict_returns_forecast_result(self, trained_manager):
        """Test that predict returns ForecastResult."""
        manager, ohlc_df, features_df, _ = trained_manager

        result = manager.predict(ohlc_df, features_df)

        assert isinstance(result, ForecastResult)
        assert result.label in ["Bullish", "Neutral", "Bearish"]
        assert 0 <= result.confidence <= 1

    def test_predict_stores_history(self, trained_manager):
        """Test that predict stores in history."""
        manager, ohlc_df, features_df, _ = trained_manager

        initial_count = len(manager.forecast_history)
        manager.predict(ohlc_df, features_df)

        assert len(manager.forecast_history) == initial_count + 1

    def test_generate_forecast_returns_dict(self, trained_manager):
        """Test that generate_forecast returns dict with points."""
        manager, ohlc_df, features_df, _ = trained_manager

        forecast = manager.generate_forecast(ohlc_df, features_df)

        assert "label" in forecast
        assert "confidence" in forecast
        assert "points" in forecast
        assert len(forecast["points"]) > 0

    def test_generate_forecast_with_horizon_override(self, trained_manager):
        """Test generate_forecast with horizon override."""
        manager, ohlc_df, features_df, _ = trained_manager

        forecast = manager.generate_forecast(ohlc_df, features_df, horizon="1W")

        assert forecast["horizon"] == "1W"
        assert len(forecast["points"]) == 5  # 1 week = 5 trading days


class TestWeightOptimization:
    """Test weight optimization."""

    def test_optimize_weights_requires_training(self, sample_data):
        """Test that optimize_weights requires training."""
        ohlc_df, features_df, labels = sample_data
        manager = EnsembleManager()

        with pytest.raises(RuntimeError, match="not trained"):
            manager.optimize_weights(ohlc_df, features_df, labels)

    def test_optimize_weights_returns_dict(self, trained_manager):
        """Test that optimize_weights returns weights dict."""
        manager, ohlc_df, features_df, labels = trained_manager

        weights = manager.optimize_weights(ohlc_df, features_df, labels)

        assert isinstance(weights, dict)
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestBacktesting:
    """Test backtesting functionality."""

    def test_run_backtest_returns_dataframe(self, sample_data):
        """Test that run_backtest returns DataFrame."""
        ohlc_df, features_df, labels = sample_data

        manager = EnsembleManager(
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=False,
            enable_prophet=False,
            enable_lstm=False,
        )

        results = manager.run_backtest(
            ohlc_df,
            features_df,
            labels,
            initial_train_size=50,
            refit_frequency=30,
        )

        assert isinstance(results, pd.DataFrame)
        assert len(results) > 0


class TestStatusAndDiagnostics:
    """Test status and diagnostic methods."""

    def test_get_status(self, trained_manager):
        """Test get_status method."""
        manager, _, _, _ = trained_manager

        status = manager.get_status()

        assert "is_trained" in status
        assert "n_models_total" in status
        assert "current_weights" in status
        assert status["is_trained"] is True

    def test_get_diagnostics(self, trained_manager):
        """Test get_diagnostics method."""
        manager, _, _, _ = trained_manager

        diagnostics = manager.get_diagnostics()

        assert "ensemble" in diagnostics
        assert "models" in diagnostics


class TestHistoryAccess:
    """Test history access methods."""

    def test_get_forecast_history_empty(self):
        """Test get_forecast_history when empty."""
        manager = EnsembleManager()
        df = manager.get_forecast_history()

        assert df.empty

    def test_get_forecast_history_after_predictions(self, trained_manager):
        """Test get_forecast_history after predictions."""
        manager, ohlc_df, features_df, _ = trained_manager

        # Make some predictions
        for _ in range(3):
            manager.predict(ohlc_df, features_df)

        df = manager.get_forecast_history()

        assert len(df) == 3
        assert "label" in df.columns
        assert "confidence" in df.columns

    def test_get_error_log_empty(self):
        """Test get_error_log when empty."""
        manager = EnsembleManager()
        df = manager.get_error_log()

        assert df.empty


class TestExportConfig:
    """Test configuration export."""

    def test_export_config(self, trained_manager):
        """Test export_config method."""
        manager, _, _, _ = trained_manager

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "config.json"
            manager.export_config(str(filepath))

            assert filepath.exists()

            with open(filepath) as f:
                config = json.load(f)

            assert "horizon" in config
            assert "weights" in config
            assert "models" in config


class TestDataclasses:
    """Test dataclasses."""

    def test_forecast_result(self):
        """Test ForecastResult dataclass."""
        result = ForecastResult(
            timestamp="2023-01-01",
            label="Bullish",
            confidence=0.8,
            probabilities={"bullish": 0.8, "neutral": 0.15, "bearish": 0.05},
            forecast_return=0.02,
            forecast_volatility=0.015,
            ci_lower=-0.01,
            ci_upper=0.05,
            agreement=0.9,
            n_models=3,
            weights={"rf": 0.5, "gb": 0.5},
            component_predictions={},
        )

        assert result.label == "Bullish"
        assert result.confidence == 0.8

    def test_error_record(self):
        """Test ErrorRecord dataclass."""
        record = ErrorRecord(
            timestamp="2023-01-01",
            operation="predict",
            model="rf",
            error="Test error",
        )

        assert record.operation == "predict"
        assert record.error == "Test error"


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, sample_data):
        """Test complete workflow."""
        ohlc_df, features_df, labels = sample_data

        # 1. Initialize
        manager = EnsembleManager(
            horizon="1D",
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,
            enable_lstm=False,
        )

        # 2. Train
        status = manager.train(ohlc_df, features_df, labels)
        assert sum(status.values()) > 0

        # 3. Predict
        result = manager.predict(ohlc_df, features_df)
        assert result.label in ["Bullish", "Neutral", "Bearish"]

        # 4. Generate forecast
        forecast = manager.generate_forecast(ohlc_df, features_df)
        assert "points" in forecast

        # 5. Get status
        status = manager.get_status()
        assert status["is_trained"]

        # 6. Get history
        history = manager.get_forecast_history()
        assert len(history) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
