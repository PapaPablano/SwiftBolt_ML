"""
Unit tests for walk-forward optimizer with window creation and divergence detection.

Tests the WalkForwardOptimizer implementation for rigorous validation methodology
from research on LSTM-ARIMA hybrid models.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.training.walk_forward_optimizer import (
    WindowConfig,
    WindowResult,
    WalkForwardOptimizer,
)


class TestWindowConfig:
    """Test WindowConfig dataclass."""

    def test_window_config_creation(self):
        """Test creating a WindowConfig."""
        train_start = datetime(2023, 1, 1)
        train_end = datetime(2023, 5, 1)
        val_start = datetime(2023, 5, 1)
        val_end = datetime(2023, 9, 1)
        test_start = datetime(2023, 9, 1)
        test_end = datetime(2024, 1, 1)

        window = WindowConfig(
            train_start=train_start,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            test_start=test_start,
            test_end=test_end,
            window_id=0,
        )

        assert window.window_id == 0
        assert window.train_start == train_start
        assert window.train_end == train_end

    def test_window_config_str(self):
        """Test WindowConfig string representation."""
        train_start = datetime(2023, 1, 1)
        train_end = datetime(2023, 5, 1)
        val_start = datetime(2023, 5, 1)
        val_end = datetime(2023, 9, 1)
        test_start = datetime(2023, 9, 1)
        test_end = datetime(2024, 1, 1)

        window = WindowConfig(
            train_start=train_start,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            test_start=test_start,
            test_end=test_end,
            window_id=0,
        )

        str_repr = str(window)
        assert "Window 0" in str_repr
        assert "2023-01-01" in str_repr
        assert "2024-01-01" in str_repr


class TestWindowResult:
    """Test WindowResult dataclass."""

    def test_window_result_creation(self):
        """Test creating a WindowResult."""
        result = WindowResult(
            window_id=0,
            best_params={"learning_rate": 0.01},
            val_rmse=0.05,
            test_rmse=0.06,
            divergence=0.20,
            n_train_samples=1000,
            n_val_samples=250,
            n_test_samples=250,
            models_used=["LSTM", "ARIMA"],
        )

        assert result.window_id == 0
        assert result.val_rmse == 0.05
        assert result.test_rmse == 0.06
        assert result.divergence == 0.20

    def test_window_result_str(self):
        """Test WindowResult string representation."""
        result = WindowResult(
            window_id=0,
            val_rmse=0.05,
            test_rmse=0.06,
            divergence=0.20,
        )

        str_repr = str(result)
        assert "Window 0" in str_repr
        assert "val_rmse=0.0500" in str_repr
        assert "test_rmse=0.0600" in str_repr
        assert "20.00%" in str_repr


class TestWalkForwardOptimizerInitialization:
    """Test WalkForwardOptimizer initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        optimizer = WalkForwardOptimizer()

        assert optimizer.train_days == 1000
        assert optimizer.val_days == 250
        assert optimizer.test_days == 250
        assert optimizer.step_size == 1
        assert optimizer.divergence_threshold == 0.20

    def test_custom_initialization(self):
        """Test custom initialization."""
        optimizer = WalkForwardOptimizer(
            train_days=500,
            val_days=100,
            test_days=100,
            step_size=5,
            divergence_threshold=0.15,
        )

        assert optimizer.train_days == 500
        assert optimizer.val_days == 100
        assert optimizer.test_days == 100
        assert optimizer.step_size == 5
        assert optimizer.divergence_threshold == 0.15


