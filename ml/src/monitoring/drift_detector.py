"""
Data drift detection for ML models.

Uses Kolmogorov-Smirnov test to detect distribution shifts
between training and production data.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    """Result of drift detection for a single feature."""

    feature: str
    statistic: float
    p_value: float
    is_drifted: bool
    drift_severity: str  # 'none', 'low', 'medium', 'high'

    def __str__(self) -> str:
        status = "⚠️ DRIFT" if self.is_drifted else "✅ OK"
        return f"{self.feature}: {status} " f"(KS={self.statistic:.4f}, p={self.p_value:.4f})"


class DriftDetector:
    """
    Detect data drift using Kolmogorov-Smirnov test.

    The KS test compares the cumulative distribution functions
    of two samples to determine if they come from the same
    distribution.

    Example:
        ```python
        detector = DriftDetector(significance_level=0.05)

        # Compare training vs production distributions
        results = detector.detect_drift(
            reference_df=training_data,
            current_df=production_data,
            features=['rsi', 'macd', 'volume']
        )

        for result in results:
            print(result)
        ```
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        min_samples: int = 30,
    ):
        """
        Initialize drift detector.

        Args:
            significance_level: P-value threshold for drift detection
            min_samples: Minimum samples required for valid test
        """
        self.significance_level = significance_level
        self.min_samples = min_samples

    def detect_drift(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        features: Optional[list[str]] = None,
    ) -> list[DriftResult]:
        """
        Detect drift between reference and current data.

        Args:
            reference_df: Reference (training) data
            current_df: Current (production) data
            features: List of features to check (default: all numeric)

        Returns:
            List of DriftResult for each feature
        """
        if features is None:
            # Use all numeric columns present in both DataFrames
            ref_numeric = reference_df.select_dtypes(include=[np.number])
            cur_numeric = current_df.select_dtypes(include=[np.number])
            features = list(set(ref_numeric.columns) & set(cur_numeric.columns))

        results = []
        for feature in features:
            result = self._test_feature(
                reference_df[feature].dropna(),
                current_df[feature].dropna(),
                feature,
            )
            results.append(result)

        return results

    def _test_feature(
        self,
        reference: pd.Series,
        current: pd.Series,
        feature_name: str,
    ) -> DriftResult:
        """Run KS test on a single feature."""
        # Check minimum samples
        if len(reference) < self.min_samples:
            logger.warning(
                f"{feature_name}: Insufficient reference samples "
                f"({len(reference)} < {self.min_samples})"
            )
            return DriftResult(
                feature=feature_name,
                statistic=0.0,
                p_value=1.0,
                is_drifted=False,
                drift_severity="none",
            )

        if len(current) < self.min_samples:
            logger.warning(
                f"{feature_name}: Insufficient current samples "
                f"({len(current)} < {self.min_samples})"
            )
            return DriftResult(
                feature=feature_name,
                statistic=0.0,
                p_value=1.0,
                is_drifted=False,
                drift_severity="none",
            )

        # Run KS test
        statistic, p_value = stats.ks_2samp(reference, current)

        # Convert to native Python types
        statistic = float(statistic)
        p_value = float(p_value)

        # Determine drift
        is_drifted = bool(p_value < self.significance_level)

        # Classify severity based on KS statistic
        if statistic < 0.1:
            severity = "none"
        elif statistic < 0.2:
            severity = "low"
        elif statistic < 0.3:
            severity = "medium"
        else:
            severity = "high"

        return DriftResult(
            feature=feature_name,
            statistic=statistic,
            p_value=p_value,
            is_drifted=is_drifted,
            drift_severity=severity,
        )

    def detect_drift_over_time(
        self,
        data: pd.DataFrame,
        features: list[str],
        window_size: int = 30,
        step_size: int = 7,
    ) -> pd.DataFrame:
        """
        Detect drift over rolling time windows.

        Args:
            data: Time-indexed DataFrame
            features: Features to monitor
            window_size: Size of each window in days
            step_size: Step between windows in days

        Returns:
            DataFrame with drift metrics over time
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")

        results = []
        dates = data.index.unique()

        # Use first window as reference
        ref_end = dates[min(window_size, len(dates) - 1)]
        reference = data[data.index <= ref_end]

        # Slide through remaining data
        for i in range(window_size, len(dates), step_size):
            window_start = dates[i - window_size]
            window_end = dates[min(i, len(dates) - 1)]

            current = data[(data.index > window_start) & (data.index <= window_end)]

            if len(current) < self.min_samples:
                continue

            drift_results = self.detect_drift(reference, current, features)

            row = {
                "date": window_end,
                "n_drifted": sum(1 for r in drift_results if r.is_drifted),
                "n_features": len(features),
            }

            for result in drift_results:
                row[f"{result.feature}_ks"] = result.statistic
                row[f"{result.feature}_pval"] = result.p_value

            results.append(row)

        return pd.DataFrame(results)

    def generate_report(
        self,
        results: list[DriftResult],
    ) -> str:
        """Generate human-readable drift report."""
        drifted = [r for r in results if r.is_drifted]
        total = len(results)

        report = [
            "=" * 60,
            "DATA DRIFT REPORT",
            "=" * 60,
            f"Features analyzed: {total}",
            f"Features with drift: {len(drifted)}",
            f"Significance level: {self.significance_level}",
            "",
        ]

        if drifted:
            report.append("⚠️ DRIFTED FEATURES:")
            for r in sorted(drifted, key=lambda x: x.statistic, reverse=True):
                report.append(
                    f"  - {r.feature}: KS={r.statistic:.4f}, "
                    f"p={r.p_value:.4f} ({r.drift_severity})"
                )
        else:
            report.append("✅ No significant drift detected")

        report.append("")
        report.append("ALL FEATURES:")
        for r in sorted(results, key=lambda x: x.statistic, reverse=True):
            status = "⚠️" if r.is_drifted else "✅"
            report.append(f"  {status} {r.feature}: " f"KS={r.statistic:.4f}, p={r.p_value:.4f}")

        return "\n".join(report)
