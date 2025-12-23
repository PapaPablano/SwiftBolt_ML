"""
Enhanced forecast quality monitoring.
Checks confidence, agreement, staleness, and conflicts.
"""

import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class ForecastQualityMonitor:
    """Monitor forecast quality with multiple metrics."""

    @staticmethod
    def compute_quality_score(forecast: Dict) -> float:
        """Compute multi-factor quality score (0-1)."""
        quality = 1.0

        confidence = forecast.get("confidence", 0.5)
        quality *= confidence

        agreement = forecast.get("model_agreement", 0.75)
        quality *= agreement

        age_hours = (
            datetime.now() - forecast["created_at"]
        ).total_seconds() / 3600
        age_decay = 0.95 ** (age_hours / 6)  # half-life 6h
        quality *= age_decay

        return quality

    @staticmethod
    def check_quality_issues(forecast: Dict) -> List[Dict]:
        """Check for quality issues in a forecast."""
        issues: List[Dict] = []

        if forecast.get("confidence", 0) < 0.50:
            issues.append(
                {
                    "level": "warning",
                    "type": "low_confidence",
                    "message": f"Low confidence: {forecast['confidence']:.0%}",
                    "action": "review",
                }
            )

        if forecast.get("model_agreement", 1) < 0.70:
            issues.append(
                {
                    "level": "info",
                    "type": "model_disagreement",
                    "message": (
                        "RF/GB disagree "
                        f"(agreement: {forecast['model_agreement']:.0%})"
                    ),
                    "action": "use_baseline_only",
                }
            )

        age_hours = (
            datetime.now() - forecast.get("created_at", datetime.now())
        ).total_seconds() / 3600
        if age_hours > 6:
            issues.append(
                {
                    "level": "warning",
                    "type": "stale_forecast",
                    "message": f"Forecast is {age_hours:.1f}h old",
                    "action": "rerun_forecast",
                }
            )

        if forecast.get("conflicting_signals", 0) > 2:
            issues.append(
                {
                    "level": "info",
                    "type": "conflicting_signals",
                    "message": (
                        f"{forecast['conflicting_signals']} indicators "
                        "conflict"
                    ),
                    "action": "review",
                }
            )

        return issues

    @staticmethod
    def check_batch_quality(forecasts: List[Dict]) -> Dict:
        """Check quality of a batch of forecasts."""
        if not forecasts:
            return {}

        quality_scores = [
            ForecastQualityMonitor.compute_quality_score(f) for f in forecasts
        ]

        all_issues: List[Dict] = []
        for forecast in forecasts:
            all_issues.extend(
                ForecastQualityMonitor.check_quality_issues(forecast)
            )

        return {
            "count": len(forecasts),
            "avg_quality_score": sum(quality_scores) / len(quality_scores),
            "min_quality_score": min(quality_scores),
            "max_quality_score": max(quality_scores),
            "low_quality_count": sum(1 for s in quality_scores if s < 0.65),
            "total_issues": len(all_issues),
            "issues_by_type": {
                "low_confidence": sum(
                    1 for issue in all_issues
                    if issue["type"] == "low_confidence"
                ),
                "model_disagreement": sum(
                    1 for issue in all_issues
                    if issue["type"] == "model_disagreement"
                ),
                "stale_forecast": sum(
                    1 for issue in all_issues
                    if issue["type"] == "stale_forecast"
                ),
            },
        }
