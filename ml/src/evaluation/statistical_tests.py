"""
Statistical Significance Testing for ML Model Performance.

Provides rigorous statistical tests to validate that model performance
metrics (MAE, RMSE, R², MAPE) are statistically significant and not
due to random chance.

Tests included:
- Bootstrap confidence intervals for all metrics
- Paired t-test for model comparison
- Permutation test for baseline comparison
- Diebold-Mariano test for forecast comparison
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceInterval:
    """Confidence interval for a metric."""

    metric: str
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    std_error: float

    def __str__(self) -> str:
        return (
            f"{self.metric}: {self.point_estimate:.4f} "
            f"[{self.lower_bound:.4f}, {self.upper_bound:.4f}] "
            f"({self.confidence_level*100:.0f}% CI)"
        )

    def is_significant(self, null_value: float = 0.0) -> bool:
        """Check if CI excludes the null value."""
        return not (self.lower_bound <= null_value <= self.upper_bound)


@dataclass
class HypothesisTestResult:
    """Result of a statistical hypothesis test."""

    test_name: str
    statistic: float
    p_value: float
    is_significant: bool
    effect_size: Optional[float] = None
    interpretation: str = ""

    def __str__(self) -> str:
        sig = "✅ Significant" if self.is_significant else "❌ Not significant"
        return (
            f"{self.test_name}: {sig}\n"
            f"  Statistic: {self.statistic:.4f}\n"
            f"  P-value: {self.p_value:.4f}\n"
            f"  {self.interpretation}"
        )


class StatisticalSignificanceTester:
    """
    Comprehensive statistical significance testing for ML models.

    Example:
        ```python
        tester = StatisticalSignificanceTester(confidence_level=0.95)

        # Get confidence intervals for metrics
        ci_results = tester.bootstrap_confidence_intervals(
            y_true, y_pred, n_bootstrap=1000
        )
        for ci in ci_results:
            print(ci)

        # Compare two models
        comparison = tester.paired_t_test(
            errors_model1, errors_model2
        )
        print(comparison)
        ```
    """

    def __init__(
        self,
        confidence_level: float = 0.95,
        random_state: int = 42,
    ):
        """
        Initialize the tester.

        Args:
            confidence_level: Confidence level for intervals (default 0.95)
            random_state: Random seed for reproducibility
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        self.random_state = random_state
        np.random.seed(random_state)

    def bootstrap_confidence_intervals(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        n_bootstrap: int = 1000,
        metrics: Optional[List[str]] = None,
    ) -> List[ConfidenceInterval]:
        """
        Calculate bootstrap confidence intervals for regression metrics.

        Uses the percentile bootstrap method to estimate confidence
        intervals without assuming normality.

        Args:
            y_true: True values
            y_pred: Predicted values
            n_bootstrap: Number of bootstrap samples
            metrics: List of metrics to compute (default: all)

        Returns:
            List of ConfidenceInterval objects
        """
        if metrics is None:
            metrics = ["MAE", "RMSE", "R2", "MAPE"]

        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()
        n_samples = len(y_true)

        # Store bootstrap samples for each metric
        bootstrap_results: Dict[str, List[float]] = {m: [] for m in metrics}

        for _ in range(n_bootstrap):
            # Sample with replacement
            indices = np.random.choice(n_samples, size=n_samples, replace=True)
            y_true_boot = y_true[indices]
            y_pred_boot = y_pred[indices]

            # Calculate metrics
            if "MAE" in metrics:
                bootstrap_results["MAE"].append(mean_absolute_error(y_true_boot, y_pred_boot))
            if "RMSE" in metrics:
                bootstrap_results["RMSE"].append(
                    np.sqrt(mean_squared_error(y_true_boot, y_pred_boot))
                )
            if "R2" in metrics:
                bootstrap_results["R2"].append(r2_score(y_true_boot, y_pred_boot))
            if "MAPE" in metrics:
                with np.errstate(divide="ignore", invalid="ignore"):
                    mape_vals = np.abs((y_true_boot - y_pred_boot) / y_true_boot)
                    mape = np.nanmean(mape_vals[np.isfinite(mape_vals)]) * 100
                    bootstrap_results["MAPE"].append(mape)

        # Calculate confidence intervals
        results = []
        lower_percentile = (self.alpha / 2) * 100
        upper_percentile = (1 - self.alpha / 2) * 100

        for metric in metrics:
            samples = np.array(bootstrap_results[metric])
            samples = samples[np.isfinite(samples)]  # Remove NaN/Inf

            if len(samples) == 0:
                continue

            point_estimate = np.mean(samples)
            lower = np.percentile(samples, lower_percentile)
            upper = np.percentile(samples, upper_percentile)
            std_error = np.std(samples)

            results.append(
                ConfidenceInterval(
                    metric=metric,
                    point_estimate=point_estimate,
                    lower_bound=lower,
                    upper_bound=upper,
                    confidence_level=self.confidence_level,
                    std_error=std_error,
                )
            )

        return results

    def paired_t_test(
        self,
        errors_model1: np.ndarray,
        errors_model2: np.ndarray,
        alternative: str = "two-sided",
    ) -> HypothesisTestResult:
        """
        Paired t-test to compare two models' prediction errors.

        Tests whether model1 has significantly different errors than model2.

        Args:
            errors_model1: Absolute errors from model 1
            errors_model2: Absolute errors from model 2
            alternative: 'two-sided', 'less', or 'greater'

        Returns:
            HypothesisTestResult with test statistics
        """
        errors1 = np.asarray(errors_model1).flatten()
        errors2 = np.asarray(errors_model2).flatten()

        if len(errors1) != len(errors2):
            raise ValueError("Error arrays must have same length")

        # Paired t-test
        statistic, p_value = stats.ttest_rel(errors1, errors2, alternative=alternative)

        # Effect size (Cohen's d for paired samples)
        diff = errors1 - errors2
        effect_size = np.mean(diff) / np.std(diff, ddof=1)

        is_significant = p_value < self.alpha

        # Interpretation
        if is_significant:
            if np.mean(errors1) < np.mean(errors2):
                interp = "Model 1 significantly outperforms Model 2"
            else:
                interp = "Model 2 significantly outperforms Model 1"
        else:
            interp = "No significant difference between models"

        return HypothesisTestResult(
            test_name="Paired t-test",
            statistic=float(statistic),
            p_value=float(p_value),
            is_significant=is_significant,
            effect_size=float(effect_size),
            interpretation=interp,
        )

    def permutation_test(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        n_permutations: int = 1000,
        metric: str = "MAE",
    ) -> HypothesisTestResult:
        """
        Permutation test to check if model beats random baseline.

        Tests whether the model's performance is significantly better
        than what would be expected by random chance.

        Args:
            y_true: True values
            y_pred: Predicted values
            n_permutations: Number of permutations
            metric: Metric to test ('MAE', 'RMSE', 'R2')

        Returns:
            HypothesisTestResult
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()

        # Calculate observed metric
        if metric == "MAE":
            observed = mean_absolute_error(y_true, y_pred)
            better_is_lower = True
        elif metric == "RMSE":
            observed = np.sqrt(mean_squared_error(y_true, y_pred))
            better_is_lower = True
        elif metric == "R2":
            observed = r2_score(y_true, y_pred)
            better_is_lower = False
        else:
            raise ValueError(f"Unknown metric: {metric}")

        # Generate null distribution by permuting predictions
        null_distribution = []
        for _ in range(n_permutations):
            y_pred_perm = np.random.permutation(y_pred)

            if metric == "MAE":
                null_val = mean_absolute_error(y_true, y_pred_perm)
            elif metric == "RMSE":
                null_val = np.sqrt(mean_squared_error(y_true, y_pred_perm))
            else:  # R2
                null_val = r2_score(y_true, y_pred_perm)

            null_distribution.append(null_val)

        null_distribution = np.array(null_distribution)

        # Calculate p-value
        if better_is_lower:
            p_value = np.mean(null_distribution <= observed)
        else:
            p_value = np.mean(null_distribution >= observed)

        is_significant = p_value < self.alpha

        # Effect size: how many std devs from null mean
        effect_size = (observed - np.mean(null_distribution)) / np.std(null_distribution)

        interp = (
            f"Model {metric}={observed:.4f} vs null mean={np.mean(null_distribution):.4f}. "
            f"{'Significantly better than random' if is_significant else 'Not significantly better than random'}"
        )

        return HypothesisTestResult(
            test_name=f"Permutation test ({metric})",
            statistic=float(observed),
            p_value=float(p_value),
            is_significant=is_significant,
            effect_size=float(effect_size),
            interpretation=interp,
        )

    def diebold_mariano_test(
        self,
        y_true: np.ndarray,
        y_pred1: np.ndarray,
        y_pred2: np.ndarray,
        loss_function: str = "squared",
    ) -> HypothesisTestResult:
        """
        Diebold-Mariano test for comparing forecast accuracy.

        Standard test in econometrics for comparing two forecasts.
        Tests whether the forecasts have equal predictive accuracy.

        Args:
            y_true: True values
            y_pred1: Predictions from model 1
            y_pred2: Predictions from model 2
            loss_function: 'squared' or 'absolute'

        Returns:
            HypothesisTestResult
        """
        y_true = np.asarray(y_true).flatten()
        y_pred1 = np.asarray(y_pred1).flatten()
        y_pred2 = np.asarray(y_pred2).flatten()

        # Calculate loss differentials
        if loss_function == "squared":
            loss1 = (y_true - y_pred1) ** 2
            loss2 = (y_true - y_pred2) ** 2
        else:  # absolute
            loss1 = np.abs(y_true - y_pred1)
            loss2 = np.abs(y_true - y_pred2)

        d = loss1 - loss2  # Loss differential

        # DM statistic
        n = len(d)
        d_mean = np.mean(d)

        # Newey-West variance estimator (handles autocorrelation)
        # Using h-1 lags where h is the forecast horizon (assume 1 for simplicity)
        gamma_0 = np.var(d, ddof=1)
        dm_var = gamma_0 / n

        dm_statistic = d_mean / np.sqrt(dm_var)

        # Two-sided p-value from normal distribution
        p_value = 2 * (1 - stats.norm.cdf(abs(dm_statistic)))

        is_significant = p_value < self.alpha

        if is_significant:
            if d_mean < 0:
                interp = "Model 1 significantly more accurate than Model 2"
            else:
                interp = "Model 2 significantly more accurate than Model 1"
        else:
            interp = "No significant difference in forecast accuracy"

        return HypothesisTestResult(
            test_name="Diebold-Mariano test",
            statistic=float(dm_statistic),
            p_value=float(p_value),
            is_significant=is_significant,
            effect_size=float(d_mean),
            interpretation=interp,
        )

    def directional_accuracy_test(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> HypothesisTestResult:
        """
        Test if directional accuracy is significantly better than 50%.

        Uses binomial test to check if the model predicts direction
        better than random chance.

        Args:
            y_true: True values
            y_pred: Predicted values

        Returns:
            HypothesisTestResult
        """
        y_true = np.asarray(y_true).flatten()
        y_pred = np.asarray(y_pred).flatten()

        if len(y_true) < 2:
            raise ValueError("Need at least 2 samples")

        # Calculate directional accuracy
        direction_true = np.diff(y_true) > 0
        direction_pred = np.diff(y_pred) > 0

        n_correct = np.sum(direction_true == direction_pred)
        n_total = len(direction_true)
        accuracy = n_correct / n_total

        # Binomial test: is accuracy significantly > 0.5?
        result = stats.binomtest(n_correct, n_total, p=0.5, alternative="greater")
        p_value = result.pvalue

        is_significant = p_value < self.alpha

        interp = (
            f"Directional accuracy: {accuracy:.2%} ({n_correct}/{n_total}). "
            f"{'Significantly better than random (50%)' if is_significant else 'Not significantly better than random'}"
        )

        return HypothesisTestResult(
            test_name="Directional accuracy test",
            statistic=float(accuracy),
            p_value=float(p_value),
            is_significant=is_significant,
            effect_size=float(accuracy - 0.5),
            interpretation=interp,
        )

    def generate_full_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str = "Model",
        n_bootstrap: int = 1000,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive statistical significance report.

        Args:
            y_true: True values
            y_pred: Predicted values
            model_name: Name of the model for the report
            n_bootstrap: Number of bootstrap samples

        Returns:
            Dictionary with all test results
        """
        logger.info(f"Generating statistical significance report for {model_name}")

        # Bootstrap confidence intervals
        ci_results = self.bootstrap_confidence_intervals(y_true, y_pred, n_bootstrap=n_bootstrap)

        # Permutation tests
        perm_mae = self.permutation_test(y_true, y_pred, metric="MAE")
        perm_r2 = self.permutation_test(y_true, y_pred, metric="R2")

        # Directional accuracy test
        dir_test = self.directional_accuracy_test(y_true, y_pred)

        # Build report
        report = {
            "model_name": model_name,
            "n_samples": len(y_true),
            "confidence_level": self.confidence_level,
            "confidence_intervals": {
                ci.metric: {
                    "point_estimate": ci.point_estimate,
                    "lower_bound": ci.lower_bound,
                    "upper_bound": ci.upper_bound,
                    "std_error": ci.std_error,
                }
                for ci in ci_results
            },
            "permutation_tests": {
                "MAE": {
                    "p_value": perm_mae.p_value,
                    "is_significant": perm_mae.is_significant,
                    "effect_size": perm_mae.effect_size,
                },
                "R2": {
                    "p_value": perm_r2.p_value,
                    "is_significant": perm_r2.is_significant,
                    "effect_size": perm_r2.effect_size,
                },
            },
            "directional_accuracy": {
                "accuracy": dir_test.statistic,
                "p_value": dir_test.p_value,
                "is_significant": dir_test.is_significant,
            },
            "overall_significant": all(
                [
                    perm_mae.is_significant,
                    dir_test.is_significant,
                ]
            ),
        }

        # Print summary
        print("\n" + "=" * 60)
        print(f"STATISTICAL SIGNIFICANCE REPORT: {model_name}")
        print("=" * 60)
        print(f"\nSamples: {len(y_true)}")
        print(f"Confidence Level: {self.confidence_level*100:.0f}%")

        print("\n--- Confidence Intervals ---")
        for ci in ci_results:
            print(f"  {ci}")

        print("\n--- Permutation Tests (vs Random) ---")
        print(f"  {perm_mae}")
        print(f"  {perm_r2}")

        print("\n--- Directional Accuracy ---")
        print(f"  {dir_test}")

        print("\n" + "=" * 60)
        if report["overall_significant"]:
            print("✅ MODEL PERFORMANCE IS STATISTICALLY SIGNIFICANT")
        else:
            print("⚠️ MODEL PERFORMANCE MAY NOT BE STATISTICALLY SIGNIFICANT")
        print("=" * 60 + "\n")

        return report


# Convenience function for quick testing
def validate_model_significance(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str = "Model",
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """
    Quick validation of model statistical significance.

    Args:
        y_true: True values
        y_pred: Predicted values
        model_name: Name for the report
        confidence_level: Confidence level (default 0.95)

    Returns:
        Full statistical report
    """
    tester = StatisticalSignificanceTester(confidence_level=confidence_level)
    return tester.generate_full_report(y_true, y_pred, model_name)
