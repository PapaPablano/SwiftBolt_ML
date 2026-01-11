"""Unit tests for Walk-Forward Ensemble Backtester."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.models.walk_forward_ensemble import (
    BacktestResult,
    EnsembleMetrics,
    WalkForwardEnsemble,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data."""
    np.random.seed(42)
    n = 200

    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    df = pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        }
    )

    return df


@pytest.fixture
def sample_features_labels(sample_ohlc_df):
    """Create sample features and labels."""
    df = sample_ohlc_df.copy()

    # Features
    df["return_1d"] = df["close"].pct_change()
    df["return_5d"] = df["close"].pct_change(5)
    df["sma_20"] = df["close"].rolling(20).mean()
    df["vol_20"] = df["return_1d"].rolling(20).std()
    df = df.dropna()

    features = df[["return_1d", "return_5d", "sma_20", "vol_20"]]

    # Labels
    fwd = df["close"].pct_change().shift(-1)
    labels = fwd.apply(
        lambda x: "bullish" if x > 0.01 else "bearish" if x < -0.01 else "neutral"
    ).iloc[:-1]

    features = features.iloc[:-1]
    ohlc = df.iloc[:-1]

    return ohlc, features, labels


@pytest.fixture
def mock_ensemble():
    """Create mock ensemble for testing."""
    ensemble = MagicMock()
    ensemble.model_trained = {"rf": True, "gb": True, "arima_garch": True}
    ensemble.train = MagicMock(return_value=ensemble)
    ensemble.predict = MagicMock(
        return_value={
            "label": "Bullish",
            "confidence": 0.7,
            "probabilities": {"bullish": 0.7, "neutral": 0.2, "bearish": 0.1},
            "agreement": 0.8,
            "component_predictions": {
                "rf": {"label": "Bullish"},
                "gb": {"label": "Bullish"},
                "arima_garch": {"label": "Neutral"},
            },
        }
    )
    return ensemble


class TestWalkForwardEnsembleInit:
    """Test initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        wfe = WalkForwardEnsemble()

        assert wfe.initial_train_size == 200
        assert wfe.test_size == 1
        assert wfe.refit_frequency == 20
        assert wfe.weight_update_frequency == 10

    def test_custom_initialization(self):
        """Test custom initialization."""
        wfe = WalkForwardEnsemble(
            initial_train_size=100,
            test_size=5,
            refit_frequency=10,
            weight_update_frequency=5,
        )

        assert wfe.initial_train_size == 100
        assert wfe.test_size == 5
        assert wfe.refit_frequency == 10


class TestEnsembleMetrics:
    """Test EnsembleMetrics class."""

    def test_update_metrics(self):
        """Test updating metrics."""
        metrics = EnsembleMetrics()

        metrics.update(
            prediction="Bullish",
            actual="Bullish",
            confidence=0.8,
            agreement=0.9,
            weights={"rf": 0.5, "gb": 0.5},
        )

        assert len(metrics.predictions) == 1
        assert metrics.predictions[0] == "Bullish"
        assert metrics.confidences[0] == 0.8

    def test_get_metrics_empty(self):
        """Test get_metrics with no data."""
        metrics = EnsembleMetrics()
        result = metrics.get_metrics()

        assert "error" in result

    def test_get_metrics_accuracy(self):
        """Test accuracy calculation."""
        metrics = EnsembleMetrics()

        # Add some correct predictions
        for _ in range(7):
            metrics.update("Bullish", "Bullish", 0.8, 0.9, {"rf": 0.5})

        # Add some incorrect
        for _ in range(3):
            metrics.update("Bullish", "Bearish", 0.6, 0.7, {"rf": 0.5})

        result = metrics.get_metrics()
        assert result["accuracy"] == 0.7


class TestBacktestResult:
    """Test BacktestResult dataclass."""

    def test_create_result(self):
        """Test creating a backtest result."""
        result = BacktestResult(
            timestamp="2023-01-01",
            step=0,
            forecast_label="Bullish",
            forecast_confidence=0.8,
            actual_direction="Bullish",
            is_correct=True,
            probabilities={"bullish": 0.8, "neutral": 0.1, "bearish": 0.1},
            weights={"rf": 0.5, "gb": 0.5},
            model_predictions={"rf": "Bullish", "gb": "Bullish"},
            agreement=0.9,
        )

        assert result.is_correct
        assert result.forecast_label == "Bullish"


class TestBacktestExecution:
    """Test backtest execution."""

    def test_insufficient_data(self, mock_ensemble):
        """Test error on insufficient data."""
        wfe = WalkForwardEnsemble(initial_train_size=100)

        small_df = pd.DataFrame(
            {
                "ts": pd.date_range("2023-01-01", periods=50, freq="D"),
                "close": np.random.randn(50) + 100,
            }
        )

        with pytest.raises(ValueError, match="Insufficient"):
            wfe.run_backtest(
                ohlc_df=small_df,
                features_df=small_df[["close"]],
                labels=pd.Series(["neutral"] * 50),
                ensemble=mock_ensemble,
            )

    def test_backtest_runs(self, sample_features_labels, mock_ensemble):
        """Test that backtest runs successfully."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(
            initial_train_size=50,
            refit_frequency=20,
        )

        results = wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        assert len(results) > 0
        assert "forecast" in results.columns
        assert "actual" in results.columns

    def test_backtest_calls_train(self, sample_features_labels, mock_ensemble):
        """Test that backtest calls train on ensemble."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(
            initial_train_size=50,
            refit_frequency=10,
        )

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        assert mock_ensemble.train.called

    def test_backtest_calls_predict(self, sample_features_labels, mock_ensemble):
        """Test that backtest calls predict on ensemble."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(
            initial_train_size=50,
            refit_frequency=20,
        )

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        assert mock_ensemble.predict.called


