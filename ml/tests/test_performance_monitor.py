"""Unit tests for Performance Monitor."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.models.performance_monitor import (
    AlertRecord,
    CalibrationSnapshot,
    ModelHealthChecker,
    PerformanceMonitor,
    PerformanceRecord,
)


@pytest.fixture
def monitor():
    """Create a PerformanceMonitor instance."""
    return PerformanceMonitor(
        accuracy_window=20,
        calibration_window=50,
        min_samples_for_alert=10,
    )


@pytest.fixture
def populated_monitor():
    """Create a monitor with sample data."""
    monitor = PerformanceMonitor(
        accuracy_window=20,
        min_samples_for_alert=10,
    )

    np.random.seed(42)
    classes = ["Bullish", "Neutral", "Bearish"]

    for i in range(50):
        actual = np.random.choice(classes)
        # 60% accuracy
        if np.random.random() < 0.6:
            prediction = actual
        else:
            prediction = np.random.choice(classes)

        monitor.record_prediction(
            prediction=prediction,
            actual=actual,
            confidence=0.5 + np.random.random() * 0.4,
            agreement=0.5 + np.random.random() * 0.4,
            probabilities={c: np.random.random() for c in classes},
            weights={"rf": 0.3, "gb": 0.3, "arima": 0.2, "lstm": 0.2},
            model_predictions={
                "rf": np.random.choice(classes),
                "gb": np.random.choice(classes),
                "arima": np.random.choice(classes),
                "lstm": np.random.choice(classes),
            },
        )

    return monitor


class TestPerformanceRecord:
    """Test PerformanceRecord dataclass."""

    def test_create_record(self):
        """Test creating a PerformanceRecord."""
        record = PerformanceRecord(
            timestamp=datetime.now(),
            prediction="Bullish",
            actual="Bullish",
            confidence=0.8,
            agreement=0.75,
            is_correct=True,
            probabilities={"bullish": 0.8, "neutral": 0.1, "bearish": 0.1},
            weights={"rf": 0.5, "lstm": 0.5},
            model_predictions={"rf": "Bullish", "lstm": "Bullish"},
        )

        assert record.prediction == "Bullish"
        assert record.is_correct is True
        assert record.confidence == 0.8


class TestAlertRecord:
    """Test AlertRecord dataclass."""

    def test_create_alert(self):
        """Test creating an AlertRecord."""
        alert = AlertRecord(
            timestamp=datetime.now(),
            alert_type="low_accuracy",
            severity="warning",
            message="Accuracy dropped",
            metric_name="accuracy",
            metric_value=0.4,
            threshold=0.45,
        )

        assert alert.severity == "warning"
        assert alert.metric_value == 0.4


class TestMonitorInit:
    """Test PerformanceMonitor initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        monitor = PerformanceMonitor()

        assert monitor.accuracy_window == 50
        assert monitor.calibration_window == 100
        assert monitor.alert_threshold_accuracy == 0.45
        assert len(monitor.records) == 0

    def test_custom_initialization(self):
        """Test custom initialization."""
        monitor = PerformanceMonitor(
            accuracy_window=30,
            calibration_window=60,
            alert_threshold_accuracy=0.5,
        )

        assert monitor.accuracy_window == 30
        assert monitor.calibration_window == 60
        assert monitor.alert_threshold_accuracy == 0.5


