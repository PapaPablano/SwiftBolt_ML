"""Monitoring utilities for ML models and data pipelines."""

from .confidence_calibrator import CalibrationResult, ConfidenceCalibrator
from .drift_detector import DriftDetector, DriftResult
from .forecast_validator import ForecastValidator, ValidationMetrics
from .price_monitor import PriceMonitor, RefreshTrigger, check_price_triggers


# Lazy import for forecast_staleness to avoid supabase dependency in tests
def check_forecast_staleness(*args, **kwargs):
    """Check if ML forecasts are stale. Lazy import wrapper."""
    from .forecast_staleness import check_forecast_staleness as _check

    return _check(*args, **kwargs)


__all__ = [
    "DriftDetector",
    "DriftResult",
    "ConfidenceCalibrator",
    "CalibrationResult",
    "PriceMonitor",
    "RefreshTrigger",
    "ForecastValidator",
    "ValidationMetrics",
    "check_forecast_staleness",
    "check_price_triggers",
]
