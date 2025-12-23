"""
Statistical Validation for Options Ranking System.

Provides rigorous testing to validate that the options ranking model
produces statistically significant results and not random noise.

Key validations:
- Ranking stability (consistency across time)
- Predictive accuracy (do high-ranked options outperform?)
- Score distribution analysis
- Backtesting with statistical significance
- Data leakage detection
- Proper IC calculation with forward returns
- Execution realism (bid/ask spreads)
- Permutation tests for leakage detection
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# =============================================================================
# LEAKAGE DETECTION
# =============================================================================

@dataclass
class LeakageCheckResult:
    """Result of a leakage check."""
    check_name: str
    passed: bool
    n_violations: int
    violation_rate: float
    details: str

    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} {self.check_name}: {self.details}"


class LeakageDetector:
    """
    Detects data leakage in options ranking validation.

    Leakage occurs when:
    1. Features use data from after the ranking timestamp
    2. Returns are computed using prices before the ranking time
    3. Feature window overlaps with label window
    """

    def __init__(self, tolerance_seconds: int = 0):
        """
        Args:
            tolerance_seconds: Allow this many seconds of overlap (0 = strict)
        """
        self.tolerance_seconds = tolerance_seconds

    def run_leakage_checklist(
        self,
        df: pd.DataFrame,
        ranking_time_col: str = "ranking_timestamp",
        feature_time_col: str = "feature_timestamp",
        return_start_col: str = "return_start_timestamp",
        return_end_col: str = "return_end_timestamp",
    ) -> List[LeakageCheckResult]:
        """
        Run complete leakage checklist.

        Required columns:
        - ranking_timestamp: When the ranking was made
        - feature_timestamp: Latest data used for features
        - return_start_timestamp: When return measurement starts
        - return_end_timestamp: When return measurement ends

        Returns:
            List of LeakageCheckResult
        """
        results = []

        # Check 1: Feature timestamp <= ranking timestamp
        if feature_time_col in df.columns and ranking_time_col in df.columns:
            result = self._check_feature_timing(
                df, feature_time_col, ranking_time_col
            )
            results.append(result)

        # Check 2: Return start >= ranking timestamp
        if return_start_col in df.columns and ranking_time_col in df.columns:
            result = self._check_return_start_timing(
                df, return_start_col, ranking_time_col
            )
            results.append(result)

        # Check 3: Feature window end < label window start
        if feature_time_col in df.columns and return_start_col in df.columns:
            result = self._check_window_overlap(
                df, feature_time_col, return_start_col
            )
            results.append(result)

        # Check 4: No future data in features
        result = self._check_lookahead_bias(df)
        results.append(result)

        return results

    def _check_feature_timing(
        self,
        df: pd.DataFrame,
        feature_col: str,
        ranking_col: str,
    ) -> LeakageCheckResult:
        """Assert every feature timestamp uses data <= ranking time."""
        feature_times = pd.to_datetime(df[feature_col])
        ranking_times = pd.to_datetime(df[ranking_col])

        violations = feature_times > ranking_times
        n_violations = violations.sum()
        violation_rate = n_violations / len(df) if len(df) > 0 else 0

        passed = n_violations == 0

        return LeakageCheckResult(
            check_name="Feature Timing",
            passed=passed,
            n_violations=int(n_violations),
            violation_rate=float(violation_rate),
            details=f"{n_violations} rows have features from after ranking time"
            if not passed else "All features use data before ranking time",
        )

    def _check_return_start_timing(
        self,
        df: pd.DataFrame,
        return_start_col: str,
        ranking_col: str,
    ) -> LeakageCheckResult:
        """Assert returns are computed from prices after ranking time."""
        return_starts = pd.to_datetime(df[return_start_col])
        ranking_times = pd.to_datetime(df[ranking_col])

        violations = return_starts < ranking_times
        n_violations = violations.sum()
        violation_rate = n_violations / len(df) if len(df) > 0 else 0

        passed = n_violations == 0

        return LeakageCheckResult(
            check_name="Return Start Timing",
            passed=passed,
            n_violations=int(n_violations),
            violation_rate=float(violation_rate),
            details=f"{n_violations} rows compute returns from before ranking"
            if not passed else "All returns start after ranking time",
        )

    def _check_window_overlap(
        self,
        df: pd.DataFrame,
        feature_col: str,
        return_start_col: str,
    ) -> LeakageCheckResult:
        """Reject rows where feature window end >= label window start."""
        feature_times = pd.to_datetime(df[feature_col])
        return_starts = pd.to_datetime(df[return_start_col])

        # Feature window should end before return window starts
        violations = feature_times >= return_starts
        n_violations = violations.sum()
        violation_rate = n_violations / len(df) if len(df) > 0 else 0

        passed = n_violations == 0

        return LeakageCheckResult(
            check_name="Window Overlap",
            passed=passed,
            n_violations=int(n_violations),
            violation_rate=float(violation_rate),
            details=f"{n_violations} rows have overlapping feature/label windows"
            if not passed else "No window overlap detected",
        )

    def _check_lookahead_bias(self, df: pd.DataFrame) -> LeakageCheckResult:
        """Check for common lookahead bias indicators."""
        suspicious_cols = []

        # Check for columns that might contain future data
        future_indicators = [
            'future_', 'next_', 'forward_', 'actual_return', 'realized_'
        ]

        for col in df.columns:
            col_lower = col.lower()
            for indicator in future_indicators:
                if indicator in col_lower:
                    # Check if this column is used as a feature (not target)
                    if col not in ['actual_return', 'forward_return']:
                        suspicious_cols.append(col)

        passed = len(suspicious_cols) == 0

        return LeakageCheckResult(
            check_name="Lookahead Bias Check",
            passed=passed,
            n_violations=len(suspicious_cols),
            violation_rate=len(suspicious_cols) / max(1, len(df.columns)),
            details=f"Suspicious columns: {suspicious_cols}"
            if not passed else "No obvious lookahead bias detected",
        )


# =============================================================================
# EXECUTION REALISM
# =============================================================================

class ExecutionRealism:
    """
    Applies realistic execution assumptions to return calculations.

    For long options:
    - Enter at ask price (pay the spread)
    - Exit at bid price (pay the spread again)

    For short options:
    - Enter at bid price (receive premium)
    - Exit at ask price (pay to close)
    """

    @staticmethod
    def calculate_realistic_return(
        entry_bid: float,
        entry_ask: float,
        exit_bid: float,
        exit_ask: float,
        side: str,
        position: str = "long",
    ) -> float:
        """
        Calculate return with realistic execution prices.

        Args:
            entry_bid: Bid price at entry
            entry_ask: Ask price at entry
            exit_bid: Bid price at exit
            exit_ask: Ask price at exit
            side: 'call' or 'put' (option type)
            position: 'long' or 'short'

        Returns:
            Realistic return accounting for bid-ask spread
        """
        if position == "long":
            # Long: buy at ask, sell at bid
            entry_price = entry_ask
            exit_price = exit_bid
        else:
            # Short: sell at bid, buy back at ask
            entry_price = entry_bid
            exit_price = exit_ask

        if entry_price <= 0:
            return 0.0

        if position == "long":
            return (exit_price - entry_price) / entry_price
        else:
            # Short profit when price goes down
            return (entry_price - exit_price) / entry_price

    @staticmethod
    def adjust_returns_for_execution(
        df: pd.DataFrame,
        entry_bid_col: str = "entry_bid",
        entry_ask_col: str = "entry_ask",
        exit_bid_col: str = "exit_bid",
        exit_ask_col: str = "exit_ask",
        position: str = "long",
    ) -> pd.Series:
        """
        Adjust all returns in DataFrame for execution realism.

        Returns:
            Series of realistic returns
        """
        realistic_returns = []

        for _, row in df.iterrows():
            ret = ExecutionRealism.calculate_realistic_return(
                entry_bid=row.get(entry_bid_col, 0),
                entry_ask=row.get(entry_ask_col, 0),
                exit_bid=row.get(exit_bid_col, 0),
                exit_ask=row.get(exit_ask_col, 0),
                side=row.get('side', 'call'),
                position=position,
            )
            realistic_returns.append(ret)

        return pd.Series(realistic_returns, index=df.index)

    @staticmethod
    def calculate_spread_cost(bid: float, ask: float) -> float:
        """Calculate the cost of the bid-ask spread as a percentage."""
        mid = (bid + ask) / 2
        if mid <= 0:
            return 0.0
        return (ask - bid) / mid


@dataclass
class RankingValidationResult:
    """Result of options ranking validation."""
    metric: str
    value: float
    p_value: float
    is_significant: bool
    confidence_interval: Tuple[float, float]
    interpretation: str
    n_samples: int = 0  # Sample size for the test
    
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
        hit_rate_warning_n_threshold: int = 200,
        low_std_warning_threshold: float = 0.01,
        min_days_threshold: int = 20,
    ):
        """
        Initialize validator.

        Args:
            confidence_level: Confidence level for statistical tests
            min_samples: Minimum samples for valid testing
            random_state: Random seed for reproducibility
            hit_rate_warning_n_threshold: Warn if hit_rate=1.0 with n < this
            low_std_warning_threshold: Warn if std_rank_ic < this
            min_days_threshold: Warn if n_days < this
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        self.min_samples = min_samples
        self.random_state = random_state
        self.hit_rate_warning_n_threshold = hit_rate_warning_n_threshold
        self.low_std_warning_threshold = low_std_warning_threshold
        self.min_days_threshold = min_days_threshold
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
            n_samples=n_total,
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

    # =========================================================================
    # PROPER IC CALCULATION WITH PER-DATE RANKING
    # =========================================================================

    def calculate_proper_ic(
        self,
        df: pd.DataFrame,
        date_col: str = "ranking_date",
        score_col: str = "ml_score",
        return_col: str = "forward_return",
        horizon: str = "1D",
        min_group_size: int = 25,
        random_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate IC properly with per-date ranking and forward returns.

        For each ranking date t:
        1. Take all contracts ranked on t
        2. Compute forward return over fixed horizon (next close, 1D, 3D)
        3. Compute Spearman (Rank IC) and Pearson (IC)

        Then report: mean IC, std, t-stat, bootstrap CI.

        Args:
            df: DataFrame with rankings and forward returns
            date_col: Column with ranking dates
            score_col: Column with ML scores
            return_col: Column with forward returns
            horizon: Return horizon label for reporting
            min_group_size: Minimum contracts per day (default 25)
            random_seed: Seed for bootstrap reproducibility

        Returns:
            Dict with IC statistics
        """
        # Set random seed for bootstrap reproducibility
        if random_seed is not None:
            np.random.seed(random_seed)

        if date_col not in df.columns:
            logger.warning(f"Date column '{date_col}' not found, using pooled IC")
            rank_corr, rank_p = stats.spearmanr(df[score_col], df[return_col])
            pearson_corr, pearson_p = stats.pearsonr(df[score_col], df[return_col])
            return {
                "mean_rank_ic": float(rank_corr),
                "mean_ic": float(pearson_corr),
                "std_rank_ic": 0.0,
                "std_ic": 0.0,
                "t_stat": float("inf") if rank_p < 0.001 else 0.0,
                "p_value": float(rank_p),
                "n_periods": 1,
                "n_days_skipped": 0,
                "pct_days_skipped": 0.0,
                "ci_lower": float(rank_corr),
                "ci_upper": float(rank_corr),
                "horizon": horizon,
            }

        # Calculate IC for each date
        daily_rank_ics = []  # Spearman (Rank IC)
        daily_pearson_ics = []  # Pearson (IC)
        contracts_per_day = []
        dates = df[date_col].unique()
        n_total_days = len(dates)
        n_skipped = 0

        for date in dates:
            day_df = df[df[date_col] == date]
            n_contracts = len(day_df)

            # Skip if below min_group_size
            if n_contracts < min_group_size:
                n_skipped += 1
                continue

            scores = day_df[score_col].values
            returns = day_df[return_col].values

            # Skip if no variance
            if np.std(scores) < 1e-10 or np.std(returns) < 1e-10:
                n_skipped += 1
                continue

            # Spearman (Rank IC)
            rank_corr, _ = stats.spearmanr(scores, returns)
            # Pearson (IC)
            pearson_corr, _ = stats.pearsonr(scores, returns)

            if np.isfinite(rank_corr):
                daily_rank_ics.append(rank_corr)
            if np.isfinite(pearson_corr):
                daily_pearson_ics.append(pearson_corr)

            contracts_per_day.append(n_contracts)

        pct_skipped = (n_skipped / n_total_days * 100) if n_total_days > 0 else 0

        if len(daily_rank_ics) < 3:
            return {
                "mean_rank_ic": 0.0,
                "mean_ic": 0.0,
                "std_rank_ic": 0.0,
                "std_ic": 0.0,
                "t_stat": 0.0,
                "p_value": 1.0,
                "n_periods": len(daily_rank_ics),
                "n_days_skipped": n_skipped,
                "pct_days_skipped": pct_skipped,
                "ci_lower": 0.0,
                "ci_upper": 0.0,
                "horizon": horizon,
                "error": "Insufficient periods for IC calculation",
            }

        daily_rank_ics = np.array(daily_rank_ics)
        daily_pearson_ics = np.array(daily_pearson_ics)

        mean_rank_ic = np.mean(daily_rank_ics)
        std_rank_ic = np.std(daily_rank_ics, ddof=1)
        mean_ic = np.mean(daily_pearson_ics)
        std_ic = np.std(daily_pearson_ics, ddof=1)
        n = len(daily_rank_ics)

        # T-statistic for Rank IC
        t_stat = mean_rank_ic / (std_rank_ic / np.sqrt(n)) if std_rank_ic > 0 else 0.0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))

        # Bootstrap CI by resampling the vector of daily_ics (not rows)
        n_bootstrap = 1000
        boot_rank_means = []
        boot_pearson_means = []
        for _ in range(n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            boot_rank_means.append(np.mean(daily_rank_ics[idx]))
            if len(daily_pearson_ics) > 0:
                boot_pearson_means.append(np.mean(daily_pearson_ics[idx]))

        ci_lower = np.percentile(boot_rank_means, 2.5)
        ci_upper = np.percentile(boot_rank_means, 97.5)
        ic_ci_lower = np.percentile(boot_pearson_means, 2.5) if boot_pearson_means else 0.0
        ic_ci_upper = np.percentile(boot_pearson_means, 97.5) if boot_pearson_means else 0.0

        # Contracts per day stats
        avg_contracts = np.mean(contracts_per_day) if contracts_per_day else 0
        min_contracts = min(contracts_per_day) if contracts_per_day else 0
        max_contracts = max(contracts_per_day) if contracts_per_day else 0

        return {
            "mean_rank_ic": float(mean_rank_ic),
            "mean_ic": float(mean_ic),
            "std_rank_ic": float(std_rank_ic),
            "std_ic": float(std_ic),
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "n_periods": n,
            "n_days_total": n_total_days,
            "n_days_skipped": n_skipped,
            "pct_days_skipped": float(pct_skipped),
            "avg_contracts_per_day": float(avg_contracts),
            "min_contracts_per_day": int(min_contracts),
            "max_contracts_per_day": int(max_contracts),
            "rank_ic_ci_lower": float(ci_lower),
            "rank_ic_ci_upper": float(ci_upper),
            "ic_ci_lower": float(ic_ci_lower),
            "ic_ci_upper": float(ic_ci_upper),
            "horizon": horizon,
            "min_group_size": min_group_size,
            "is_significant": p_value < self.alpha and mean_rank_ic > 0,
            "daily_rank_ics": daily_rank_ics.tolist(),
            "daily_ics": daily_pearson_ics.tolist(),
        }

    # =========================================================================
    # PERMUTATION TEST FOR LEAKAGE DETECTION
    # =========================================================================

    def run_permutation_test(
        self,
        df: pd.DataFrame,
        date_col: str = "ranking_date",
        score_col: str = "ml_score",
        return_col: str = "forward_return",
        n_permutations: int = 1000,
        min_group_size: int = 25,
        random_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run permutation test to detect data leakage.

        Permute forward_return within each ranking_date and recompute
        mean daily Rank IC each permutation (not pooled).
        IC should collapse near 0. If it doesn't, leakage is present.

        NOTE: For real data runs, use n_permutations >= 1000 for meaningful
        p-value resolution. With 100 permutations, the smallest attainable
        p-value is ~1/101 ≈ 0.0099, which is too coarse for production.

        Args:
            df: DataFrame with rankings and returns
            date_col: Column with ranking dates
            score_col: Column with ML scores
            return_col: Column with forward returns
            n_permutations: Number of permutations (default 1000, use >= 1000)
            min_group_size: Minimum contracts per day
            random_seed: Seed for reproducibility in CI/debugging

        Returns:
            Dict with permutation test results
        """
        # Set random seed for reproducibility
        if random_seed is not None:
            np.random.seed(random_seed)

        # Calculate actual IC (use Rank IC = Spearman)
        actual_ic_result = self.calculate_proper_ic(
            df, date_col, score_col, return_col, min_group_size=min_group_size
        )
        actual_ic = actual_ic_result["mean_rank_ic"]
        n_periods = actual_ic_result.get("n_periods", 0)

        # Run permutations - permute within each ranking_date
        permuted_ics = []
        count_extreme = 0  # Count permuted ICs >= actual IC

        for _ in range(n_permutations):
            df_perm = df.copy()

            # Shuffle forward_return within each ranking_date
            if date_col in df.columns:
                for date in df[date_col].unique():
                    mask = df_perm[date_col] == date
                    shuffled = df_perm.loc[mask, return_col].values.copy()
                    np.random.shuffle(shuffled)
                    df_perm.loc[mask, return_col] = shuffled
            else:
                # Shuffle all returns if no date column
                shuffled = df_perm[return_col].values.copy()
                np.random.shuffle(shuffled)
                df_perm[return_col] = shuffled

            # Recompute mean daily Rank IC on permuted data (not pooled)
            perm_result = self.calculate_proper_ic(
                df_perm, date_col, score_col, return_col,
                min_group_size=min_group_size
            )
            perm_ic = perm_result["mean_rank_ic"]
            permuted_ics.append(perm_ic)

            # Count extreme values for p-value
            if perm_ic >= actual_ic:
                count_extreme += 1

        permuted_ics = np.array(permuted_ics)

        # Correct p-value formula: (count_extreme + 1) / (n_permutations + 1)
        # This ensures p-value is never exactly 0
        p_value = (count_extreme + 1) / (n_permutations + 1)
        min_p = 1 / (n_permutations + 1)

        # Statistics
        mean_permuted = np.mean(permuted_ics)
        std_permuted = np.std(permuted_ics)

        # Z-score of actual IC vs permuted distribution
        z_score = (actual_ic - mean_permuted) / (std_permuted + 1e-10)

        # Leakage detection flags:
        # 1. If permuted IC is not near 0, there may be leakage
        permuted_not_near_zero = abs(mean_permuted) > 0.02

        # 2. If actual IC is > 3 std dev of permuted distribution (z-score)
        extreme_z_score = abs(z_score) > 3.0

        # 3. p-value < 0.001 with very small sample sizes is suspicious
        small_sample_extreme_p = p_value < 0.001 and n_periods < 10

        # Combined leakage flag
        leakage_suspected = (
            permuted_not_near_zero or
            (extreme_z_score and small_sample_extreme_p)
        )

        return {
            "actual_rank_ic": float(actual_ic),
            "mean_permuted_ic": float(mean_permuted),
            "std_permuted_ic": float(std_permuted),
            "z_score": float(z_score),
            "p_value": float(p_value),
            "min_p": float(min_p),
            "count_extreme": count_extreme,
            "n_permutations": n_permutations,
            "n_periods": n_periods,
            "random_seed": random_seed,
            "leakage_suspected": leakage_suspected,
            "leakage_flags": {
                "permuted_not_near_zero": permuted_not_near_zero,
                "extreme_z_score": extreme_z_score,
                "small_sample_extreme_p": small_sample_extreme_p,
            },
            "is_significant": p_value < self.alpha,
            "interpretation": self._interpret_permutation_test(
                actual_ic, mean_permuted, z_score, p_value,
                leakage_suspected, n_periods
            ),
        }

    def _interpret_permutation_test(
        self,
        actual_ic: float,
        mean_permuted: float,
        z_score: float,
        p_value: float,
        leakage_suspected: bool,
        n_periods: int,
    ) -> str:
        """Interpret permutation test results."""
        if leakage_suspected:
            return (
                f"⚠️ LEAKAGE SUSPECTED: Permuted IC ({mean_permuted:.4f}) "
                f"not near 0, or extreme z-score ({z_score:.2f}) with "
                f"small sample (n={n_periods}). Check feature/label timing."
            )

        if p_value < 0.05:
            return (
                f"✅ NO LEAKAGE: Actual IC ({actual_ic:.4f}) significantly "
                f"higher than permuted ({mean_permuted:.4f}), "
                f"z={z_score:.2f}, p={p_value:.4f}"
            )
        else:
            return (
                f"❌ IC NOT SIGNIFICANT: Actual IC ({actual_ic:.4f}) not "
                f"different from random (p={p_value:.4f}, z={z_score:.2f})"
            )

    def generate_report(
        self,
        validation_results: List[RankingValidationResult],
        distribution_stats: Optional[Dict[str, Any]] = None,
        ic_stats: Optional[Dict[str, Any]] = None,
        permutation_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a comprehensive validation report."""
        lines = [
            "=" * 60,
            "OPTIONS RANKING VALIDATION REPORT",
            "=" * 60,
            f"Confidence Level: {self.confidence_level * 100:.0f}%",
            "",
        ]

        # Collect warnings for Data Sufficiency block
        data_warnings = []
        insufficient_days = False  # Track if we should suppress significance

        # Check hit rate warnings from validation results
        top_quantile_n = 0
        total_samples_all = len(validation_results) if validation_results else 0
        for result in validation_results:
            if "Hit Rate" in result.metric:
                top_quantile_n = result.n_samples
                if result.value == 1.0 and result.n_samples < self.hit_rate_warning_n_threshold:
                    data_warnings.append(
                        f"⚠️ 100% hit rate with n={result.n_samples} "
                        f"(threshold={self.hit_rate_warning_n_threshold}) - "
                        "likely sample-size artifact"
                    )

        # Extract IC stats for Data Sufficiency block
        n_days = ic_stats.get('n_periods', 0) if ic_stats else 0
        n_days_total = ic_stats.get('n_days_total', 0) if ic_stats else 0
        pct_skip = ic_stats.get('pct_days_skipped', 0) if ic_stats else 0
        avg_c = ic_stats.get('avg_contracts_per_day', 0) if ic_stats else 0
        min_c = ic_stats.get('min_contracts_per_day', 0) if ic_stats else 0
        max_c = ic_stats.get('max_contracts_per_day', 0) if ic_stats else 0
        std_rank_ic = ic_stats.get('std_rank_ic', 0) if ic_stats else 0
        total_samples = int(n_days * avg_c) if ic_stats else total_samples_all

        # Check for low n_days - this is a hard warning that affects significance
        if n_days < self.min_days_threshold:
            insufficient_days = True
            data_warnings.append(
                f"⚠️ n_days={n_days} < {self.min_days_threshold} - "
                "SIGNIFICANCE NOT ASSESSED (insufficient days). "
                "Increase sample window to at least 60 days (prefer 120)."
            )

        # Check for low std_rank_ic (synthetic/degenerate data)
        if ic_stats and std_rank_ic < self.low_std_warning_threshold:
            data_warnings.append(
                f"⚠️ std_rank_ic={std_rank_ic:.4f} < {self.low_std_warning_threshold} - "
                "results may be synthetic/degenerate"
            )

        # === DATA SUFFICIENCY BLOCK (first, so users can't miss it) ===
        lines.append("--- Data Sufficiency ---")
        lines.append(f"  n_days: {n_days} (of {n_days_total} total)")
        lines.append(f"  top_quantile_n: {top_quantile_n}")
        lines.append(f"  total_samples_all_contracts: {total_samples}")
        lines.append(f"  avg_contracts_per_day: {avg_c:.1f}")
        lines.append(f"  min/max contracts per day: {min_c} / {max_c}")
        lines.append(f"  % days skipped: {pct_skip:.1f}%")
        if data_warnings:
            lines.append("")
            lines.append("  WARNINGS:")
            for w in data_warnings:
                lines.append(f"    {w}")
        else:
            lines.append("  ✅ No data sufficiency warnings")

        # === STATISTICAL TESTS ===
        lines.append("\n--- Statistical Tests ---")
        n_significant = 0
        for result in validation_results:
            lines.append(str(result))
            if result.is_significant:
                n_significant += 1

        # === IC ANALYSIS ===
        if ic_stats:
            lines.append("\n--- IC Analysis ---")
            lines.append(f"  Horizon: {ic_stats.get('horizon', 'N/A')}")
            lines.append(f"  Min Group Size: {ic_stats.get('min_group_size', 25)}")
            lines.append("")
            rank_ic = ic_stats.get('mean_rank_ic', 0)
            ic = ic_stats.get('mean_ic', 0)
            std_ic = ic_stats.get('std_ic', 0)
            lines.append(f"  Rank IC (Spearman): {rank_ic:.4f} "
                         f"± {std_rank_ic:.4f} (std)")
            lines.append(f"    CI: [{ic_stats.get('rank_ic_ci_lower', 0):.4f}, "
                         f"{ic_stats.get('rank_ic_ci_upper', 0):.4f}]")
            lines.append(f"  IC (Pearson): {ic:.4f} ± {std_ic:.4f} (std)")
            lines.append(f"    CI: [{ic_stats.get('ic_ci_lower', 0):.4f}, "
                         f"{ic_stats.get('ic_ci_upper', 0):.4f}]")
            lines.append(f"  t-stat: {ic_stats.get('t_stat', 0):.2f} "
                         f"(df={n_days - 1}), "
                         f"p-value: {ic_stats.get('p_value', 1):.4f}")
            # Suppress significance if insufficient days
            if insufficient_days:
                lines.append("  ⚠️ Significant: NOT ASSESSED (insufficient days)")
            else:
                sig = "✅" if ic_stats.get('is_significant', False) else "❌"
                lines.append(f"  {sig} Significant: {ic_stats.get('is_significant')}")

        # Permutation test results
        if permutation_stats:
            lines.append("\n--- Permutation Test ---")
            lines.append(f"  n_permutations: {permutation_stats.get('n_permutations')}")
            lines.append(f"  Actual Rank IC: "
                         f"{permutation_stats.get('actual_rank_ic', 0):.4f}")
            lines.append(f"  Mean Permuted IC: "
                         f"{permutation_stats.get('mean_permuted_ic', 0):.4f}")
            lines.append(f"  Std Permuted IC: "
                         f"{permutation_stats.get('std_permuted_ic', 0):.4f}")
            lines.append(f"  Z-score: {permutation_stats.get('z_score', 0):.2f}")
            lines.append(f"  P-value: {permutation_stats.get('p_value', 1):.4f}")
            leak = permutation_stats.get('leakage_suspected', False)
            leak_icon = "⚠️" if leak else "✅"
            lines.append(f"  {leak_icon} Leakage Suspected: {leak}")
            lines.append(f"  {permutation_stats.get('interpretation', '')}")

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
