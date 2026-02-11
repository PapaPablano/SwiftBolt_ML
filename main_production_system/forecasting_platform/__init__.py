"""
Forecasting Platform Module

Multi-timeframe directional forecasting with regime-aware confidence scoring.

This module provides:
- Multi-timeframe forecaster with wave analogy strategy
- Terminal dashboard for real-time forecasts
- Alert system for high confidence signals
- Accuracy tracking and reporting

Usage:
    from main_production_system.forecasting_platform import Forecaster
    from main_production_system.forecasting_platform import forecast_dashboard
    from main_production_system.forecasting_platform import forecast_alerts
"""

from .multi_timeframe_forecaster import Forecaster

__version__ = "1.0.0"
__author__ = "Your Trading Edge"

__all__ = [
    'Forecaster',
]
