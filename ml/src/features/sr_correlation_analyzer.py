"""Analyze correlation between S/R indicators to reduce redundancy.

If multiple S/R indicators (Pivot, Polynomial, Logistic) are highly correlated,
their combined weight should be reduced to avoid over-weighting structural signals.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class SRCorrelationAnalyzer:
    """
    Measures correlation between S/R indicators to optimize weights.

    If two indicators are highly correlated (r > 0.8), their combined
    weight should be reduced to avoid over-weighting that signal.
    """

    # Default weights for S/R indicators
    DEFAULT_WEIGHTS = {
        "pivot": 0.30,
        "polynomial": 0.35,
        "logistic": 0.35,
    }

    # Correlation thresholds for weight penalties
    HIGH_CORRELATION_THRESHOLD = 0.8
    MEDIUM_CORRELATION_THRESHOLD = 0.6

    def analyze(
        self,
        pivot_levels: pd.Series,
        polynomial_levels: pd.Series,
        logistic_levels: pd.Series,
    ) -> Dict:
        """
        Compute pairwise correlations and suggest weight adjustments.

        Args:
            pivot_levels: Series of pivot-based S/R levels
            polynomial_levels: Series of polynomial-based S/R levels
            logistic_levels: Series of logistic-based S/R levels

        Returns:
            Dict with correlations and suggested weight multipliers
        """
        # Ensure all series have same length
        min_len = min(len(pivot_levels), len(polynomial_levels), len(logistic_levels))
        if min_len < 10:
            logger.warning(
                f"Insufficient data for correlation analysis ({min_len} < 10)"
            )
            return self._default_result()

        pivot = pivot_levels.iloc[:min_len].values
        poly = polynomial_levels.iloc[:min_len].values
        logistic = logistic_levels.iloc[:min_len].values

        # Compute pairwise correlations
        correlations = {}
        try:
            correlations["pivot_poly"] = stats.pearsonr(pivot, poly)[0]
            correlations["pivot_logistic"] = stats.pearsonr(pivot, logistic)[0]
            correlations["poly_logistic"] = stats.pearsonr(poly, logistic)[0]
        except Exception as e:
            logger.warning(f"Correlation calculation failed: {e}")
            return self._default_result()

        # Calculate redundancy penalties
        penalties = {}
        for pair, corr in correlations.items():
            if np.isnan(corr):
                penalties[pair] = 1.0
            elif abs(corr) > self.HIGH_CORRELATION_THRESHOLD:
                penalties[pair] = 0.7  # 30% reduction for highly correlated
            elif abs(corr) > self.MEDIUM_CORRELATION_THRESHOLD:
                penalties[pair] = 0.85  # 15% reduction
            else:
                penalties[pair] = 1.0  # No reduction

        # Apply average penalty to each indicator based on its correlations
        pivot_penalty = (
            penalties["pivot_poly"] + penalties["pivot_logistic"]
        ) / 2
        poly_penalty = (
            penalties["pivot_poly"] + penalties["poly_logistic"]
        ) / 2
        logistic_penalty = (
            penalties["pivot_logistic"] + penalties["poly_logistic"]
        ) / 2

        adjusted = {
            "pivot": self.DEFAULT_WEIGHTS["pivot"] * pivot_penalty,
            "polynomial": self.DEFAULT_WEIGHTS["polynomial"] * poly_penalty,
            "logistic": self.DEFAULT_WEIGHTS["logistic"] * logistic_penalty,
        }

        # Normalize to sum to 1
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        logger.info(
            f"S/R Correlation Analysis: "
            f"pivot_poly={correlations['pivot_poly']:.2f}, "
            f"pivot_log={correlations['pivot_logistic']:.2f}, "
            f"poly_log={correlations['poly_logistic']:.2f}"
        )
        logger.info(f"Adjusted weights: {adjusted}")

        return {
            "correlations": correlations,
            "penalties": penalties,
            "adjusted_weights": adjusted,
            "original_weights": self.DEFAULT_WEIGHTS.copy(),
        }

    def _default_result(self) -> Dict:
        """Return default result when analysis fails."""
        return {
            "correlations": {
                "pivot_poly": 0.0,
                "pivot_logistic": 0.0,
                "poly_logistic": 0.0,
            },
            "penalties": {
                "pivot_poly": 1.0,
                "pivot_logistic": 1.0,
                "poly_logistic": 1.0,
            },
            "adjusted_weights": self.DEFAULT_WEIGHTS.copy(),
            "original_weights": self.DEFAULT_WEIGHTS.copy(),
        }

    def get_redundancy_score(
        self,
        pivot_levels: pd.Series,
        polynomial_levels: pd.Series,
        logistic_levels: pd.Series,
    ) -> float:
        """
        Calculate overall redundancy score (0-1).

        Higher score = more redundancy = should reduce S/R weight.

        Args:
            pivot_levels: Series of pivot-based S/R levels
            polynomial_levels: Series of polynomial-based S/R levels
            logistic_levels: Series of logistic-based S/R levels

        Returns:
            Redundancy score (0 = no redundancy, 1 = fully redundant)
        """
        result = self.analyze(pivot_levels, polynomial_levels, logistic_levels)
        correlations = result["correlations"]

        # Average absolute correlation as redundancy measure
        avg_corr = np.mean([abs(c) for c in correlations.values()])

        return float(avg_corr)


def analyze_sr_redundancy(
    pivot_levels: pd.Series,
    polynomial_levels: pd.Series,
    logistic_levels: pd.Series,
) -> Dict:
    """
    Convenience function to analyze S/R indicator redundancy.

    Args:
        pivot_levels: Pivot-based S/R levels
        polynomial_levels: Polynomial-based S/R levels
        logistic_levels: Logistic-based S/R levels

    Returns:
        Dict with correlations, penalties, and adjusted weights
    """
    analyzer = SRCorrelationAnalyzer()
    return analyzer.analyze(pivot_levels, polynomial_levels, logistic_levels)
