"""Evaluation and validation modules for ML models."""

from .walk_forward_cv import WalkForwardCV, directional_accuracy
from .statistical_tests import (
    StatisticalSignificanceTester,
    ConfidenceInterval,
    HypothesisTestResult,
    validate_model_significance,
)
from .options_ranking_validation import (
    OptionsRankingValidator,
    RankingValidationResult,
    validate_options_ranking,
    LeakageDetector,
    LeakageCheckResult,
    ExecutionRealism,
)

__all__ = [
    # Walk-forward CV
    "WalkForwardCV",
    "directional_accuracy",
    # Statistical significance for forecasting
    "StatisticalSignificanceTester",
    "ConfidenceInterval",
    "HypothesisTestResult",
    "validate_model_significance",
    # Options ranking validation
    "OptionsRankingValidator",
    "RankingValidationResult",
    "validate_options_ranking",
    # Leakage detection and execution realism
    "LeakageDetector",
    "LeakageCheckResult",
    "ExecutionRealism",
]
