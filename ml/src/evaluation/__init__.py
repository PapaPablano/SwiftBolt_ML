"""Evaluation and validation modules for ML models."""

# Option B Forecast Accuracy Framework
from ..forecast_validator import (
    ForecastAccuracySummary,
    ForecastEvaluation,
    ForecastOutcome,
    evaluate_forecast_batch,
    evaluate_single_forecast,
    get_tolerance_for_horizon,
    summarize_forecast_accuracy,
)
from .options_ranking_validation import (
    ExecutionRealism,
    LeakageCheckResult,
    LeakageDetector,
    OptionsRankingValidator,
    RankingValidationResult,
    validate_options_ranking,
)
from .statistical_tests import (
    ConfidenceInterval,
    HypothesisTestResult,
    StatisticalSignificanceTester,
    validate_model_significance,
)
from .walk_forward_cv import WalkForwardCV, directional_accuracy

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
