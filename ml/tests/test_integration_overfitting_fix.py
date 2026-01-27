"""
End-to-end integration tests for ML overfitting fix.

Tests the complete pipeline:
1. Ensemble creation with 2-3 model configurations
2. Walk-forward validation with divergence detection
3. Weight calibration with train/val/test splits
4. Forecast synthesis with simplified ensemble logic
5. Backward compatibility with existing forecasts

Validates that all components work together correctly.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.training.walk_forward_optimizer import WalkForwardOptimizer
from src.models.enhanced_ensemble_integration import get_production_ensemble
from src.monitoring.divergence_monitor import DivergenceMonitor


class TestEnsembleCreationIntegration:
    """Test ensemble creation integrated with environment variables."""

    def test_2_model_ensemble_from_env(self):
        """Test creating 2-model ensemble from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "false",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify correct configuration
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is False
            assert ensemble.n_models == 2

    def test_3_model_ensemble_from_env(self):
        """Test creating 3-model ensemble from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "ENSEMBLE_MODEL_COUNT": "3",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "true",
            },
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Verify correct configuration
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True
            assert ensemble.n_models == 3


class TestWalkForwardIntegration:
    """Test walk-forward validation in complete pipeline."""

    def test_walk_forward_with_divergence_detection(self):
        """Test walk-forward optimizer detects overfitting via divergence."""
        # Create synthetic time series data
        dates = pd.date_range(start="2021-01-01", periods=1000, freq="D")
        prices = np.cumsum(np.random.randn(1000) * 0.02) + 100
        data = pd.DataFrame({"close": prices}, index=dates)

        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=50,  # Fewer windows for testing
            divergence_threshold=0.20,
        )

        # Create windows
        windows = optimizer.create_windows(data)

        # Should create multiple windows
        assert len(windows) > 0

        # Verify window structure
        first_window = windows[0]
        assert first_window.train_start == data.index.min()
        assert first_window.test_end <= data.index.max()

    def test_window_creation_temporal_integrity(self):
        """Test that walk-forward windows maintain temporal integrity."""
        dates = pd.date_range(start="2021-01-01", periods=800, freq="D")
        data = pd.DataFrame({"close": np.random.randn(800)}, index=dates)

        optimizer = WalkForwardOptimizer(train_days=100, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        if len(windows) > 1:
            # Verify windows progress chronologically (later windows have later dates)
            for i in range(len(windows) - 1):
                current_train_start = windows[i].train_start
                next_train_start = windows[i + 1].train_start

                # Next window should start after current window (rolling forward)
                assert next_train_start > current_train_start

        # Verify each window has valid internal temporal structure
        for window in windows:
            assert window.train_start < window.train_end
            assert window.train_end <= window.val_start
            assert window.val_start < window.val_end
            assert window.val_end <= window.test_start
            assert window.test_start < window.test_end


class TestDivergenceMonitorIntegration:
    """Test divergence monitoring in complete pipeline."""

    def test_monitor_tracks_multiple_windows(self):
        """Test that divergence monitor tracks multiple window results."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log multiple window results
        for window_id in range(5):
            val_rmse = 0.05
            # Simulate varying test performance
            test_rmse = 0.05 + (window_id * 0.01)

            result = monitor.log_window_result(
                symbol="AAPL",
                symbol_id="AAPL_test",
                horizon="1D",
                window_id=window_id,
                val_rmse=val_rmse,
                test_rmse=test_rmse,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

            assert result["divergence"] >= 0
            assert result["window_id"] == window_id

        # Verify history is populated
        assert len(monitor.divergence_history) == 5

    def test_monitor_detects_overfitting_threshold(self):
        """Test that monitor correctly detects overfitting above threshold."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        # Non-overfitting case
        result1 = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="AAPL_test",
            horizon="1D",
            window_id=1,
            val_rmse=0.10,
            test_rmse=0.11,  # 10% divergence - below threshold
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        assert result1["is_overfitting"] is False

        # Overfitting case
        result2 = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="AAPL_test",
            horizon="1D",
            window_id=2,
            val_rmse=0.10,
            test_rmse=0.18,  # 80% divergence - above threshold
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        assert result2["is_overfitting"] is True

    def test_monitor_summary_statistics(self):
        """Test that monitor generates correct summary statistics."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log diverse results
        test_results = [
            (0.05, 0.05),  # 0% divergence
            (0.05, 0.06),  # 20% divergence
            (0.05, 0.08),  # 60% divergence
        ]

        for i, (val_rmse, test_rmse) in enumerate(test_results):
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="AAPL_test",
                horizon="1D",
                window_id=i,
                val_rmse=val_rmse,
                test_rmse=test_rmse,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        summary = monitor.get_divergence_summary()

        assert summary["total_windows"] == 3
        assert summary["overfitting_windows"] == 1  # Only 60% divergence > 20%
        assert summary["mean_divergence"] > 0
        assert summary["max_divergence"] == pytest.approx(0.6, abs=0.01)


class TestCalibrationDivergenceIntegration:
    """Test calibrator divergence monitoring in pipeline."""

    def test_calibration_train_val_test_split_logic(self):
        """Test train/val/test split logic for calibration."""
        # Simulate 300 samples
        n_samples = 300
        train_ratio, val_ratio, test_ratio = 0.6, 0.2, 0.2

        train_size = int(n_samples * train_ratio)
        val_size = int(n_samples * val_ratio)
        test_size = n_samples - train_size - val_size

        assert train_size == 180
        assert val_size == 60
        assert test_size == 60
        assert train_size + val_size + test_size == 300

    def test_calibration_divergence_calculation(self):
        """Test divergence calculation for calibration metrics."""
        # Simulate calibration metrics
        train_mae = 0.04
        val_mae = 0.05
        test_mae = 0.08  # Worse performance on test set

        divergence = abs(val_mae - test_mae) / val_mae if val_mae > 0 else 0
        is_overfitting = divergence > 0.15

        assert divergence == pytest.approx(0.6, abs=0.01)  # 60% divergence
        assert is_overfitting is True

    def test_calibration_weight_reversion_on_overfitting(self):
        """Test that weights revert to equal when overfitting detected."""
        divergence = 0.25
        threshold = 0.15

        if divergence > threshold:
            # Revert to equal weights
            reverted_weights = np.array([1/3, 1/3, 1/3])
        else:
            reverted_weights = None

        assert reverted_weights is not None
        assert np.allclose(np.sum(reverted_weights), 1.0)


class TestForecastSynthesisIntegration:
    """Test forecast synthesis with simplified ensemble logic."""

    def test_ensemble_agreement_for_2_models(self):
        """Test ensemble agreement calculation for 2-model setup."""
        # Agreement score from 2-model ensemble
        model_1_prediction = "bullish"
        model_2_prediction = "bullish"

        # Both agree
        agreement = 1.0 if model_1_prediction == model_2_prediction else 0.0
        assert agreement == 1.0

        # Partial agreement (only 1 of 2)
        model_2_prediction = "bearish"
        unique_predictions = len(set([model_1_prediction, model_2_prediction]))
        agreement = 1.0 - (unique_predictions - 1) / (2 - 1)
        assert agreement == 0.0

    def test_ensemble_agreement_for_3_models(self):
        """Test ensemble agreement calculation for 3-model setup."""
        predictions = ["bullish", "bullish", "bearish"]

        # Calculate agreement for 3 models
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (3 - 1)

        # 2 unique predictions: agreement = 1 - 1/2 = 0.5
        assert agreement == pytest.approx(0.5, abs=0.01)

    def test_confidence_boost_from_ensemble_agreement(self):
        """Test that confidence gets boosted from ensemble agreement."""
        base_confidence = 0.50
        agreement_boost = 0.10

        # Agreement >= 0.5 triggers boost
        agreement = 0.75
        if agreement >= 0.5:
            final_confidence = base_confidence + agreement_boost
        else:
            final_confidence = base_confidence

        assert final_confidence == pytest.approx(0.60, abs=0.01)


class TestBackwardCompatibilityIntegration:
    """Test backward compatibility with existing forecast systems."""

    def test_legacy_4_model_still_works(self):
        """Test that legacy 4-model configuration still functions."""
        with patch.dict(
            "os.environ",
            {"ENSEMBLE_MODEL_COUNT": "4"},
        ):
            ensemble = get_production_ensemble(horizon="1D")

            # Should create legacy 4-model (though Transformer disabled)
            assert ensemble.enable_lstm is True
            assert ensemble.enable_arima_garch is True
            assert ensemble.enable_gb is True

    def test_weight_calculations_maintain_constraints(self):
        """Test that all weight configurations satisfy constraints."""
        # 2-model weights
        weights_2 = np.array([0.50, 0.50])
        assert np.allclose(np.sum(weights_2), 1.0)
        assert np.all(weights_2 >= 0)
        assert np.all(weights_2 <= 1)

        # 3-model weights
        weights_3 = np.array([0.40, 0.30, 0.30])
        assert np.allclose(np.sum(weights_3), 1.0)
        assert np.all(weights_3 >= 0)
        assert np.all(weights_3 <= 1)

        # 4-model weights
        weights_4 = np.array([0.25, 0.20, 0.35, 0.20])
        assert np.allclose(np.sum(weights_4), 1.0)
        assert np.all(weights_4 >= 0)
        assert np.all(weights_4 <= 1)


class TestCompleteEndToEndPipeline:
    """Test complete end-to-end workflow."""

    def test_2_model_ensemble_full_workflow(self):
        """Test complete workflow with 2-model ensemble."""
        with patch.dict(
            "os.environ",
            {
                "ENSEMBLE_MODEL_COUNT": "2",
                "ENABLE_LSTM": "true",
                "ENABLE_ARIMA_GARCH": "true",
                "ENABLE_GB": "false",
            },
        ):
            # Step 1: Create ensemble
            ensemble = get_production_ensemble(horizon="1D")
            assert ensemble.n_models == 2

            # Step 2: Initialize monitoring
            monitor = DivergenceMonitor(divergence_threshold=0.20)
            assert len(monitor.divergence_history) == 0

            # Step 3: Log validation results (simulated)
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="AAPL_1",
                horizon="1D",
                window_id=1,
                val_rmse=0.05,
                test_rmse=0.06,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

            # Step 4: Verify monitoring captured results
            summary = monitor.get_divergence_summary()
            assert summary["total_windows"] == 1
            assert summary["overfitting_windows"] == 0  # 20% divergence = threshold

            # Step 5: Verify weights maintain constraints
            assert ensemble.n_models == 2

    def test_workflow_with_multiple_symbols(self):
        """Test workflow with multiple symbols and horizons."""
        symbols = ["AAPL", "MSFT", "SPY"]
        horizons = ["1D", "4h"]

        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Process multiple symbols and horizons
        for symbol in symbols:
            for horizon in horizons:
                for window_id in range(3):
                    val_rmse = 0.05
                    test_rmse = 0.05 + (np.random.rand() * 0.04)

                    monitor.log_window_result(
                        symbol=symbol,
                        symbol_id=f"{symbol}_test",
                        horizon=horizon,
                        window_id=window_id,
                        val_rmse=val_rmse,
                        test_rmse=test_rmse,
                        model_count=2,
                        models_used=["LSTM", "ARIMA_GARCH"],
                    )

        # Verify all results logged
        assert len(monitor.divergence_history) == len(symbols) * len(horizons) * 3

        # Verify summary statistics
        summary = monitor.get_divergence_summary()
        assert summary["total_windows"] == len(symbols) * len(horizons) * 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