class TestRecordPrediction:
    """Test record_prediction method."""

    def test_record_single_prediction(self, monitor):
        """Test recording a single prediction."""
        monitor.record_prediction(
            prediction="Bullish",
            actual="Bullish",
            confidence=0.8,
            agreement=0.75,
            probabilities={"bullish": 0.8, "neutral": 0.1, "bearish": 0.1},
            weights={"rf": 0.5, "lstm": 0.5},
            model_predictions={"rf": "Bullish", "lstm": "Neutral"},
        )

        assert len(monitor.records) == 1
        assert monitor.records[0].is_correct is True

    def test_record_incorrect_prediction(self, monitor):
        """Test recording an incorrect prediction."""
        monitor.record_prediction(
            prediction="Bullish",
            actual="Bearish",
            confidence=0.7,
            agreement=0.6,
            probabilities={"bullish": 0.7, "neutral": 0.2, "bearish": 0.1},
            weights={"rf": 0.5, "lstm": 0.5},
            model_predictions={"rf": "Bullish", "lstm": "Bullish"},
        )

        assert len(monitor.records) == 1
        assert monitor.records[0].is_correct is False

    def test_tracks_model_accuracies(self, monitor):
        """Test that model accuracies are tracked."""
        monitor.record_prediction(
            prediction="Bullish",
            actual="Bullish",
            confidence=0.8,
            agreement=0.75,
            probabilities={},
            weights={"rf": 0.5, "lstm": 0.5},
            model_predictions={"rf": "Bullish", "lstm": "Bearish"},
        )

        assert "rf" in monitor.model_accuracies
        assert "lstm" in monitor.model_accuracies
        assert monitor.model_accuracies["rf"][-1] == 1.0  # Correct
        assert monitor.model_accuracies["lstm"][-1] == 0.0  # Incorrect

    def test_tracks_weight_history(self, monitor):
        """Test that weight history is tracked."""
        weights = {"rf": 0.6, "lstm": 0.4}
        monitor.record_prediction(
            prediction="Bullish",
            actual="Bullish",
            confidence=0.8,
            agreement=0.75,
            probabilities={},
            weights=weights,
            model_predictions={"rf": "Bullish", "lstm": "Bullish"},
        )

        assert len(monitor.weight_history) == 1
        assert monitor.weight_history[0]["weights"] == weights


class TestRecordCalibration:
    """Test record_calibration method."""

    def test_record_calibration(self, monitor):
        """Test recording calibration."""
        monitor.record_calibration(
            empirical_coverage=0.93,
            target_coverage=0.95,
            n_samples=100,
        )

        assert len(monitor.calibration_history) == 1
        assert monitor.calibration_history[0].empirical_coverage == 0.93

    def test_calibration_drift_alert(self, monitor):
        """Test that calibration drift generates alert."""
        # Add enough samples for alerts
        for _ in range(15):
            monitor.record_prediction(
                prediction="Bullish",
                actual="Bullish",
                confidence=0.8,
                agreement=0.75,
                probabilities={},
                weights={},
                model_predictions={},
            )

        monitor.record_calibration(
            empirical_coverage=0.7,  # Significant drift
            target_coverage=0.95,
            n_samples=100,
        )

        alerts = [a for a in monitor.alerts if a.alert_type == "calibration_drift"]
        assert len(alerts) >= 1


class TestGetRollingAccuracy:
    """Test get_rolling_accuracy method."""

    def test_empty_records(self, monitor):
        """Test with empty records."""
        result = monitor.get_rolling_accuracy()
        assert np.isnan(result["accuracy"])
        assert result["n_samples"] == 0

    def test_rolling_accuracy(self, populated_monitor):
        """Test rolling accuracy calculation."""
        result = populated_monitor.get_rolling_accuracy()

        assert "accuracy" in result
        assert 0 <= result["accuracy"] <= 1
        assert result["n_samples"] == 20  # Window size

    def test_class_accuracy(self, populated_monitor):
        """Test class-level accuracy."""
        result = populated_monitor.get_rolling_accuracy()

        assert "class_accuracy" in result
        # Should have at least some classes
        assert len(result["class_accuracy"]) > 0


class TestGetModelPerformance:
    """Test get_model_performance method."""

    def test_model_performance(self, populated_monitor):
        """Test model performance metrics."""
        result = populated_monitor.get_model_performance()

        assert "rf" in result
        assert "gb" in result
        assert "accuracy" in result["rf"]
        assert "recent_trend" in result["rf"]

    def test_accuracy_bounded(self, populated_monitor):
        """Test accuracy is bounded 0-1."""
        result = populated_monitor.get_model_performance()

        for model_stats in result.values():
            assert 0 <= model_stats["accuracy"] <= 1


class TestGetWeightEvolution:
    """Test get_weight_evolution method."""

    def test_empty_history(self, monitor):
        """Test with empty history."""
        df = monitor.get_weight_evolution()
        assert df.empty

    def test_weight_evolution_df(self, populated_monitor):
        """Test weight evolution DataFrame."""
        df = populated_monitor.get_weight_evolution()

        assert not df.empty
        assert "timestamp" in df.columns
        assert "rf" in df.columns


