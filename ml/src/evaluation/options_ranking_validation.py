"""
Statistical Validation for Options Ranking System.

Provides rigorous testing to validate that the options ranking model
produces statistically significant results and not random noise.

Key validations:
- Ranking stability (consistency across time)
- Predictive accuracy (do high-ranked options outperform?)
- Score distribution analysis
- Backtesting with statistical significance
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class RankingValidationResult:
    """Result of options ranking validation."""
    metric: str
    value: float
    p_value: float
    is_significant: bool
    confidence_interval: Tuple[float, float]
    interpretation: str
    
    def __str__(self) -> str:
        sig = "✅" if self.is_significant else "❌"
        return (
            f"{sig} {self.metric}: {self.value:.4f} "
            f"(p={self.p_value:.4f}, CI=[{self.confidence_interval[0]:.4f}, "
            f"{self.confidence_interval[1]:.4f}])\n"
            f"   {self.interpretation}"
        )


class OptionsRankingValidator:
    """
    Validates options ranking model performance with statistical rigor.
    
    Example:
        ```python
        validator = OptionsRankingValidator()
        
        # Validate ranking predictions vs actual returns
        results = validator.validate_ranking_accuracy(
            ranked_options_df,
            actual_returns_df
        )
        
        # Print full report
        validator.generate_report(results)
        ```
    """
    
    def __init__(
        self,
        confidence_level: float = 0.95,
        min_samples: int = 30,
        random_state: int = 42,
    ):
        """
        Initialize validator.
        
        Args:
            confidence_level: Confidence level for statistical tests
            min_samples: Minimum samples for valid testing
            random_state: Random seed for reproducibility
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        self.min_samples = min_samples
        self.random_state = random_state
        np.random.seed(random_state)
    
    def validate_ranking_accuracy(
        self,
        rankings_df: pd.DataFrame,
        returns_df: pd.DataFrame,
        score_col: str = "ml_score",
        return_col: str = "actual_return",
        n_quantiles: int = 5,
    ) -> List[RankingValidationResult]:
        """
        Validate if high-ranked options actually outperform low-ranked ones.
        
        Tests:
        1. Spearman rank correlation between scores and returns
        2. Top quantile vs bottom quantile returns (t-test)
        3. Information coefficient (IC)
        
        Args:
            rankings_df: DataFrame with ml_score column
            returns_df: DataFrame with actual returns
            score_col: Column name for ML scores
            return_col: Column name for actual returns
            n_quantiles: Number of quantiles for analysis
        
        Returns:
            List of RankingValidationResult
        """
        results = []
        
        # Merge rankings with returns
        df = rankings_df.merge(returns_df, how="inner")
        
        if len(df) < self.min_samples:
            logger.warning(f"Insufficient samples: {len(df)} < {self.min_samples}")
            return results
        
        scores = df[score_col].values
        returns = df[return_col].values
        
        # 1. Spearman Rank Correlation
        spearman_result = self._test_spearman_correlation(scores, returns)
        results.append(spearman_result)
        
        # 2. Top vs Bottom Quantile Returns
        quantile_result = self._test_quantile_returns(df, score_col, return_col, n_quantiles)
        results.append(quantile_result)
        
        # 3. Information Coefficient
        ic_result = self._test_information_coefficient(scores, returns)
        results.append(ic_result)
        
        # 4. Hit Rate (% of positive returns in top quantile)
        hit_rate_result = self._test_hit_rate(df, score_col, return_col, n_quantiles)
        results.append(hit_rate_result)
        
        return results
    
    def _test_spearman_correlation(
        self,
        scores: np.ndarray,
        returns: np.ndarray,
    ) -> RankingValidationResult:
        """Test Spearman rank correlation between scores and returns."""
        correlation, p_value = stats.spearmanr(scores, returns)
        
        # Bootstrap confidence interval
        n_bootstrap = 1000
        boot_corrs = []
        n = len(scores)
        
        for _ in range(n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            corr, _ = stats.spearmanr(scores[idx], returns[idx])
            if np.isfinite(corr):
                boot_corrs.append(corr)
        
        ci_lower = np.percentile(boot_corrs, 2.5)
        ci_upper = np.percentile(boot_corrs, 97.5)
        
        is_significant = p_value < self.alpha and correlation > 0
        
        if is_significant:
            interp = f"Scores positively correlate with returns (ρ={correlation:.3f})"
        elif correlation > 0:
            interp = f"Weak positive correlation, not statistically significant"
        else:
            interp = f"No positive correlation between scores and returns"
        
        return RankingValidationResult(
            metric="Spearman Correlation",
            value=float(correlation),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper),
            interpretation=interp,
        )
    
    def _test_quantile_returns(
        self,
        df: pd.DataFrame,
        score_col: str,
        return_col: str,
        n_quantiles: int,
    ) -> RankingValidationResult:
        """Test if top quantile outperforms bottom quantile."""
        df = df.copy()
        df["quantile"] = pd.qcut(df[score_col], q=n_quantiles, labels=False, duplicates="drop")
        
        top_quantile = df[df["quantile"] == df["quantile"].max()][return_col]
        bottom_quantile = df[df["quantile"] == df["quantile"].min()][return_col]
        
        if len(top_quantile) < 5 or len(bottom_quantile) < 5:
            return RankingValidationResult(
                metric="Top vs Bottom Quantile",
                value=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                interpretation="Insufficient samples in quantiles",
            )
        
        # One-sided t-test: top > bottom
        statistic, p_value = stats.ttest_ind(top_quantile, bottom_quantile, alternative="greater")
        
        spread = top_quantile.mean() - bottom_quantile.mean()
        
        # Bootstrap CI for spread
        n_bootstrap = 1000
        boot_spreads = []
        
        for _ in range(n_bootstrap):
            top_sample = np.random.choice(top_quantile, size=len(top_quantile), replace=True)
            bot_sample = np.random.choice(bottom_quantile, size=len(bottom_quantile), replace=True)
            boot_spreads.append(top_sample.mean() - bot_sample.mean())
        
        ci_lower = np.percentile(boot_spreads, 2.5)
        ci_upper = np.percentile(boot_spreads, 97.5)
        
        is_significant = p_value < self.alpha and spread > 0
        
        if is_significant:
            interp = f"Top quintile outperforms bottom by {spread:.2%} (significant)"
        else:
            interp = f"Top quintile spread: {spread:.2%} (not significant)"
        
        return RankingValidationResult(
            metric="Top vs Bottom Quantile Spread",
            value=float(spread),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper),
            interpretation=interp,
        )
    
    def _test_information_coefficient(
        self,
        scores: np.ndarray,
        returns: np.ndarray,
    ) -> RankingValidationResult:
        """
        Calculate Information Coefficient (IC).
        
        IC is the correlation between predicted scores and forward returns.
        Industry standard: IC > 0.05 is considered good for options.
        """
        # Pearson correlation as IC
        correlation, p_value = stats.pearsonr(scores, returns)
        
        # Bootstrap CI
        n_bootstrap = 1000
        boot_ics = []
        n = len(scores)
        
        for _ in range(n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            corr, _ = stats.pearsonr(scores[idx], returns[idx])
            if np.isfinite(corr):
                boot_ics.append(corr)
        
        ci_lower = np.percentile(boot_ics, 2.5)
        ci_upper = np.percentile(boot_ics, 97.5)
        
        # IC > 0.05 is considered good
        is_significant = p_value < self.alpha and correlation > 0.03
        
        if correlation > 0.10:
            quality = "Excellent"
        elif correlation > 0.05:
            quality = "Good"
        elif correlation > 0.03:
            quality = "Acceptable"
        else:
            quality = "Weak"
        
        interp = f"IC = {correlation:.4f} ({quality})"
        
        return RankingValidationResult(
            metric="Information Coefficient (IC)",
            value=float(correlation),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper),
            interpretation=interp,
        )
    
    def _test_hit_rate(
        self,
        df: pd.DataFrame,
        score_col: str,
        return_col: str,
        n_quantiles: int,
    ) -> RankingValidationResult:
        """
        Test hit rate: % of positive returns in top quantile.
        
        Uses binomial test to check if hit rate > 50%.
        """
        df = df.copy()
        df["quantile"] = pd.qcut(df[score_col], q=n_quantiles, labels=False, duplicates="drop")
        
        top_quantile = df[df["quantile"] == df["quantile"].max()]
        
        n_positive = (top_quantile[return_col] > 0).sum()
        n_total = len(top_quantile)
        
        if n_total < 10:
            return RankingValidationResult(
                metric="Hit Rate (Top Quantile)",
                value=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                interpretation="Insufficient samples",
            )
        
        hit_rate = n_positive / n_total
        
        # Binomial test: is hit rate > 50%?
        result = stats.binomtest(n_positive, n_total, p=0.5, alternative="greater")
        p_value = result.pvalue
        
        # Wilson score interval for proportion
        z = stats.norm.ppf(1 - self.alpha / 2)
        denominator = 1 + z**2 / n_total
        center = (hit_rate + z**2 / (2 * n_total)) / denominator
        margin = z * np.sqrt((hit_rate * (1 - hit_rate) + z**2 / (4 * n_total)) / n_total) / denominator
        ci_lower = max(0, center - margin)
        ci_upper = min(1, center + margin)
        
        is_significant = p_value < self.alpha and hit_rate > 0.5
        
        interp = f"Hit rate: {hit_rate:.1%} ({n_positive}/{n_total} positive)"
        
        return RankingValidationResult(
            metric="Hit Rate (Top Quantile)",
            value=float(hit_rate),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper),
            interpretation=interp,
        )
    
    def validate_ranking_stability(
        self,
        rankings_over_time: List[pd.DataFrame],
        score_col: str = "ml_score",
        contract_id_col: str = "contract_symbol",
    ) -> RankingValidationResult:
        """
        Test ranking stability over time.
        
        Measures how consistent rankings are across different time periods.
        Uses Kendall's W (coefficient of concordance).
        
        Args:
            rankings_over_time: List of ranking DataFrames from different periods
            score_col: Column with ML scores
            contract_id_col: Column identifying contracts
        
        Returns:
            RankingValidationResult for stability
        """
        if len(rankings_over_time) < 3:
            return RankingValidationResult(
                metric="Ranking Stability (Kendall's W)",
                value=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                interpretation="Need at least 3 time periods",
            )
        
        # Find common contracts across all periods
        common_contracts = set(rankings_over_time[0][contract_id_col])
        for df in rankings_over_time[1:]:
            common_contracts &= set(df[contract_id_col])
        
        if len(common_contracts) < 10:
            return RankingValidationResult(
                metric="Ranking Stability (Kendall's W)",
                value=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                interpretation="Insufficient common contracts across periods",
            )
        
        # Build rank matrix
        common_list = list(common_contracts)
        n_items = len(common_list)
        n_judges = len(rankings_over_time)
        
        rank_matrix = np.zeros((n_judges, n_items))
        
        for j, df in enumerate(rankings_over_time):
            df_filtered = df[df[contract_id_col].isin(common_contracts)].copy()
            df_filtered["rank"] = df_filtered[score_col].rank(ascending=False)
            
            for i, contract in enumerate(common_list):
                rank_matrix[j, i] = df_filtered[
                    df_filtered[contract_id_col] == contract
                ]["rank"].values[0]
        
        # Calculate Kendall's W
        n = n_items
        k = n_judges
        
        rank_sums = rank_matrix.sum(axis=0)
        mean_rank_sum = rank_sums.mean()
        ss = np.sum((rank_sums - mean_rank_sum) ** 2)
        
        w = (12 * ss) / (k**2 * (n**3 - n))
        
        # Chi-square test for significance
        chi2 = k * (n - 1) * w
        df_chi = n - 1
        p_value = 1 - stats.chi2.cdf(chi2, df_chi)
        
        is_significant = p_value < self.alpha and w > 0.5
        
        if w > 0.7:
            quality = "High stability"
        elif w > 0.5:
            quality = "Moderate stability"
        elif w > 0.3:
            quality = "Low stability"
        else:
            quality = "Unstable rankings"
        
        interp = f"Kendall's W = {w:.3f} ({quality})"
        
        return RankingValidationResult(
            metric="Ranking Stability (Kendall's W)",
            value=float(w),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(max(0, w - 0.1), min(1, w + 0.1)),  # Approximate
            interpretation=interp,
        )
    
    def validate_score_distribution(
        self,
        scores: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Analyze the distribution of ML scores.
        
        Checks for:
        - Normality
        - Skewness
        - Score spread (entropy)
        
        Args:
            scores: Array of ML scores
        
        Returns:
            Dictionary with distribution metrics
        """
        scores = np.asarray(scores).flatten()
        scores = scores[np.isfinite(scores)]
        
        # Basic stats
        mean = np.mean(scores)
        std = np.std(scores)
        skewness = stats.skew(scores)
        kurtosis = stats.kurtosis(scores)
        
        # Normality test
        if len(scores) >= 20:
            _, normality_p = stats.shapiro(scores[:min(5000, len(scores))])
        else:
            normality_p = 1.0
        
        # Score spread (using entropy of binned distribution)
        hist, _ = np.histogram(scores, bins=10, density=True)
        hist = hist[hist > 0]  # Remove zeros
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        
        return {
            "mean": float(mean),
            "std": float(std),
            "skewness": float(skewness),
            "kurtosis": float(kurtosis),
            "normality_p_value": float(normality_p),
            "is_normal": normality_p > 0.05,
            "entropy": float(entropy),
            "score_range": (float(scores.min()), float(scores.max())),
            "interpretation": self._interpret_distribution(skewness, std, entropy),
        }
    
    def _interpret_distribution(
        self,
        skewness: float,
        std: float,
        entropy: float,
    ) -> str:
        """Interpret score distribution characteristics."""
        issues = []
        
        if abs(skewness) > 1:
            issues.append(f"highly skewed ({skewness:.2f})")
        
        if std < 0.1:
            issues.append("low variance (scores too similar)")
        
        if entropy < 1.5:
            issues.append("low entropy (poor differentiation)")
        
        if not issues:
            return "Good score distribution"
        
        return "Issues: " + ", ".join(issues)
    
    def generate_report(
        self,
        validation_results: List[RankingValidationResult],
        distribution_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a comprehensive validation report."""
        lines = [
            "=" * 60,
            "OPTIONS RANKING VALIDATION REPORT",
            "=" * 60,
            f"Confidence Level: {self.confidence_level * 100:.0f}%",
            "",
        ]
        
        # Validation results
        lines.append("--- Statistical Tests ---")
        n_significant = 0
        for result in validation_results:
            lines.append(str(result))
            if result.is_significant:
                n_significant += 1
        
        # Distribution stats
        if distribution_stats:
            lines.append("\n--- Score Distribution ---")
            lines.append(f"  Mean: {distribution_stats['mean']:.4f}")
            lines.append(f"  Std Dev: {distribution_stats['std']:.4f}")
            lines.append(f"  Skewness: {distribution_stats['skewness']:.4f}")
            lines.append(f"  Range: {distribution_stats['score_range']}")
            lines.append(f"  {distribution_stats['interpretation']}")
        
        # Summary
        lines.append("\n" + "=" * 60)
        if n_significant >= len(validation_results) * 0.75:
            lines.append("✅ RANKING MODEL IS STATISTICALLY VALIDATED")
        elif n_significant >= len(validation_results) * 0.5:
            lines.append("⚠️ RANKING MODEL SHOWS PARTIAL SIGNIFICANCE")
        else:
            lines.append("❌ RANKING MODEL LACKS STATISTICAL SIGNIFICANCE")
        lines.append(f"   {n_significant}/{len(validation_results)} tests passed")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience function
def validate_options_ranking(
    rankings_df: pd.DataFrame,
    returns_df: pd.DataFrame,
    score_col: str = "ml_score",
    return_col: str = "actual_return",
) -> Dict[str, Any]:
    """
    Quick validation of options ranking model.
    
    Args:
        rankings_df: DataFrame with ML scores
        returns_df: DataFrame with actual returns
        score_col: Column name for scores
        return_col: Column name for returns
    
    Returns:
        Validation report dictionary
    """
    validator = OptionsRankingValidator()
    
    results = validator.validate_ranking_accuracy(
        rankings_df, returns_df, score_col, return_col
    )
    
    dist_stats = validator.validate_score_distribution(rankings_df[score_col].values)
    
    report = validator.generate_report(results, dist_stats)
    print(report)
    
    return {
        "validation_results": results,
        "distribution_stats": dist_stats,
        "n_significant": sum(1 for r in results if r.is_significant),
        "n_tests": len(results),
    }
