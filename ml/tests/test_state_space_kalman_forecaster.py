"""Unit tests for StateSpaceKalmanForecaster and _probabilities_from_forecast."""

import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.modules["config.settings"] = MagicMock()

from src.models.state_space_kalman_forecaster import (  # noqa: E402
    StateSpaceKalmanForecaster,
    _probabilities_from_forecast,
)


def _assert_valid_probs(probs: dict) -> None:
    """Assert probabilities sum to 1 and are in [0, 1]."""
    assert abs(sum(probs.values()) - 1.0) < 1e-6, f"probs sum={sum(probs.values())}"
    assert all(0 <= p <= 1 for p in probs.values()), f"probs out of range: {probs}"


class TestProbabilitiesFromForecast:
    """Tests for _probabilities_from_forecast (CDF-based, no scipy)."""

    def test_probs_sum_and_bounds_nominal(self) -> None:
        """Nominal case: mean=0, std=0.01, symmetric thresholds."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.0,
            forecast_std=0.01,
            bull_thresh=0.002,
            bear_thresh=-0.002,
        )
        _assert_valid_probs(probs)

    def test_probs_sum_and_bounds_tiny_std(self) -> None:
        """Edge case: very small std (clamped to 0.01 internally)."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.001,
            forecast_std=1e-10,
            bull_thresh=0.002,
            bear_thresh=-0.002,
        )
        _assert_valid_probs(probs)

    def test_probs_sum_and_bounds_extreme_thresholds(self) -> None:
        """Edge case: tight thresholds (mean=0, std=0.001) can push raw probs outside [0,1]."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.0,
            forecast_std=0.001,
            bull_thresh=0.001,
            bear_thresh=-0.001,
        )
        _assert_valid_probs(probs)

    def test_probs_sum_and_bounds_stress_clamp(self) -> None:
        """Stress case: extreme thresholds + tiny std to really exercise clamp/normalization."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.0,
            forecast_std=1e-6,
            bull_thresh=0.05,
            bear_thresh=-0.05,
        )
        _assert_valid_probs(probs)

    def test_probs_sum_and_bounds_zero_std(self) -> None:
        """Edge case: zero std is clamped."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.0,
            forecast_std=0.0,
            bull_thresh=0.002,
            bear_thresh=-0.002,
        )
        _assert_valid_probs(probs)

    def test_probs_sum_and_bounds_strong_bullish(self) -> None:
        """High mean, low variance -> mostly bullish."""
        probs = _probabilities_from_forecast(
            forecast_mean=0.005,
            forecast_std=0.001,
            bull_thresh=0.002,
            bear_thresh=-0.002,
        )
        _assert_valid_probs(probs)
        assert probs["bullish"] > probs["bearish"]

    def test_probs_sum_and_bounds_strong_bearish(self) -> None:
        """Low mean, low variance -> mostly bearish."""
        probs = _probabilities_from_forecast(
            forecast_mean=-0.005,
            forecast_std=0.001,
            bull_thresh=0.002,
            bear_thresh=-0.002,
        )
        _assert_valid_probs(probs)
        assert probs["bearish"] > probs["bullish"]
