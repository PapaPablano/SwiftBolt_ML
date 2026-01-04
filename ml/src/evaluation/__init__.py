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

# Option B Forecast Accuracy Framework
from ..forecast_validator import (
    ForecastOutcome,
    ForecastEvaluation,
    ForecastAccuracySummary,
    evaluate_single_forecast,
    summarize_forecast_accuracy,
    evaluate_forecast_batch,
    get_tolerance_for_horizon,
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
    # Option B Forecast Accuracy Framework
    "ForecastOutcome",
    "ForecastEvaluation",
    "ForecastAccuracySummary",
    "evaluate_single_forecast",
    "summarize_forecast_accuracy",
    "evaluate_forecast_batch",
    "get_tolerance_for_horizon",
]
