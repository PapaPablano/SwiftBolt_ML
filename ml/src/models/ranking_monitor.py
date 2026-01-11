"""
Ranking Monitor - Continuous validation and alerting for options ranking.

Implements Perplexity's recommendation:
"Actually use the validator in your workflow. The system should:
- compute Rank IC per day (already supported)
- compute stability metrics
- alert when:
  - IC collapses
  - leakage flags occur
  - hit rate becomes suspicious given sample size

That becomes your ranking system's equivalent of forecast_evaluations."
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of ranking alerts."""

    IC_COLLAPSE = "ic_collapse"
    IC_DEGRADATION = "ic_degradation"
    LEAKAGE_DETECTED = "leakage_detected"
    HIT_RATE_SUSPICIOUS = "hit_rate_suspicious"
    STABILITY_DEGRADED = "stability_degraded"
    INSUFFICIENT_DATA = "insufficient_data"
    CALIBRATION_DRIFT = "calibration_drift"


@dataclass
class RankingAlert:
    """Alert from ranking validation."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        icon = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
        }[self.severity]
        return (
            f"{icon} [{self.severity.value.upper()}] {self.alert_type.value}: "
            f"{self.message} (value={self.metric_value:.4f}, "
            f"threshold={self.threshold:.4f})"
        )


@dataclass
class RankingHealthReport:
    """Health report for ranking system."""

    timestamp: datetime
    is_healthy: bool
    alerts: List[RankingAlert]
    metrics: Dict[str, float]
    n_days_evaluated: int
    n_contracts_evaluated: int

    def __str__(self) -> str:
        status = "✅ HEALTHY" if self.is_healthy else "❌ UNHEALTHY"
        lines = [
            "=" * 60,
            f"RANKING HEALTH REPORT - {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
            f"Status: {status}",
            f"Days Evaluated: {self.n_days_evaluated}",
            f"Contracts Evaluated: {self.n_contracts_evaluated}",
            "",
            "--- Metrics ---",
        ]
        for key, value in self.metrics.items():
            lines.append(f"  {key}: {value:.4f}")

        if self.alerts:
            lines.append("")
            lines.append("--- Alerts ---")
            for alert in self.alerts:
                lines.append(f"  {alert}")

        lines.append("=" * 60)
        return "\n".join(lines)


class RankingMonitor:
    """
    Monitors ranking system health and generates alerts.

    Tracks:
    - Daily Rank IC (Information Coefficient)
    - Ranking stability (day-over-day correlation)
    - Hit rate in top quantile
    - Leakage indicators
    - Calibration drift

    Alerts when metrics degrade beyond thresholds.
    """

    # Alert thresholds
    IC_COLLAPSE_THRESHOLD = 0.0
    IC_DEGRADATION_THRESHOLD = 0.02
    IC_ROLLING_WINDOW = 5
    IC_DEGRADATION_PCT = 0.50

    STABILITY_THRESHOLD = 0.5
    HIT_RATE_MIN_N = 50
    HIT_RATE_SUSPICIOUS_THRESHOLD = 0.95

    MIN_DAYS_FOR_EVALUATION = 5
    MIN_CONTRACTS_PER_DAY = 25

    def __init__(
        self,
        ic_collapse_threshold: float = 0.0,
        ic_degradation_threshold: float = 0.02,
        stability_threshold: float = 0.5,
        lookback_days: int = 30,
    ):
        """
        Initialize ranking monitor.

        Args:
            ic_collapse_threshold: IC below this triggers collapse alert
            ic_degradation_threshold: IC below this triggers degradation alert
            stability_threshold: Kendall's W below this triggers stability alert
            lookback_days: Days of history to evaluate
        """
        self.ic_collapse_threshold = ic_collapse_threshold
        self.ic_degradation_threshold = ic_degradation_threshold
        self.stability_threshold = stability_threshold
        self.lookback_days = lookback_days

        self._ic_history: List[float] = []
        self._stability_history: List[float] = []
        self._hit_rate_history: List[tuple] = []
        self._alerts: List[RankingAlert] = []

    def evaluate(
        self,
        rankings_df: pd.DataFrame,
        returns_df: pd.DataFrame,
        date_col: str = "ranking_date",
        score_col: str = "composite_rank",
        return_col: str = "forward_return",
        contract_col: str = "contract_symbol",
    ) -> RankingHealthReport:
        """
        Evaluate ranking system health.

        Args:
            rankings_df: Historical rankings with scores
            returns_df: Actual forward returns
            date_col: Column with ranking dates
            score_col: Column with ranking scores
            return_col: Column with forward returns
            contract_col: Column with contract identifiers

        Returns:
            RankingHealthReport with health status and alerts
        """
        self._alerts = []
        metrics = {}

        # Merge rankings with returns
        if rankings_df is None or returns_df is None:
            return self._create_insufficient_data_report("Missing rankings or returns data")

        df = rankings_df.merge(returns_df, how="inner")

        if len(df) < self.MIN_CONTRACTS_PER_DAY * self.MIN_DAYS_FOR_EVALUATION:
            return self._create_insufficient_data_report(f"Insufficient data: {len(df)} samples")

        # Get unique dates
        dates = df[date_col].unique() if date_col in df.columns else [None]
        n_days = len(dates) if dates[0] is not None else 1

        if n_days < self.MIN_DAYS_FOR_EVALUATION:
            return self._create_insufficient_data_report(
                f"Insufficient days: {n_days} < {self.MIN_DAYS_FOR_EVALUATION}"
            )

        # Calculate metrics
        ic_stats = self._calculate_daily_ic(df, date_col, score_col, return_col)
        metrics.update(ic_stats)

        stability = self._calculate_stability(df, date_col, score_col, contract_col)
        metrics["stability"] = stability

        hit_rate_stats = self._calculate_hit_rate(df, score_col, return_col)
        metrics.update(hit_rate_stats)

        leakage_stats = self._check_leakage(df, date_col, score_col, return_col)
        metrics.update(leakage_stats)

        # Generate alerts
        self._check_ic_alerts(ic_stats)
        self._check_stability_alerts(stability)
        self._check_hit_rate_alerts(hit_rate_stats)
        self._check_leakage_alerts(leakage_stats)

        # Determine health status
        critical_alerts = [a for a in self._alerts if a.severity == AlertSeverity.CRITICAL]
        is_healthy = len(critical_alerts) == 0

        return RankingHealthReport(
            timestamp=datetime.utcnow(),
            is_healthy=is_healthy,
            alerts=self._alerts.copy(),
            metrics=metrics,
            n_days_evaluated=n_days,
            n_contracts_evaluated=len(df),
        )

    def _calculate_daily_ic(
        self,
        df: pd.DataFrame,
        date_col: str,
        score_col: str,
        return_col: str,
    ) -> Dict[str, float]:
        """Calculate daily Information Coefficient statistics."""
        from scipy import stats

        daily_ics = []

        if date_col not in df.columns:
            # Pooled IC if no date column
            corr, _ = stats.spearmanr(df[score_col], df[return_col])
            return {
                "mean_ic": float(corr) if np.isfinite(corr) else 0.0,
                "std_ic": 0.0,
                "min_ic": float(corr) if np.isfinite(corr) else 0.0,
                "max_ic": float(corr) if np.isfinite(corr) else 0.0,
                "n_days": 1,
            }

        for date in df[date_col].unique():
            day_df = df[df[date_col] == date]
            if len(day_df) >= self.MIN_CONTRACTS_PER_DAY:
                corr, _ = stats.spearmanr(day_df[score_col], day_df[return_col])
                if np.isfinite(corr):
                    daily_ics.append(corr)

        if len(daily_ics) == 0:
            return {
                "mean_ic": 0.0,
                "std_ic": 0.0,
                "min_ic": 0.0,
                "max_ic": 0.0,
                "n_days": 0,
            }

        # Update history
        self._ic_history.extend(daily_ics)
        if len(self._ic_history) > self.lookback_days:
            self._ic_history = self._ic_history[-self.lookback_days :]

        return {
            "mean_ic": float(np.mean(daily_ics)),
            "std_ic": float(np.std(daily_ics)),
            "min_ic": float(np.min(daily_ics)),
            "max_ic": float(np.max(daily_ics)),
            "n_days": len(daily_ics),
            "recent_ic_trend": self._calculate_ic_trend(),
        }

    def _calculate_ic_trend(self) -> float:
        """Calculate recent IC trend (positive = improving)."""
        if len(self._ic_history) < self.IC_ROLLING_WINDOW * 2:
            return 0.0

        recent = np.mean(self._ic_history[-self.IC_ROLLING_WINDOW :])
        previous = np.mean(self._ic_history[-self.IC_ROLLING_WINDOW * 2 : -self.IC_ROLLING_WINDOW])

        return recent - previous

    def _calculate_stability(
        self,
        df: pd.DataFrame,
        date_col: str,
        score_col: str,
        contract_col: str,
    ) -> float:
        """Calculate ranking stability using day-over-day correlation."""
        from scipy import stats

        if date_col not in df.columns:
            return 1.0

        dates = sorted(df[date_col].unique())
        if len(dates) < 2:
            return 1.0

        correlations = []

        for i in range(1, len(dates)):
            prev_date = dates[i - 1]
            curr_date = dates[i]

            prev_df = df[df[date_col] == prev_date]
            curr_df = df[df[date_col] == curr_date]

            # Find common contracts
            common = set(prev_df[contract_col]) & set(curr_df[contract_col])
            if len(common) < 10:
                continue

            prev_scores = prev_df[prev_df[contract_col].isin(common)].set_index(contract_col)[
                score_col
            ]
            curr_scores = curr_df[curr_df[contract_col].isin(common)].set_index(contract_col)[
                score_col
            ]

            # Align indices
            common_idx = prev_scores.index.intersection(curr_scores.index)
            if len(common_idx) < 10:
                continue

            corr, _ = stats.spearmanr(prev_scores.loc[common_idx], curr_scores.loc[common_idx])
            if np.isfinite(corr):
                correlations.append(corr)

        if len(correlations) == 0:
            return 1.0

        stability = float(np.mean(correlations))
        self._stability_history.append(stability)

        return stability

    def _calculate_hit_rate(
        self,
        df: pd.DataFrame,
        score_col: str,
        return_col: str,
        n_quantiles: int = 5,
    ) -> Dict[str, float]:
        """Calculate hit rate in top quantile."""
        df = df.copy()
        df["quantile"] = pd.qcut(df[score_col], q=n_quantiles, labels=False, duplicates="drop")

        top_quantile = df[df["quantile"] == df["quantile"].max()]
        n_total = len(top_quantile)

        if n_total == 0:
            return {
                "hit_rate": 0.5,
                "hit_rate_n": 0,
                "hit_rate_ci_lower": 0.0,
                "hit_rate_ci_upper": 1.0,
            }

        n_positive = (top_quantile[return_col] > 0).sum()
        hit_rate = n_positive / n_total

        # Wilson score interval
        from scipy import stats

        z = stats.norm.ppf(0.975)
        denominator = 1 + z**2 / n_total
        center = (hit_rate + z**2 / (2 * n_total)) / denominator
        margin = (
            z * np.sqrt((hit_rate * (1 - hit_rate) + z**2 / (4 * n_total)) / n_total) / denominator
        )

        self._hit_rate_history.append((hit_rate, n_total))

        return {
            "hit_rate": float(hit_rate),
            "hit_rate_n": n_total,
            "hit_rate_ci_lower": float(max(0, center - margin)),
            "hit_rate_ci_upper": float(min(1, center + margin)),
        }

    def _check_leakage(
        self,
        df: pd.DataFrame,
        date_col: str,
        score_col: str,
        return_col: str,
    ) -> Dict[str, Any]:
        """Check for leakage indicators."""
        from scipy import stats

        # Quick permutation test (fewer iterations for monitoring)
        n_permutations = 100
        actual_corr, _ = stats.spearmanr(df[score_col], df[return_col])

        permuted_corrs = []
        for _ in range(n_permutations):
            shuffled = df[return_col].values.copy()
            np.random.shuffle(shuffled)
            corr, _ = stats.spearmanr(df[score_col], shuffled)
            if np.isfinite(corr):
                permuted_corrs.append(corr)

        if len(permuted_corrs) == 0:
            return {
                "leakage_score": 0.0,
                "permuted_ic_mean": 0.0,
                "leakage_suspected": False,
            }

        permuted_mean = np.mean(permuted_corrs)
        permuted_std = np.std(permuted_corrs)

        # Leakage score: how many std devs is permuted mean from 0
        leakage_score = abs(permuted_mean) / (permuted_std + 1e-10)

        # Leakage suspected if permuted IC is not near 0
        leakage_suspected = abs(permuted_mean) > 0.02

        return {
            "leakage_score": float(leakage_score),
            "permuted_ic_mean": float(permuted_mean),
            "permuted_ic_std": float(permuted_std),
            "leakage_suspected": leakage_suspected,
        }

    def _check_ic_alerts(self, ic_stats: Dict[str, float]) -> None:
        """Generate IC-related alerts."""
        mean_ic = ic_stats.get("mean_ic", 0.0)
        ic_trend = ic_stats.get("recent_ic_trend", 0.0)

        # IC collapse
        if mean_ic <= self.ic_collapse_threshold:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.IC_COLLAPSE,
                    severity=AlertSeverity.CRITICAL,
                    message=f"Mean IC collapsed to {mean_ic:.4f}",
                    metric_value=mean_ic,
                    threshold=self.ic_collapse_threshold,
                    details=ic_stats,
                )
            )
        # IC degradation
        elif mean_ic < self.ic_degradation_threshold:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.IC_DEGRADATION,
                    severity=AlertSeverity.WARNING,
                    message=f"Mean IC degraded to {mean_ic:.4f}",
                    metric_value=mean_ic,
                    threshold=self.ic_degradation_threshold,
                    details=ic_stats,
                )
            )

        # IC trend degradation
        if ic_trend < -0.02 and len(self._ic_history) >= self.IC_ROLLING_WINDOW * 2:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.IC_DEGRADATION,
                    severity=AlertSeverity.WARNING,
                    message=f"IC trending down: {ic_trend:.4f}",
                    metric_value=ic_trend,
                    threshold=-0.02,
                    details={"ic_history": self._ic_history[-10:]},
                )
            )

    def _check_stability_alerts(self, stability: float) -> None:
        """Generate stability-related alerts."""
        if stability < self.stability_threshold:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.STABILITY_DEGRADED,
                    severity=AlertSeverity.WARNING,
                    message=f"Ranking stability degraded to {stability:.4f}",
                    metric_value=stability,
                    threshold=self.stability_threshold,
                )
            )

    def _check_hit_rate_alerts(self, hit_rate_stats: Dict[str, float]) -> None:
        """Generate hit rate-related alerts."""
        hit_rate = hit_rate_stats.get("hit_rate", 0.5)
        n = hit_rate_stats.get("hit_rate_n", 0)

        # Suspicious hit rate (too good to be true with small sample)
        if hit_rate >= self.HIT_RATE_SUSPICIOUS_THRESHOLD and n < self.HIT_RATE_MIN_N:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.HIT_RATE_SUSPICIOUS,
                    severity=AlertSeverity.WARNING,
                    message=f"Hit rate {hit_rate:.1%} with only n={n} samples",
                    metric_value=hit_rate,
                    threshold=self.HIT_RATE_SUSPICIOUS_THRESHOLD,
                    details=hit_rate_stats,
                )
            )

        # Perfect hit rate is always suspicious
        if hit_rate == 1.0 and n > 0:
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.HIT_RATE_SUSPICIOUS,
                    severity=AlertSeverity.CRITICAL if n < 20 else AlertSeverity.WARNING,
                    message=f"Perfect 100% hit rate with n={n} - likely artifact",
                    metric_value=hit_rate,
                    threshold=1.0,
                    details=hit_rate_stats,
                )
            )

    def _check_leakage_alerts(self, leakage_stats: Dict[str, Any]) -> None:
        """Generate leakage-related alerts."""
        if leakage_stats.get("leakage_suspected", False):
            self._alerts.append(
                RankingAlert(
                    alert_type=AlertType.LEAKAGE_DETECTED,
                    severity=AlertSeverity.CRITICAL,
                    message="Data leakage suspected - permuted IC not near 0",
                    metric_value=leakage_stats.get("permuted_ic_mean", 0.0),
                    threshold=0.02,
                    details=leakage_stats,
                )
            )

    def _create_insufficient_data_report(self, reason: str) -> RankingHealthReport:
        """Create report for insufficient data."""
        alert = RankingAlert(
            alert_type=AlertType.INSUFFICIENT_DATA,
            severity=AlertSeverity.INFO,
            message=reason,
            metric_value=0.0,
            threshold=0.0,
        )

        return RankingHealthReport(
            timestamp=datetime.utcnow(),
            is_healthy=True,
            alerts=[alert],
            metrics={},
            n_days_evaluated=0,
            n_contracts_evaluated=0,
        )

    def get_alert_summary(self) -> str:
        """Get summary of recent alerts."""
        if not self._alerts:
            return "No alerts"

        critical = sum(1 for a in self._alerts if a.severity == AlertSeverity.CRITICAL)
        warning = sum(1 for a in self._alerts if a.severity == AlertSeverity.WARNING)
        info = sum(1 for a in self._alerts if a.severity == AlertSeverity.INFO)

        return f"Alerts: {critical} critical, {warning} warning, {info} info"


class RankingEvaluationJob:
    """
    Scheduled job for ranking evaluation - equivalent to forecast_evaluations.

    Runs periodically to:
    1. Compute daily Rank IC
    2. Check for degradation
    3. Store results to database
    4. Generate alerts
    """

    def __init__(
        self,
        db_client: Any = None,
        lookback_days: int = 30,
        evaluation_horizon: str = "1D",
    ):
        """
        Initialize evaluation job.

        Args:
            db_client: Database client for storing results
            lookback_days: Days of history to evaluate
            evaluation_horizon: Return horizon for IC calculation
        """
        self.db_client = db_client
        self.lookback_days = lookback_days
        self.evaluation_horizon = evaluation_horizon
        self.monitor = RankingMonitor(lookback_days=lookback_days)

    def run(
        self,
        rankings_df: pd.DataFrame,
        returns_df: pd.DataFrame,
    ) -> RankingHealthReport:
        """
        Run evaluation job.

        Args:
            rankings_df: Historical rankings
            returns_df: Actual forward returns

        Returns:
            RankingHealthReport
        """
        report = self.monitor.evaluate(rankings_df, returns_df)

        # Log results
        logger.info(f"Ranking evaluation complete: {report}")

        # Store to database if client available
        if self.db_client is not None:
            self._store_evaluation(report)

        # Log alerts
        for alert in report.alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                logger.error(str(alert))
            elif alert.severity == AlertSeverity.WARNING:
                logger.warning(str(alert))
            else:
                logger.info(str(alert))

        return report

    def _store_evaluation(self, report: RankingHealthReport) -> None:
        """Store evaluation results to database."""
        try:
            record = {
                "evaluated_at": report.timestamp.isoformat(),
                "is_healthy": report.is_healthy,
                "n_days": report.n_days_evaluated,
                "n_contracts": report.n_contracts_evaluated,
                "mean_ic": report.metrics.get("mean_ic", 0.0),
                "std_ic": report.metrics.get("std_ic", 0.0),
                "stability": report.metrics.get("stability", 0.0),
                "hit_rate": report.metrics.get("hit_rate", 0.0),
                "leakage_suspected": report.metrics.get("leakage_suspected", False),
                "n_alerts": len(report.alerts),
                "alert_types": [a.alert_type.value for a in report.alerts],
                "horizon": self.evaluation_horizon,
            }

            self.db_client.table("ranking_evaluations").insert(record).execute()
            logger.info("Stored ranking evaluation to database")

        except Exception as e:
            logger.error(f"Failed to store evaluation: {e}")