class TestResultsAccess:
    """Test results access methods."""

    def test_get_results_dataframe_empty(self):
        """Test get_results_dataframe with no results."""
        wfe = WalkForwardEnsemble()
        df = wfe.get_results_dataframe()

        assert df.empty

    def test_get_metrics_after_backtest(self, sample_features_labels, mock_ensemble):
        """Test get_metrics after backtest."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(initial_train_size=50)

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        metrics = wfe.get_metrics()

        assert "accuracy" in metrics
        assert "n_predictions" in metrics

    def test_get_weight_evolution(self, sample_features_labels, mock_ensemble):
        """Test weight evolution tracking."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(
            initial_train_size=50,
            weight_update_frequency=10,
        )

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        weight_df = wfe.get_weight_evolution()

        # Should have recorded weight updates
        assert len(weight_df) > 0 or len(wfe.weight_history) > 0

    def test_get_confusion_matrix(self, sample_features_labels, mock_ensemble):
        """Test confusion matrix generation."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(initial_train_size=50)

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        cm = wfe.get_confusion_matrix()

        assert "Bullish" in cm.index
        assert "Bearish" in cm.index
        assert "Neutral" in cm.index

    def test_get_accuracy_by_confidence(self, sample_features_labels, mock_ensemble):
        """Test accuracy by confidence stratification."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(initial_train_size=50)

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        acc_df = wfe.get_accuracy_by_confidence(n_bins=5)

        assert "accuracy" in acc_df.columns
        assert "count" in acc_df.columns

    def test_get_summary(self, sample_features_labels, mock_ensemble):
        """Test get_summary method."""
        ohlc_df, features_df, labels = sample_features_labels

        wfe = WalkForwardEnsemble(initial_train_size=50)

        wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=mock_ensemble,
        )

        summary = wfe.get_summary()

        assert "metrics" in summary
        assert "n_steps" in summary


class TestWeightOptimization:
    """Test weight optimization during backtest."""

    def test_initial_weights_equal(self, mock_ensemble):
        """Test that initial weights are equal."""
        wfe = WalkForwardEnsemble()
        weights = wfe._get_initial_weights(mock_ensemble)

        assert len(weights) == 3
        assert all(abs(w - 1 / 3) < 0.01 for w in weights.values())


class TestEdgeCases:
    """Test edge cases."""

    def test_handles_prediction_errors(self, sample_features_labels):
        """Test handling of prediction errors."""
        ohlc_df, features_df, labels = sample_features_labels

        # Create mock that fails sometimes
        failing_ensemble = MagicMock()
        failing_ensemble.model_trained = {"rf": True, "gb": True}
        failing_ensemble.train = MagicMock()

        call_count = [0]

        def predict_with_errors(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 5 == 0:
                raise ValueError("Prediction failed")
            return {
                "label": "Neutral",
                "confidence": 0.5,
                "probabilities": {"bullish": 0.3, "neutral": 0.4, "bearish": 0.3},
                "agreement": 0.7,
                "component_predictions": {},
            }

        failing_ensemble.predict = predict_with_errors

        wfe = WalkForwardEnsemble(initial_train_size=50)

        # Should not raise, just skip failed predictions
        results = wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=failing_ensemble,
        )

        # Should have some results despite errors
        assert len(results) > 0


class TestIntegration:
    """Integration tests with real ensemble."""

    def test_with_real_ensemble(self, sample_features_labels):
        """Test with actual MultiModelEnsemble."""
        ohlc_df, features_df, labels = sample_features_labels

        # Import real ensemble
        from src.models.multi_model_ensemble import MultiModelEnsemble

        ensemble = MultiModelEnsemble(
            horizon="1D",
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=True,
            enable_prophet=False,  # Faster
            enable_lstm=False,
        )

        wfe = WalkForwardEnsemble(
            initial_train_size=80,
            refit_frequency=50,  # Less frequent for speed
            weight_update_frequency=30,
        )

        results = wfe.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=ensemble,
        )

        assert len(results) > 0

        metrics = wfe.get_metrics()
        assert 0 <= metrics["accuracy"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