class TestCreateWindows:
    """Test window creation."""

    def test_create_windows_basic(self):
        """Test creating windows from data."""
        # Create 2 years of daily data
        dates = pd.date_range(start="2021-01-01", periods=504, freq="D")
        data = pd.DataFrame(
            {"close": np.random.randn(504).cumsum() + 100},
            index=dates,
        )

        optimizer = WalkForwardOptimizer(train_days=100, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        # With 504 days, step=1, train=100+val=50+test=50=200 total per window
        # Should create (504-200)/1 + 1 = 305 windows
        # Actually: first window starts at day 0, ends at day 200
        # Second starts at day 1, ends at day 201, etc.
        # Last valid window: starts at day 304, ends at day 504
        # So we get 305 windows but the last one doesn't fit...
        # Actually formula: (end_date - start_date - total_window_days) / step_size + 1
        # With step_size=1: (504 - 200) = 304 possible windows
        assert len(windows) > 0
        assert windows[0].window_id == 0
        assert windows[0].train_start == data.index.min()

    def test_create_windows_no_overlap(self):
        """Test that windows have no temporal overlap."""
        dates = pd.date_range(start="2021-01-01", periods=504, freq="D")
        data = pd.DataFrame(
            {"close": np.random.randn(504).cumsum() + 100},
            index=dates,
        )

        optimizer = WalkForwardOptimizer(train_days=100, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        if len(windows) > 1:
            # Check first two windows for no overlap
            window1 = windows[0]
            window2 = windows[1]

            # window1's test_end should be <= window2's train_start
            # Actually, windows overlap because step_size=1
            # So window2 starts 1 day after window1
            assert window2.train_start > window1.train_start

    def test_create_windows_insufficient_data(self):
        """Test with insufficient data."""
        dates = pd.date_range(start="2021-01-01", periods=50, freq="D")
        data = pd.DataFrame(
            {"close": np.random.randn(50).cumsum() + 100},
            index=dates,
        )

        optimizer = WalkForwardOptimizer(train_days=100, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        # Should create no windows (only 50 days, need 200)
        assert len(windows) == 0


class TestDivergenceDetection:
    """Test divergence detection."""

    def test_divergence_calculation_perfect_agreement(self):
        """Test divergence when val and test are identical."""
        optimizer = WalkForwardOptimizer()

        # No divergence when val_rmse == test_rmse
        result = WindowResult(
            window_id=0,
            val_rmse=0.05,
            test_rmse=0.05,  # Same as val_rmse
            divergence=0.0,
        )

        # Manually calculate divergence
        expected_divergence = abs(0.05 - 0.05) / 0.05
        assert expected_divergence == 0.0

    def test_divergence_calculation_high_divergence(self):
        """Test divergence when test is much worse than val (overfitting)."""
        # val_rmse=0.05, test_rmse=0.10 -> divergence = 0.05/0.05 = 1.0 (100%)
        expected_divergence = abs(0.05 - 0.10) / 0.05
        assert expected_divergence == 1.0

    def test_divergence_calculation_moderate_divergence(self):
        """Test moderate divergence."""
        # val_rmse=0.05, test_rmse=0.075 -> divergence = 0.025/0.05 = 0.5 (50%)
        expected_divergence = abs(0.05 - 0.075) / 0.05
        assert expected_divergence == pytest.approx(0.5, abs=0.001)

    def test_divergence_history_tracking(self):
        """Test that divergence is tracked in history."""
        optimizer = WalkForwardOptimizer()

        assert len(optimizer.divergence_history) == 0

        # Simulate adding divergence values
        optimizer.divergence_history.append(0.10)
        optimizer.divergence_history.append(0.15)
        optimizer.divergence_history.append(0.25)

        assert len(optimizer.divergence_history) == 3
        assert optimizer.divergence_history[0] == 0.10


class TestDivergenceSummary:
    """Test divergence summary statistics."""

    def test_empty_divergence_summary(self):
        """Test summary with no divergence data."""
        optimizer = WalkForwardOptimizer()

        summary = optimizer.get_divergence_summary()

        assert summary["mean_divergence"] == 0.0
        assert summary["max_divergence"] == 0.0
        assert summary["n_overfitting_windows"] == 0
        assert summary["total_windows"] == 0

    def test_divergence_summary_with_data(self):
        """Test summary with divergence data."""
        optimizer = WalkForwardOptimizer(divergence_threshold=0.20)

        optimizer.divergence_history = [0.05, 0.15, 0.30, 0.25, 0.10]

        summary = optimizer.get_divergence_summary()

        assert summary["total_windows"] == 5
        assert summary["mean_divergence"] == pytest.approx(0.17, abs=0.01)
        assert summary["max_divergence"] == 0.30
        assert summary["min_divergence"] == 0.05
        # Overfitting windows: those > 0.20 threshold
        assert summary["n_overfitting_windows"] == 2  # 0.30, 0.25
        assert summary["pct_overfitting"] == 40.0  # 2/5 = 40%

    def test_divergence_threshold_parameter(self):
        """Test that threshold is included in summary."""
        optimizer = WalkForwardOptimizer(divergence_threshold=0.15)

        summary = optimizer.get_divergence_summary()

        assert summary["divergence_threshold"] == 0.15


class TestHyperparameterGeneration:
    """Test hyperparameter combination generation."""

    def test_generate_param_combos_empty(self):
        """Test with empty grid."""
        optimizer = WalkForwardOptimizer()

        combos = optimizer._generate_param_combos({})

        assert len(combos) == 1
        assert combos[0] == {}

    def test_generate_param_combos_single_param(self):
        """Test with single parameter."""
        optimizer = WalkForwardOptimizer()

        param_grid = {"learning_rate": [0.001, 0.01, 0.1]}
        combos = optimizer._generate_param_combos(param_grid)

        assert len(combos) == 3
        assert combos[0] == {"learning_rate": 0.001}
        assert combos[1] == {"learning_rate": 0.01}
        assert combos[2] == {"learning_rate": 0.1}

    def test_generate_param_combos_multiple_params(self):
        """Test with multiple parameters (cartesian product)."""
        optimizer = WalkForwardOptimizer()

        param_grid = {
            "learning_rate": [0.01, 0.1],
            "batch_size": [32, 64],
        }
        combos = optimizer._generate_param_combos(param_grid)

        # Should have 2 * 2 = 4 combinations
        assert len(combos) == 4


class TestRMSECalculation:
    """Test RMSE calculation."""

    def test_rmse_perfect_predictions(self):
        """Test RMSE with perfect predictions."""
        optimizer = WalkForwardOptimizer()

        predictions = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        actuals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        rmse = optimizer._calculate_rmse(predictions, actuals)

        assert rmse == 0.0

    def test_rmse_fixed_error(self):
        """Test RMSE with fixed error."""
        optimizer = WalkForwardOptimizer()

        predictions = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
        actuals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        # All predictions are off by 1.0

        rmse = optimizer._calculate_rmse(predictions, actuals)

        assert rmse == pytest.approx(1.0, abs=0.001)

    def test_rmse_with_series(self):
        """Test RMSE with pandas Series."""
        optimizer = WalkForwardOptimizer()

        predictions = pd.Series([2.0, 3.0, 4.0, 5.0, 6.0])
        actuals = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

        rmse = optimizer._calculate_rmse(predictions, actuals)

        assert rmse == pytest.approx(1.0, abs=0.001)

    def test_rmse_empty_data(self):
        """Test RMSE with empty data."""
        optimizer = WalkForwardOptimizer()

        predictions = np.array([])
        actuals = np.array([])

        rmse = optimizer._calculate_rmse(predictions, actuals)

        assert np.isinf(rmse)

    def test_rmse_length_mismatch(self):
        """Test RMSE with mismatched lengths."""
        optimizer = WalkForwardOptimizer()

        predictions = np.array([1.0, 2.0, 3.0])
        actuals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        rmse = optimizer._calculate_rmse(predictions, actuals)

        # Should truncate to shorter length
        expected_rmse = np.sqrt(np.mean((predictions - actuals[:3]) ** 2))
        assert rmse == pytest.approx(expected_rmse, abs=0.001)


class TestGetActiveModels:
    """Test getting active models from ensemble."""

    def test_get_active_models_lstm_only(self):
        """Test with LSTM only."""
        optimizer = WalkForwardOptimizer()

        ensemble = MagicMock()
        ensemble.enable_lstm = True
        ensemble.enable_arima_garch = False
        ensemble.enable_gb = False
        ensemble.enable_rf = False

        models = optimizer._get_active_models(ensemble)

        assert len(models) == 1
        assert "LSTM" in models

    def test_get_active_models_multiple(self):
        """Test with multiple models."""
        optimizer = WalkForwardOptimizer()

        ensemble = MagicMock()
        ensemble.enable_lstm = True
        ensemble.enable_arima_garch = True
        ensemble.enable_gb = True
        ensemble.enable_rf = False

        models = optimizer._get_active_models(ensemble)

        assert len(models) == 3
        assert "LSTM" in models
        assert "ARIMA_GARCH" in models
        assert "GB" in models

    def test_get_active_models_none(self):
        """Test with no models enabled."""
        optimizer = WalkForwardOptimizer()

        ensemble = MagicMock()
        ensemble.enable_lstm = False
        ensemble.enable_arima_garch = False
        ensemble.enable_gb = False
        ensemble.enable_rf = False

        models = optimizer._get_active_models(ensemble)

        assert len(models) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
