"""Monitoring utilities for ML models and data pipelines."""

from .drift_detector import DriftDetector, DriftResult


# Lazy import for forecast_staleness to avoid supabase dependency in tests
def check_forecast_staleness(*args, **kwargs):
    """Check if ML forecasts are stale. Lazy import wrapper."""
    from .forecast_staleness import check_forecast_staleness as _check
    return _check(*args, **kwargs)


__all__ = [
    "DriftDetector",
    "DriftResult",
    "check_forecast_staleness",
]