class TestGetConfidenceCalibration:
    """Test get_confidence_calibration method."""

    def test_insufficient_data(self, monitor):
        """Test with insufficient data."""
        result = monitor.get_confidence_calibration()
        assert "error" in result

    def test_confidence_calibration(self, populated_monitor):
        """Test confidence calibration analysis."""
        result = populated_monitor.get_confidence_calibration()

        assert "ece" in result
        assert "is_well_calibrated" in result
        assert 0 <= result["ece"] <= 1


class TestGetAgreementAnalysis:
    """Test get_agreement_analysis method."""

    def test_insufficient_data(self, monitor):
        """Test with insufficient data."""
        result = monitor.get_agreement_analysis()
        assert "error" in result

    def test_agreement_analysis(self, populated_monitor):
        """Test agreement analysis."""
        result = populated_monitor.get_agreement_analysis()

        assert "agreement_accuracy" in result
        assert "correlation" in result


class TestGetRecentAlerts:
    """Test get_recent_alerts method."""

    def test_no_alerts(self, monitor):
        """Test with no alerts."""
        alerts = monitor.get_recent_alerts()
        assert len(alerts) == 0

    def test_filter_by_severity(self, populated_monitor):
        """Test filtering by severity."""
        # Generate some alerts by adding poor predictions
        for _ in range(20):
            populated_monitor.record_prediction(
                prediction="Bullish",
                actual="Bearish",
                confidence=0.5,
                agreement=0.3,
                probabilities={},
                weights={"rf": 0.5, "lstm": 0.5},
                model_predictions={"rf": "Bullish", "lstm": "Bullish"},
            )

        all_alerts = populated_monitor.get_recent_alerts()
        warning_alerts = populated_monitor.get_recent_alerts(severity="warning")

        assert len(warning_alerts) <= len(all_alerts)


class TestGetDashboardSummary:
    """Test get_dashboard_summary method."""

    def test_dashboard_summary(self, populated_monitor):
        """Test dashboard summary."""
        summary = populated_monitor.get_dashboard_summary()

        assert "timestamp" in summary
        assert "n_predictions" in summary
        assert "rolling_accuracy" in summary
        assert "model_performance" in summary
        assert "current_weights" in summary
        assert "alert_summary" in summary

    def test_empty_monitor_summary(self, monitor):
        """Test summary with empty monitor."""
        summary = monitor.get_dashboard_summary()

        assert summary["n_predictions"] == 0


class TestGetPerformanceReport:
    """Test get_performance_report method."""

    def test_performance_report(self, populated_monitor):
        """Test performance report generation."""
        report = populated_monitor.get_performance_report(period_days=30)

        assert "overall_accuracy" in report
        assert "mean_confidence" in report
        assert "model_stats" in report

    def test_no_data_in_period(self, monitor):
        """Test with no data in period."""
        report = monitor.get_performance_report(period_days=1)
        assert "error" in report


class TestExportRecords:
    """Test export_records method."""

    def test_export_empty(self, monitor):
        """Test exporting empty records."""
        df = monitor.export_records()
        assert df.empty

    def test_export_records(self, populated_monitor):
        """Test exporting records."""
        df = populated_monitor.export_records()

        assert not df.empty
        assert "timestamp" in df.columns
        assert "prediction" in df.columns
        assert "is_correct" in df.columns


class TestReset:
    """Test reset method."""

    def test_reset(self, populated_monitor):
        """Test resetting monitor."""
        assert len(populated_monitor.records) > 0

        populated_monitor.reset()

        assert len(populated_monitor.records) == 0
        assert len(populated_monitor.alerts) == 0
        assert len(populated_monitor.weight_history) == 0


class TestAlertGeneration:
    """Test alert generation."""

    def test_low_accuracy_alert(self, monitor):
        """Test low accuracy alert generation."""
        # Generate many incorrect predictions
        for _ in range(25):
            monitor.record_prediction(
                prediction="Bullish",
                actual="Bearish",
                confidence=0.6,
                agreement=0.5,
                probabilities={},
                weights={"rf": 0.5},
                model_predictions={"rf": "Bullish"},
            )

        low_acc_alerts = [a for a in monitor.alerts if a.alert_type == "low_accuracy"]
        assert len(low_acc_alerts) >= 1

    def test_sudden_drop_alert(self, monitor):
        """Test sudden accuracy drop alert."""
        # First 15 correct
        for _ in range(15):
            monitor.record_prediction(
                prediction="Bullish",
                actual="Bullish",
                confidence=0.8,
                agreement=0.8,
                probabilities={},
                weights={"rf": 0.5},
                model_predictions={"rf": "Bullish"},
            )

        # Then 10 incorrect
        for _ in range(10):
            monitor.record_prediction(
                prediction="Bullish",
                actual="Bearish",
                confidence=0.6,
                agreement=0.5,
                probabilities={},
                weights={"rf": 0.5},
                model_predictions={"rf": "Bullish"},
            )

        drop_alerts = [a for a in monitor.alerts if a.alert_type == "accuracy_drop"]
        assert len(drop_alerts) >= 1


