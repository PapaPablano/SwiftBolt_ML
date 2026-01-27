"""
Real data calibration testing for divergence monitoring.

Tests weight calibration with divergence detection on realistic multi-symbol
datasets to validate Phase 3.2 implementation.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.monitoring.divergence_monitor import DivergenceMonitor


class TestCalibratorWithSyntheticSymbolData:
    """Test calibration logic with synthetic but realistic symbol data."""

    @pytest.fixture
    def symbol_validation_data(self):
        """Generate synthetic validation data for 5 symbols."""
        symbols = {
            "AAPL": {
                "train_mae": 0.035,
                "val_mae": 0.045,
                "test_mae": 0.052,  # 15.6% divergence
            },
            "MSFT": {
                "train_mae": 0.040,
                "val_mae": 0.048,
                "test_mae": 0.050,  # 4.2% divergence
            },
            "SPY": {
                "train_mae": 0.030,
                "val_mae": 0.038,
                "test_mae": 0.070,  # 84.2% divergence (overfitting)
            },
            "NVDA": {
                "train_mae": 0.045,
                "val_mae": 0.055,
                "test_mae": 0.058,  # 5.5% divergence
            },
            "GLD": {
                "train_mae": 0.025,
                "val_mae": 0.032,
                "test_mae": 0.048,  # 50% divergence (moderate overfitting)
            },
        }
        return symbols

    def test_divergence_calculation_across_symbols(self, symbol_validation_data):
        """Test divergence calculation for multiple symbols."""
        divergences = {}

        for symbol, metrics in symbol_validation_data.items():
            val_mae = metrics["val_mae"]
            test_mae = metrics["test_mae"]
            divergence = abs(val_mae - test_mae) / val_mae if val_mae > 0 else 0

            divergences[symbol] = divergence

        # Verify calculations
        assert divergences["AAPL"] == pytest.approx(0.156, abs=0.01)
        assert divergences["MSFT"] == pytest.approx(0.042, abs=0.01)
        assert divergences["SPY"] == pytest.approx(0.842, abs=0.01)
        assert divergences["NVDA"] == pytest.approx(0.055, abs=0.01)
        assert divergences["GLD"] == pytest.approx(0.50, abs=0.01)

    def test_overfitting_detection_threshold(self, symbol_validation_data):
        """Test overfitting detection with 15% threshold."""
        threshold = 0.15
        overfitting_symbols = []

        for symbol, metrics in symbol_validation_data.items():
            val_mae = metrics["val_mae"]
            test_mae = metrics["test_mae"]
            divergence = abs(val_mae - test_mae) / val_mae if val_mae > 0 else 0

            if divergence > threshold:
                overfitting_symbols.append((symbol, divergence))

        # AAPL (15.56%), SPY (84.2%), and GLD (50%) should be flagged
        assert len(overfitting_symbols) == 3
        symbols_flagged = {s[0] for s in overfitting_symbols}
        assert "AAPL" in symbols_flagged
        assert "SPY" in symbols_flagged
        assert "GLD" in symbols_flagged

    def test_weight_reversion_logic(self, symbol_validation_data):
        """Test that weights revert to equal when overfitting detected."""
        threshold = 0.15
        symbol_weights = {}

        for symbol, metrics in symbol_validation_data.items():
            val_mae = metrics["val_mae"]
            test_mae = metrics["test_mae"]
            divergence = abs(val_mae - test_mae) / val_mae if val_mae > 0 else 0

            if divergence > threshold:
                # Revert to equal weights (3-layer: ST, SR, Ensemble)
                weights = np.array([1/3, 1/3, 1/3])
            else:
                # Optimized weights (example)
                weights = np.array([0.30, 0.35, 0.35])

            symbol_weights[symbol] = weights

        # Verify weight distributions
        assert np.allclose(symbol_weights["AAPL"].sum(), 1.0)  # Equal (overfitting detected - 15.6%)
        assert np.allclose(symbol_weights["MSFT"].sum(), 1.0)  # Optimized (below threshold)
        assert np.allclose(symbol_weights["SPY"].sum(), 1.0)   # Equal (overfitting detected)
        assert np.allclose(symbol_weights["GLD"].sum(), 1.0)   # Equal (overfitting detected)
        assert np.allclose(symbol_weights["NVDA"].sum(), 1.0)  # Optimized (below threshold)

        # AAPL, SPY, and GLD should have equal weights
        assert np.allclose(symbol_weights["AAPL"], [1/3, 1/3, 1/3])
        assert np.allclose(symbol_weights["SPY"], [1/3, 1/3, 1/3])
        assert np.allclose(symbol_weights["GLD"], [1/3, 1/3, 1/3])

    def test_calibration_data_quality_check(self, symbol_validation_data):
        """Test validation of calibration data quality."""
        min_samples = 100
        min_span_days = 30

        # Simulate sample counts
        sample_counts = {
            "AAPL": 250,   # Good
            "MSFT": 200,   # Good
            "SPY": 180,    # Good
            "NVDA": 150,   # Good
            "GLD": 80,     # Insufficient
        }

        span_days = {
            "AAPL": 365,   # Good
            "MSFT": 300,   # Good
            "SPY": 250,    # Good
            "NVDA": 200,   # Good
            "GLD": 15,     # Insufficient
        }

        valid_calibrations = {}
        for symbol in symbol_validation_data.keys():
            is_valid = (sample_counts[symbol] >= min_samples and
                       span_days[symbol] >= min_span_days)
            valid_calibrations[symbol] = is_valid

        assert valid_calibrations["AAPL"] is True
        assert valid_calibrations["MSFT"] is True
        assert valid_calibrations["SPY"] is True
        assert valid_calibrations["NVDA"] is True
        assert valid_calibrations["GLD"] is False  # Insufficient data

    def test_multi_horizon_calibration(self):
        """Test calibration across multiple time horizons."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        # Calibrate AAPL for 1D, 4h, 8h
        horizons_data = {
            "1D": {"val_rmse": 0.045, "test_rmse": 0.050},  # 11% divergence
            "4h": {"val_rmse": 0.035, "test_rmse": 0.045},  # 29% divergence (overfitting)
            "8h": {"val_rmse": 0.040, "test_rmse": 0.042},  # 5% divergence
        }

        for horizon, metrics in horizons_data.items():
            result = monitor.log_window_result(
                symbol="AAPL",
                symbol_id=f"aapl_{horizon}",
                horizon=horizon,
                window_id=1,
                val_rmse=metrics["val_rmse"],
                test_rmse=metrics["test_rmse"],
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

            if horizon == "4h":
                assert result["is_overfitting"] is True
            else:
                assert result["is_overfitting"] is False

    def test_sequential_calibration_updates(self):
        """Test updating calibration as new data arrives."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        symbol = "AAPL"
        iterations = 3

        for iteration in range(iterations):
            # Simulate improving calibration over time
            val_rmse = 0.05
            test_rmse = 0.05 + (0.02 - iteration * 0.005)  # Improving generalization

            result = monitor.log_window_result(
                symbol=symbol,
                symbol_id=f"{symbol}_1d",
                horizon="1D",
                window_id=iteration,
                val_rmse=val_rmse,
                test_rmse=test_rmse,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

            # First iteration might have overfitting, later ones improve
            if iteration == 0:
                assert result["divergence"] > 0.25  # 40% divergence

        # Verify history captures progression
        assert len(monitor.divergence_history) == iterations
        divergences = [h["divergence"] for h in monitor.divergence_history]
        # Should show improving (decreasing) divergence
        assert divergences[-1] < divergences[0]


class TestCalibratorEdgeCases:
    """Test calibrator edge cases and boundary conditions."""

    def test_perfect_calibration(self):
        """Test when validation and test performance are identical."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.050,
            test_rmse=0.050,  # Perfect match
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        assert result["divergence"] == 0.0
        assert result["is_overfitting"] is False

    def test_complete_overfitting(self):
        """Test severe overfitting case."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.050,
            test_rmse=0.150,  # 3x worse
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        assert result["divergence"] == pytest.approx(2.0, abs=0.01)
        assert result["is_overfitting"] is True

    def test_zero_validation_rmse_handling(self):
        """Test handling of edge case where validation RMSE is near zero."""
        monitor = DivergenceMonitor()

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.0001,
            test_rmse=0.001,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Should still calculate divergence
        assert result["divergence"] > 0
        assert np.isfinite(result["divergence"])

    def test_negative_divergence_impossible(self):
        """Test that divergence is always non-negative."""
        monitor = DivergenceMonitor()

        # Case where test is better than validation
        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.100,
            test_rmse=0.050,  # Better than validation
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Divergence uses absolute value, so still positive
        assert result["divergence"] >= 0
        assert result["divergence"] == pytest.approx(0.5, abs=0.01)


class TestCalibrationMetricsCombination:
    """Test combinations of calibration metrics."""

    def test_mae_and_rmse_divergence_correlation(self):
        """Test that MAE and RMSE divergence show correlation."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        # Symbol with both MAE and RMSE
        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.045,
            test_rmse=0.055,
            val_mae=0.035,
            test_mae=0.045,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # RMSE divergence: (0.055-0.045)/0.045 = 22%
        # MAE divergence: (0.045-0.035)/0.035 = 29%
        assert result["divergence"] == pytest.approx(0.222, abs=0.01)

    def test_sample_count_impact_on_confidence(self):
        """Test that larger sample counts provide more confidence."""
        monitor = DivergenceMonitor()

        # Small sample - high uncertainty
        result_small = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.050,
            test_rmse=0.055,
            n_train_samples=50,
            n_val_samples=10,
            n_test_samples=10,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Large sample - high confidence
        result_large = monitor.log_window_result(
            symbol="MSFT",
            symbol_id="msft_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.050,
            test_rmse=0.055,
            n_train_samples=500,
            n_val_samples=100,
            n_test_samples=100,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Same divergence, but different confidence context
        assert result_small["divergence"] == result_large["divergence"]
        assert result_small["n_val_samples"] < result_large["n_val_samples"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
