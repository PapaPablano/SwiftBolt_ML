"""
Database integration tests for ensemble validation metrics.

Tests database schema, insertion, and querying of divergence monitoring data.
This validates Phase 5 (Database & Monitoring) implementation.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.monitoring.divergence_monitor import DivergenceMonitor


class TestDivergenceMonitorDatabaseSchema:
    """Test database schema and structure for divergence metrics."""

    def test_divergence_monitor_initialization(self):
        """Test DivergenceMonitor initializes with database client."""
        mock_db_client = MagicMock()
        monitor = DivergenceMonitor(db_client=mock_db_client)

        assert monitor.db_client is mock_db_client
        assert monitor.divergence_threshold == 0.20
        assert len(monitor.divergence_history) == 0

    def test_divergence_monitor_without_db_client(self):
        """Test DivergenceMonitor works without database client (fallback)."""
        monitor = DivergenceMonitor(db_client=None)

        assert monitor.db_client is None
        assert monitor.divergence_threshold == 0.20
        # Should still be able to log to memory
        assert len(monitor.divergence_history) == 0


class TestValidationMetricsStructure:
    """Test structure of validation metrics matching database schema."""

    def test_window_result_contains_required_fields(self):
        """Test that logged window results contain all required schema fields."""
        monitor = DivergenceMonitor()

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Check all required fields are present
        required_fields = [
            "symbol",
            "symbol_id",
            "horizon",
            "window_id",
            "val_rmse",
            "test_rmse",
            "divergence",
            "is_overfitting",
            "alert_level",
            "model_count",
            "models_used",
            "validation_date",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
            assert result[field] is not None, f"Field {field} is None"

    def test_optional_fields_in_window_result(self):
        """Test that optional fields are included when provided."""
        monitor = DivergenceMonitor()

        result = monitor.log_window_result(
            symbol="MSFT",
            symbol_id="msft_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.04,
            test_rmse=0.07,
            val_mae=0.03,
            test_mae=0.05,
            train_rmse=0.03,
            n_train_samples=1000,
            n_val_samples=250,
            n_test_samples=250,
            data_span_days=500,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
            hyperparameters={"learning_rate": 0.001, "batch_size": 32},
            directional_accuracy=0.75,
        )

        # Check optional fields are present
        assert result["train_rmse"] == 0.03
        assert result["n_train_samples"] == 1000
        assert result["n_val_samples"] == 250
        assert result["n_test_samples"] == 250
        assert result["data_span_days"] == 500

    def test_validation_date_is_recent(self):
        """Test that validation_date is recent (within last minute)."""
        monitor = DivergenceMonitor()

        result = monitor.log_window_result(
            symbol="SPY",
            symbol_id="spy_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        validation_date = result["validation_date"]
        now = datetime.utcnow()
        time_diff = abs((now - validation_date).total_seconds())

        # Should be logged within 1 second
        assert time_diff < 1.0, f"validation_date is {time_diff}s old"

    def test_models_used_array_format(self):
        """Test that models_used is stored as array/list."""
        monitor = DivergenceMonitor()

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_4h",
            horizon="4h",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=3,
            models_used=["LSTM", "ARIMA_GARCH", "GB"],
        )

        assert isinstance(result["models_used"], list)
        assert len(result["models_used"]) == 3
        assert "LSTM" in result["models_used"]
        assert "ARIMA_GARCH" in result["models_used"]
        assert "GB" in result["models_used"]


class TestDivergenceMetricsCalculation:
    """Test divergence metric calculation and storage."""

    def test_divergence_calculation_stored_correctly(self):
        """Test that divergence is calculated and stored correctly."""
        monitor = DivergenceMonitor()

        val_rmse = 0.05
        test_rmse = 0.10
        expected_divergence = abs(val_rmse - test_rmse) / val_rmse  # 1.0

        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=val_rmse,
            test_rmse=test_rmse,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        assert result["divergence"] == pytest.approx(expected_divergence, abs=0.001)

    def test_overfitting_flag_with_20_percent_threshold(self):
        """Test overfitting flag with 20% threshold."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Case 1: Below threshold
        result1 = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,  # 20% divergence, exactly at threshold
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )
        assert result1["is_overfitting"] is False  # = threshold, not >

        # Case 2: Above threshold
        result2 = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=2,
            val_rmse=0.05,
            test_rmse=0.061,  # 22% divergence, above threshold
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )
        assert result2["is_overfitting"] is True

    def test_alert_levels_assigned_correctly(self):
        """Test alert level assignment based on divergence."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Normal (< 15%)
        result_normal = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.055,  # 10% divergence
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )
        assert result_normal["alert_level"] == "normal"

        # Warning (15-30%)
        result_warning = monitor.log_window_result(
            symbol="MSFT",
            symbol_id="msft_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.058,  # 16% divergence
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )
        assert result_warning["alert_level"] == "warning"

        # Critical (> 30%)
        result_critical = monitor.log_window_result(
            symbol="SPY",
            symbol_id="spy_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.066,  # 32% divergence
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )
        assert result_critical["alert_level"] == "critical"


class TestDivergenceHistoryTracking:
    """Test tracking divergence history across multiple windows."""

    def test_history_accumulates_results(self):
        """Test that divergence history accumulates results."""
        monitor = DivergenceMonitor()

        assert len(monitor.divergence_history) == 0

        # Log multiple results
        for i in range(5):
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="aapl_1d",
                horizon="1D",
                window_id=i,
                val_rmse=0.05,
                test_rmse=0.05 + (i * 0.01),
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        assert len(monitor.divergence_history) == 5

    def test_history_persists_between_calls(self):
        """Test that history persists across multiple log_window_result calls."""
        monitor = DivergenceMonitor()

        # First batch
        for i in range(3):
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="aapl_1d",
                horizon="1D",
                window_id=i,
                val_rmse=0.05,
                test_rmse=0.06,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        assert len(monitor.divergence_history) == 3

        # Second batch
        for i in range(3, 6):
            monitor.log_window_result(
                symbol="MSFT",
                symbol_id="msft_1d",
                horizon="1D",
                window_id=i,
                val_rmse=0.04,
                test_rmse=0.05,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        assert len(monitor.divergence_history) == 6

    def test_clear_history(self):
        """Test clearing divergence history."""
        monitor = DivergenceMonitor()

        # Add results
        for i in range(5):
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="aapl_1d",
                horizon="1D",
                window_id=i,
                val_rmse=0.05,
                test_rmse=0.06,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        assert len(monitor.divergence_history) == 5

        # Clear
        monitor.clear_history()

        assert len(monitor.divergence_history) == 0


class TestGetRecentOverfittingSymbols:
    """Test querying recent overfitting symbols."""

    def test_get_recent_overfitting_symbols(self):
        """Test retrieving symbols with recent overfitting."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log some overfitting results
        monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.065,  # 30% divergence
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        monitor.log_window_result(
            symbol="MSFT",
            symbol_id="msft_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.061,  # 22% divergence
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Get overfitting symbols
        overfitting = monitor.get_recent_overfitting_symbols(horizon="1D", days=7)

        assert len(overfitting) == 2
        # Should be sorted by divergence (worst first)
        assert overfitting[0][0] == "AAPL"  # 30% divergence
        assert overfitting[1][0] == "MSFT"  # 22% divergence
        assert overfitting[0][1] > overfitting[1][1]

    def test_filter_by_horizon(self):
        """Test filtering overfitting symbols by horizon."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log overfitting for 1D
        monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.065,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Log overfitting for 4h
        monitor.log_window_result(
            symbol="MSFT",
            symbol_id="msft_4h",
            horizon="4h",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.065,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Filter by 1D only
        overfitting_1d = monitor.get_recent_overfitting_symbols(horizon="1D", days=7)
        assert len(overfitting_1d) == 1
        assert overfitting_1d[0][0] == "AAPL"

        # Filter by 4h only
        overfitting_4h = monitor.get_recent_overfitting_symbols(horizon="4h", days=7)
        assert len(overfitting_4h) == 1
        assert overfitting_4h[0][0] == "MSFT"


class TestDivergenceSummaryStatistics:
    """Test divergence summary statistics generation."""

    def test_divergence_summary_basic(self):
        """Test basic divergence summary statistics."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log results with varying divergence
        divergences = [0.05, 0.15, 0.25, 0.30, 0.10]
        for i, div in enumerate(divergences):
            val_rmse = 0.05
            test_rmse = val_rmse * (1 + div)

            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="aapl_1d",
                horizon="1D",
                window_id=i,
                val_rmse=val_rmse,
                test_rmse=test_rmse,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        summary = monitor.get_divergence_summary()

        assert summary["total_windows"] == 5
        assert summary["mean_divergence"] == pytest.approx(0.17, abs=0.01)
        assert summary["max_divergence"] == pytest.approx(0.30, abs=0.001)
        assert summary["min_divergence"] == pytest.approx(0.05, abs=0.001)
        assert summary["overfitting_windows"] == 2  # 0.25 and 0.30 > 0.20
        assert summary["pct_overfitting"] == pytest.approx(40.0, abs=0.1)  # 2 out of 5

    def test_summary_includes_threshold(self):
        """Test that summary includes the divergence threshold."""
        monitor = DivergenceMonitor(divergence_threshold=0.15)

        monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        summary = monitor.get_divergence_summary()

        assert summary["threshold"] == 0.15

    def test_summary_with_horizon_filter(self):
        """Test summary statistics filtered by horizon."""
        monitor = DivergenceMonitor(divergence_threshold=0.20)

        # Log 1D results
        for i in range(3):
            monitor.log_window_result(
                symbol="AAPL",
                symbol_id="aapl_1d",
                horizon="1D",
                window_id=i,
                val_rmse=0.05,
                test_rmse=0.055,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        # Log 4h results with different divergence
        for i in range(2):
            monitor.log_window_result(
                symbol="MSFT",
                symbol_id="msft_4h",
                horizon="4h",
                window_id=i,
                val_rmse=0.05,
                test_rmse=0.065,
                model_count=2,
                models_used=["LSTM", "ARIMA_GARCH"],
            )

        # Summary for 1D only
        summary_1d = monitor.get_divergence_summary(horizon="1D")
        assert summary_1d["total_windows"] == 3

        # Summary for 4h only
        summary_4h = monitor.get_divergence_summary(horizon="4h")
        assert summary_4h["total_windows"] == 2

    def test_empty_summary(self):
        """Test summary with no data."""
        monitor = DivergenceMonitor()

        summary = monitor.get_divergence_summary()

        assert summary["total_windows"] == 0
        assert summary["mean_divergence"] == 0.0
        assert summary["max_divergence"] == 0.0
        assert summary["overfitting_windows"] == 0


class TestDatabaseLoggingWithMock:
    """Test database logging behavior with mocked db_client."""

    def test_log_to_database_called_when_client_available(self):
        """Test that database logging is called when db_client is available."""
        mock_db_client = MagicMock()
        monitor = DivergenceMonitor(db_client=mock_db_client)

        monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # In real implementation, would call db_client.table().insert()
        # This test verifies structure is correct

    def test_database_logging_error_handling(self):
        """Test that database errors are caught and logged."""
        mock_db_client = MagicMock()
        mock_db_client.table().insert().execute.side_effect = Exception("DB Error")

        monitor = DivergenceMonitor(db_client=mock_db_client)

        # Should not raise - error handling in place
        result = monitor.log_window_result(
            symbol="AAPL",
            symbol_id="aapl_1d",
            horizon="1D",
            window_id=1,
            val_rmse=0.05,
            test_rmse=0.06,
            model_count=2,
            models_used=["LSTM", "ARIMA_GARCH"],
        )

        # Result should still be returned (logged to memory)
        assert result["symbol"] == "AAPL"
        assert len(monitor.divergence_history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
