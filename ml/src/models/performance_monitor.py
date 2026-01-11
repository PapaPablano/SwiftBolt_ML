"""
Ensemble Performance Monitor
============================

Tracks and monitors ensemble model performance over time with:
- Rolling accuracy metrics
- Weight evolution tracking
- Calibration drift detection
- Alert generation for performance degradation
- Dashboard-ready data structures

Key Features:
- Real-time performance tracking
- Historical analysis and trending
- Anomaly detection for model failures
- Export capabilities for visualization
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PerformanceRecord:
    """Single performance record for tracking."""

    timestamp: datetime
    prediction: str
    actual: str
    confidence: float
    agreement: float
    is_correct: bool
    probabilities: Dict[str, float]
    weights: Dict[str, float]
    model_predictions: Dict[str, str]
    forecast_return: Optional[float] = None
    actual_return: Optional[float] = None


@dataclass
class AlertRecord:
    """Alert for performance issues."""

    timestamp: datetime
    alert_type: str
    severity: str  # 'info', 'warning', 'critical'
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationSnapshot:
    """Calibration status at a point in time."""

    timestamp: datetime
    empirical_coverage: float
    target_coverage: float
    calibration_ratio: float
    n_samples: int
    needs_recalibration: bool


class PerformanceMonitor:
    """
    Monitor ensemble performance over time.

    Tracks accuracy, calibration, weight evolution,
    and generates alerts for performance degradation.
    """

    def __init__(
        self,
        accuracy_window: int = 50,
        calibration_window: int = 100,
        alert_threshold_accuracy: float = 0.45,
        alert_threshold_calibration: float = 0.15,
        min_samples_for_alert: int = 20,
    ) -> None:
        """
        Initialize Performance Monitor.

        Args:
            accuracy_window: Rolling window for accuracy calculation
            calibration_window: Window for calibration checks
            alert_threshold_accuracy: Min accuracy before alert
            alert_threshold_calibration: Max calibration drift before alert
            min_samples_for_alert: Min samples before generating alerts
        """
        self.accuracy_window = accuracy_window
        self.calibration_window = calibration_window
        self.alert_threshold_accuracy = alert_threshold_accuracy
        self.alert_threshold_calibration = alert_threshold_calibration
        self.min_samples_for_alert = min_samples_for_alert

        # Storage
        self.records: List[PerformanceRecord] = []
        self.alerts: List[AlertRecord] = []
        self.calibration_history: List[CalibrationSnapshot] = []
        self.weight_history: List[Dict] = []

        # Model-specific tracking
        self.model_accuracies: Dict[str, List[float]] = {}
        self.model_contributions: Dict[str, List[float]] = {}

        logger.info(
            "PerformanceMonitor initialized: " "accuracy_window=%d, calibration_window=%d",
            accuracy_window,
            calibration_window,
        )

    def record_prediction(
        self,
        prediction: str,
        actual: str,
        confidence: float,
        agreement: float,
        probabilities: Dict[str, float],
        weights: Dict[str, float],
        model_predictions: Dict[str, str],
        forecast_return: Optional[float] = None,
        actual_return: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record a prediction and actual outcome.

        Args:
            prediction: Ensemble prediction label
            actual: Actual outcome label
            confidence: Prediction confidence
            agreement: Model agreement score
            probabilities: Class probabilities
            weights: Model weights used
            model_predictions: Individual model predictions
            forecast_return: Predicted return (optional)
            actual_return: Actual return (optional)
            timestamp: Timestamp (defaults to now)
        """
        ts = timestamp or datetime.now()

        record = PerformanceRecord(
            timestamp=ts,
            prediction=prediction,
            actual=actual,
            confidence=confidence,
            agreement=agreement,
            is_correct=prediction.lower() == actual.lower(),
            probabilities=probabilities,
            weights=weights.copy(),
            model_predictions=model_predictions.copy(),
            forecast_return=forecast_return,
            actual_return=actual_return,
        )

        self.records.append(record)

        # Track model-level accuracy
        for model, pred in model_predictions.items():
            if model not in self.model_accuracies:
                self.model_accuracies[model] = []
            self.model_accuracies[model].append(1.0 if pred.lower() == actual.lower() else 0.0)

        # Track weight history
        self.weight_history.append(
            {
                "timestamp": ts,
                "weights": weights.copy(),
            }
        )

        # Check for alerts
        self._check_alerts()

    def record_calibration(
        self,
        empirical_coverage: float,
        target_coverage: float,
        n_samples: int,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record calibration status."""
        ts = timestamp or datetime.now()

        calibration_ratio = empirical_coverage / target_coverage if target_coverage > 0 else 1.0
        needs_recalibration = abs(calibration_ratio - 1.0) > 0.1

        snapshot = CalibrationSnapshot(
            timestamp=ts,
            empirical_coverage=empirical_coverage,
            target_coverage=target_coverage,
            calibration_ratio=calibration_ratio,
            n_samples=n_samples,
            needs_recalibration=needs_recalibration,
        )

        self.calibration_history.append(snapshot)

        # Check calibration drift
        if needs_recalibration and n_samples >= self.min_samples_for_alert:
            self._add_alert(
                alert_type="calibration_drift",
                severity="warning",
                message=(
                    f"Calibration drift detected: "
                    f"coverage={empirical_coverage:.1%} vs "
                    f"target={target_coverage:.1%}"
                ),
                metric_name="calibration_ratio",
                metric_value=calibration_ratio,
                threshold=1.0,
            )

    def get_rolling_accuracy(
        self,
        window: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Get rolling accuracy metrics.

        Args:
            window: Rolling window size (default: accuracy_window)

        Returns:
            Dict with accuracy metrics
        """
        window = window or self.accuracy_window

        if len(self.records) < 2:
            return {"accuracy": np.nan, "n_samples": len(self.records)}

        recent = self.records[-window:]
        correct = sum(1 for r in recent if r.is_correct)
        total = len(recent)

        # Class-level accuracy
        class_correct = {}
        class_total = {}
        for r in recent:
            cls = r.actual.lower()
            if cls not in class_total:
                class_total[cls] = 0
                class_correct[cls] = 0
            class_total[cls] += 1
            if r.is_correct:
                class_correct[cls] += 1

        class_accuracy = {
            cls: class_correct[cls] / class_total[cls]
            for cls in class_total
            if class_total[cls] > 0
        }

        return {
            "accuracy": correct / total if total > 0 else np.nan,
            "n_samples": total,
            "class_accuracy": class_accuracy,
            "window": window,
        }

    def get_model_performance(self) -> Dict[str, Dict]:
        """Get individual model performance metrics."""
        performance = {}

        for model, accuracies in self.model_accuracies.items():
            if not accuracies:
                continue

            recent = accuracies[-self.accuracy_window :]

            performance[model] = {
                "accuracy": np.mean(recent),
                "accuracy_std": np.std(recent),
                "n_predictions": len(accuracies),
                "recent_trend": self._calculate_trend(recent),
            }

        return performance

    def get_weight_evolution(self) -> pd.DataFrame:
        """Get weight evolution as DataFrame."""
        if not self.weight_history:
            return pd.DataFrame()

        records = []
        for entry in self.weight_history:
            row = {"timestamp": entry["timestamp"]}
            row.update(entry["weights"])
            records.append(row)

        return pd.DataFrame(records)

    def get_confidence_calibration(self) -> Dict[str, Any]:
        """
        Analyze confidence vs accuracy calibration.

        Returns reliability diagram data.
        """
        if len(self.records) < 10:
            return {"error": "Insufficient data"}

        # Bin predictions by confidence
        bins = np.linspace(0, 1, 6)
        bin_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(5)]

        confidences = [r.confidence for r in self.records]
        correct = [r.is_correct for r in self.records]

        df = pd.DataFrame(
            {
                "confidence": confidences,
                "correct": correct,
            }
        )
        df["bin"] = pd.cut(
            df["confidence"],
            bins=bins,
            labels=bin_labels,
            include_lowest=True,
        )

        calibration = df.groupby("bin", observed=True).agg(
            {
                "correct": ["mean", "count"],
                "confidence": "mean",
            }
        )
        calibration.columns = ["accuracy", "count", "mean_confidence"]

        # Expected Calibration Error (ECE)
        ece = 0.0
        total = len(df)
        for _, row in calibration.iterrows():
            if row["count"] > 0:
                ece += (row["count"] / total) * abs(row["accuracy"] - row["mean_confidence"])

        return {
            "calibration_table": calibration.to_dict(),
            "ece": float(ece),
            "is_well_calibrated": ece < 0.1,
        }

    def get_agreement_analysis(self) -> Dict[str, Any]:
        """Analyze model agreement vs accuracy."""
        if len(self.records) < 10:
            return {"error": "Insufficient data"}

        agreements = [r.agreement for r in self.records]
        correct = [r.is_correct for r in self.records]

        # Bin by agreement
        bins = [0, 0.5, 0.7, 0.85, 1.0]
        bin_labels = ["low", "medium", "high", "very_high"]

        df = pd.DataFrame(
            {
                "agreement": agreements,
                "correct": correct,
            }
        )
        df["bin"] = pd.cut(
            df["agreement"],
            bins=bins,
            labels=bin_labels,
            include_lowest=True,
        )

        analysis = df.groupby("bin", observed=True).agg(
            {
                "correct": ["mean", "count"],
            }
        )
        analysis.columns = ["accuracy", "count"]

        return {
            "agreement_accuracy": analysis.to_dict(),
            "correlation": (
                float(np.corrcoef(agreements, correct)[0, 1]) if len(set(correct)) > 1 else 0.0
            ),
        }

    def get_recent_alerts(
        self,
        n: int = 10,
        severity: Optional[str] = None,
    ) -> List[Dict]:
        """Get recent alerts."""
        alerts = self.alerts

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        recent = alerts[-n:]

        return [
            {
                "timestamp": a.timestamp.isoformat(),
                "type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "metric": a.metric_name,
                "value": a.metric_value,
                "threshold": a.threshold,
            }
            for a in recent
        ]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary.

        Returns all key metrics for dashboard display.
        """
        rolling_accuracy = self.get_rolling_accuracy()
        model_performance = self.get_model_performance()
        confidence_cal = self.get_confidence_calibration()

        # Recent trend
        if len(self.records) >= 20:
            recent_10 = [r.is_correct for r in self.records[-10:]]
            prev_10 = [r.is_correct for r in self.records[-20:-10]]
            trend = np.mean(recent_10) - np.mean(prev_10)
        else:
            trend = 0.0

        # Current weights
        current_weights = self.weight_history[-1]["weights"] if self.weight_history else {}

        # Active alerts count
        recent_alerts = [
            a for a in self.alerts if a.timestamp > datetime.now() - timedelta(hours=24)
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "n_predictions": len(self.records),
            "rolling_accuracy": rolling_accuracy.get("accuracy", np.nan),
            "accuracy_trend": float(trend),
            "class_accuracy": rolling_accuracy.get("class_accuracy", {}),
            "model_performance": model_performance,
            "current_weights": current_weights,
            "confidence_ece": confidence_cal.get("ece", np.nan),
            "is_well_calibrated": confidence_cal.get("is_well_calibrated", False),
            "n_active_alerts": len(recent_alerts),
            "alert_summary": {
                "critical": len([a for a in recent_alerts if a.severity == "critical"]),
                "warning": len([a for a in recent_alerts if a.severity == "warning"]),
                "info": len([a for a in recent_alerts if a.severity == "info"]),
            },
            "calibration_status": (
                self.calibration_history[-1].__dict__ if self.calibration_history else None
            ),
        }

    def get_performance_report(
        self,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Generate detailed performance report.

        Args:
            period_days: Number of days to analyze

        Returns:
            Comprehensive performance report
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        recent_records = [r for r in self.records if r.timestamp > cutoff]

        if not recent_records:
            return {"error": "No records in specified period"}

        # Overall metrics
        correct = sum(1 for r in recent_records if r.is_correct)
        total = len(recent_records)
        accuracy = correct / total

        # Confidence analysis
        confidences = [r.confidence for r in recent_records]
        high_conf = [r for r in recent_records if r.confidence > 0.7]
        high_conf_accuracy = (
            sum(1 for r in high_conf if r.is_correct) / len(high_conf) if high_conf else np.nan
        )

        # Agreement analysis
        agreements = [r.agreement for r in recent_records]
        high_agree = [r for r in recent_records if r.agreement > 0.7]
        high_agree_accuracy = (
            sum(1 for r in high_agree if r.is_correct) / len(high_agree) if high_agree else np.nan
        )

        # Model contributions
        model_stats = {}
        for model in self.model_accuracies.keys():
            model_records = [r for r in recent_records if model in r.model_predictions]
            if model_records:
                model_correct = sum(
                    1
                    for r in model_records
                    if r.model_predictions[model].lower() == r.actual.lower()
                )
                model_stats[model] = {
                    "accuracy": model_correct / len(model_records),
                    "n_predictions": len(model_records),
                }

        return {
            "period_days": period_days,
            "n_predictions": total,
            "overall_accuracy": float(accuracy),
            "mean_confidence": float(np.mean(confidences)),
            "mean_agreement": float(np.mean(agreements)),
            "high_confidence_accuracy": float(high_conf_accuracy),
            "high_agreement_accuracy": float(high_agree_accuracy),
            "model_stats": model_stats,
            "n_alerts_generated": len([a for a in self.alerts if a.timestamp > cutoff]),
        }

    def export_records(self) -> pd.DataFrame:
        """Export all records as DataFrame."""
        if not self.records:
            return pd.DataFrame()

        data = []
        for r in self.records:
            row = {
                "timestamp": r.timestamp,
                "prediction": r.prediction,
                "actual": r.actual,
                "confidence": r.confidence,
                "agreement": r.agreement,
                "is_correct": r.is_correct,
            }
            # Add probabilities
            for cls, prob in r.probabilities.items():
                row[f"prob_{cls}"] = prob
            # Add weights
            for model, weight in r.weights.items():
                row[f"weight_{model}"] = weight
            data.append(row)

        return pd.DataFrame(data)

    def reset(self) -> None:
        """Reset all tracking data."""
        self.records = []
        self.alerts = []
        self.calibration_history = []
        self.weight_history = []
        self.model_accuracies = {}
        self.model_contributions = {}
        logger.info("PerformanceMonitor reset")

    def _check_alerts(self) -> None:
        """Check for alert conditions."""
        if len(self.records) < self.min_samples_for_alert:
            return

        # Check rolling accuracy
        accuracy = self.get_rolling_accuracy()
        if accuracy["accuracy"] < self.alert_threshold_accuracy:
            self._add_alert(
                alert_type="low_accuracy",
                severity="warning",
                message=(f"Rolling accuracy dropped to " f"{accuracy['accuracy']:.1%}"),
                metric_name="rolling_accuracy",
                metric_value=accuracy["accuracy"],
                threshold=self.alert_threshold_accuracy,
            )

        # Check individual model degradation
        for model, accs in self.model_accuracies.items():
            if len(accs) >= self.accuracy_window:
                recent = np.mean(accs[-self.accuracy_window :])
                if recent < 0.40:  # Model performing worse than random
                    self._add_alert(
                        alert_type="model_degradation",
                        severity="warning",
                        message=f"Model {model} accuracy dropped to {recent:.1%}",
                        metric_name=f"{model}_accuracy",
                        metric_value=recent,
                        threshold=0.40,
                        details={"model": model},
                    )

        # Check for sudden accuracy drop
        if len(self.records) >= 20:
            recent_10 = np.mean([r.is_correct for r in self.records[-10:]])
            prev_10 = np.mean([r.is_correct for r in self.records[-20:-10]])
            if prev_10 - recent_10 > 0.15:  # 15% drop
                self._add_alert(
                    alert_type="accuracy_drop",
                    severity="critical",
                    message=(f"Sudden accuracy drop: " f"{prev_10:.1%} -> {recent_10:.1%}"),
                    metric_name="accuracy_change",
                    metric_value=recent_10 - prev_10,
                    threshold=-0.15,
                )

    def _add_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        details: Optional[Dict] = None,
    ) -> None:
        """Add an alert if not duplicate."""
        # Check for recent duplicate
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_same = [
            a for a in self.alerts if (a.alert_type == alert_type and a.timestamp > recent_cutoff)
        ]

        if recent_same:
            return  # Don't duplicate alerts

        alert = AlertRecord(
            timestamp=datetime.now(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            details=details or {},
        )

        self.alerts.append(alert)
        logger.warning("Alert: [%s] %s", severity.upper(), message)

    def _calculate_trend(
        self,
        values: List[float],
        window: int = 10,
    ) -> str:
        """Calculate trend direction."""
        if len(values) < window * 2:
            return "insufficient_data"

        recent = np.mean(values[-window:])
        previous = np.mean(values[-window * 2 : -window])

        diff = recent - previous

        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"


class ModelHealthChecker:
    """Check health of individual models in ensemble."""

    def __init__(
        self,
        monitor: PerformanceMonitor,
        health_window: int = 30,
    ) -> None:
        """
        Initialize health checker.

        Args:
            monitor: PerformanceMonitor instance
            health_window: Window for health assessment
        """
        self.monitor = monitor
        self.health_window = health_window

    def check_model_health(self, model_name: str) -> Dict[str, Any]:
        """
        Check health status of a specific model.

        Returns health report with recommendations.
        """
        if model_name not in self.monitor.model_accuracies:
            return {"status": "unknown", "reason": "No data for model"}

        accuracies = self.monitor.model_accuracies[model_name]

        if len(accuracies) < self.health_window:
            return {
                "status": "warming_up",
                "n_predictions": len(accuracies),
                "required": self.health_window,
            }

        recent = accuracies[-self.health_window :]
        accuracy = np.mean(recent)
        std = np.std(recent)

        # Determine health status
        if accuracy >= 0.55:
            status = "healthy"
        elif accuracy >= 0.45:
            status = "marginal"
        else:
            status = "unhealthy"

        # Check for instability
        is_unstable = std > 0.3

        # Get weight trend
        weight_trend = self._get_weight_trend(model_name)

        return {
            "status": status,
            "accuracy": float(accuracy),
            "accuracy_std": float(std),
            "is_unstable": is_unstable,
            "weight_trend": weight_trend,
            "recommendation": self._get_recommendation(status, accuracy, is_unstable),
        }

    def check_all_models(self) -> Dict[str, Dict]:
        """Check health of all models."""
        return {
            model: self.check_model_health(model) for model in self.monitor.model_accuracies.keys()
        }

    def _get_weight_trend(self, model_name: str) -> str:
        """Get weight trend for model."""
        if len(self.monitor.weight_history) < 10:
            return "insufficient_data"

        weights = [
            entry["weights"].get(model_name, 0) for entry in self.monitor.weight_history[-20:]
        ]

        if len(weights) < 10:
            return "insufficient_data"

        recent = np.mean(weights[-5:])
        previous = np.mean(weights[-10:-5])

        if recent > previous * 1.1:
            return "increasing"
        elif recent < previous * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _get_recommendation(
        self,
        status: str,
        accuracy: float,
        is_unstable: bool,
    ) -> str:
        """Get recommendation based on health status."""
        if status == "healthy" and not is_unstable:
            return "No action needed"
        elif status == "healthy" and is_unstable:
            return "Consider reducing weight to stabilize ensemble"
        elif status == "marginal":
            return "Monitor closely, may need retraining"
        else:
            return "Consider disabling or retraining model"


if __name__ == "__main__":
    # Quick test
    print("Testing PerformanceMonitor...")

    monitor = PerformanceMonitor(
        accuracy_window=20,
        min_samples_for_alert=10,
    )

    # Simulate predictions
    np.random.seed(42)
    classes = ["Bullish", "Neutral", "Bearish"]

    for i in range(100):
        actual = np.random.choice(classes)

        # Simulate varying accuracy
        if np.random.random() < 0.6:  # 60% accuracy
            prediction = actual
        else:
            prediction = np.random.choice(classes)

        confidence = 0.5 + np.random.random() * 0.4
        agreement = 0.5 + np.random.random() * 0.4

        monitor.record_prediction(
            prediction=prediction,
            actual=actual,
            confidence=confidence,
            agreement=agreement,
            probabilities={c: np.random.random() for c in classes},
            weights={"rf": 0.3, "gb": 0.3, "arima": 0.2, "lstm": 0.2},
            model_predictions={
                "rf": np.random.choice(classes),
                "gb": np.random.choice(classes),
                "arima": np.random.choice(classes),
                "lstm": np.random.choice(classes),
            },
        )

    # Test methods
    print(f"\nRolling Accuracy: {monitor.get_rolling_accuracy()}")
    print(f"\nModel Performance: {monitor.get_model_performance()}")
    print(f"\nDashboard Summary: {monitor.get_dashboard_summary()}")
    print(f"\nRecent Alerts: {monitor.get_recent_alerts()}")

    # Test health checker
    checker = ModelHealthChecker(monitor)
    print(f"\nModel Health: {checker.check_all_models()}")

    print("\n\nSUCCESS: PerformanceMonitor working!")
