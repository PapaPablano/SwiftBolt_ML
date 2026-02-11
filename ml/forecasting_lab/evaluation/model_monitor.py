from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Alert:
    alert_type: str
    severity: str
    message: str
    metric_value: float | None = None
    threshold_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
        }


class ModelMonitor:
    """
    Baseline + thresholds monitor.

    Note: forecasting_lab directional_accuracy is a fraction 0..1, not percent. [cite:188]
    """

    def __init__(self, thresholds: dict[str, float]):
        self.thresholds = thresholds
        self.baseline: dict[str, float] = {}

    def update_baseline(self, metrics: dict[str, float]) -> None:
        self.baseline = dict(metrics or {})

    def check_health(self, current_metrics: dict[str, Any]) -> tuple[str, list[Alert]]:
        alerts: list[Alert] = []
        m = current_metrics or {}

        mae_now = m.get("mae")
        mae_base = self.baseline.get("mae")
        if mae_now is not None and mae_base is not None and float(mae_base) != 0.0:
            pct = (float(mae_now) - float(mae_base)) / float(mae_base) * 100.0
            thr = float(self.thresholds.get("mae_degradation", 15.0))
            if pct > thr:
                alerts.append(Alert(
                    alert_type="MAE_DEGRADATION",
                    severity="CRITICAL",
                    message=f"MAE increased {pct:.1f}% vs baseline",
                    metric_value=pct,
                    threshold_value=thr,
                ))

        acc = m.get("directional_accuracy")
        if acc is not None:
            thr = float(self.thresholds.get("accuracy_drop", 0.50))
            if float(acc) < thr:
                alerts.append(Alert(
                    alert_type="ACCURACY_DROP",
                    severity="CRITICAL",
                    message=f"Directional accuracy {float(acc):.3f} below threshold",
                    metric_value=float(acc),
                    threshold_value=thr,
                ))

        drift_p = m.get("drift_p_value")
        if drift_p is not None:
            thr = float(self.thresholds.get("drift_threshold", 0.05))
            if float(drift_p) < thr:
                alerts.append(Alert(
                    alert_type="DRIFT_DETECTED",
                    severity="HIGH",
                    message=f"Drift detected (p={float(drift_p):.4f} < {thr})",
                    metric_value=float(drift_p),
                    threshold_value=thr,
                ))

        lat = m.get("prediction_latency_ms")
        if lat is not None:
            thr = float(self.thresholds.get("latency_threshold", 100.0))
            if float(lat) > thr:
                alerts.append(Alert(
                    alert_type="LATENCY",
                    severity="MEDIUM",
                    message=f"Prediction latency {float(lat):.1f}ms above threshold",
                    metric_value=float(lat),
                    threshold_value=thr,
                ))

        if not alerts:
            return "HEALTHY", []
        if any(a.severity in ("HIGH", "CRITICAL") for a in alerts):
            return "DEGRADED", alerts
        return "MONITORING", alerts


def ks_drift_p_value(historical: list[float], recent: list[float]) -> float | None:
    """KS-test drift helper; returns p-value if scipy is installed, else None."""
    try:
        from scipy.stats import ks_2samp  # type: ignore
    except Exception:
        return None
    if not historical or not recent:
        return None
    _, p = ks_2samp(historical, recent)
    return float(p)