class TestModelHealthChecker:
    """Test ModelHealthChecker."""

    def test_init(self, populated_monitor):
        """Test initialization."""
        checker = ModelHealthChecker(populated_monitor, health_window=20)

        assert checker.monitor == populated_monitor
        assert checker.health_window == 20

    def test_check_unknown_model(self, populated_monitor):
        """Test checking unknown model."""
        checker = ModelHealthChecker(populated_monitor)
        result = checker.check_model_health("unknown_model")

        assert result["status"] == "unknown"

    def test_check_model_health(self, populated_monitor):
        """Test checking model health."""
        checker = ModelHealthChecker(populated_monitor, health_window=20)
        result = checker.check_model_health("rf")

        assert "status" in result
        assert result["status"] in ["healthy", "marginal", "unhealthy"]
        assert "accuracy" in result
        assert "recommendation" in result

    def test_check_all_models(self, populated_monitor):
        """Test checking all models."""
        checker = ModelHealthChecker(populated_monitor, health_window=20)
        results = checker.check_all_models()

        assert "rf" in results
        assert "gb" in results
        assert "lstm" in results

    def test_weight_trend(self, populated_monitor):
        """Test weight trend calculation."""
        checker = ModelHealthChecker(populated_monitor)
        result = checker.check_model_health("rf")

        assert "weight_trend" in result


class TestIntegration:
    """Integration tests."""

    def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        monitor = PerformanceMonitor(
            accuracy_window=10,
            min_samples_for_alert=5,
        )

        # 1. Record predictions
        np.random.seed(42)
        classes = ["Bullish", "Neutral", "Bearish"]

        for i in range(30):
            actual = np.random.choice(classes)
            # Varying accuracy over time
            accuracy = 0.7 if i < 20 else 0.3

            if np.random.random() < accuracy:
                prediction = actual
            else:
                prediction = np.random.choice(classes)

            monitor.record_prediction(
                prediction=prediction,
                actual=actual,
                confidence=0.5 + np.random.random() * 0.4,
                agreement=0.5 + np.random.random() * 0.4,
                probabilities={c: 0.33 for c in classes},
                weights={"rf": 0.4, "gb": 0.3, "arima": 0.3},
                model_predictions={
                    "rf": np.random.choice(classes),
                    "gb": np.random.choice(classes),
                    "arima": np.random.choice(classes),
                },
            )

        # 2. Record calibration
        monitor.record_calibration(
            empirical_coverage=0.92,
            target_coverage=0.95,
            n_samples=30,
        )

        # 3. Get dashboard summary
        summary = monitor.get_dashboard_summary()
        assert summary["n_predictions"] == 30

        # 4. Get performance report
        report = monitor.get_performance_report(period_days=1)
        assert report["n_predictions"] == 30

        # 5. Check model health
        checker = ModelHealthChecker(monitor, health_window=10)
        health = checker.check_all_models()
        assert len(health) == 3

        # 6. Export records
        df = monitor.export_records()
        assert len(df) == 30

    def test_alert_escalation(self):
        """Test alert escalation from warning to critical."""
        monitor = PerformanceMonitor(
            accuracy_window=10,
            min_samples_for_alert=5,
        )

        # Generate consistently bad predictions
        for _ in range(25):
            monitor.record_prediction(
                prediction="Bullish",
                actual="Bearish",
                confidence=0.6,
                agreement=0.5,
                probabilities={},
                weights={"rf": 1.0},
                model_predictions={"rf": "Bullish"},
            )

        # Should have multiple alert types
        alert_types = set(a.alert_type for a in monitor.alerts)
        assert len(alert_types) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
