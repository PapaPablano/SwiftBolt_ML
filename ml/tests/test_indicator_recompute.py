"""
Unit tests for L1 indicator recompute (Option B).

Validates attach_indicators_to_forecast_points and recompute_indicators_on_series:
- Points get ohlc and indicators when history + predicted points are provided
- value == ohlc.close; ohlc has open, high, low, close, volume
- At least one indicator (e.g. rsi_14) present when enough history
"""

import numpy as np
import pandas as pd
import pytest

from src.features.indicator_recompute import (
    attach_indicators_to_forecast_points,
    recompute_indicators_on_series,
)


def _make_history_bars(n: int = 100, base_price: float = 100.0) -> pd.DataFrame:
    """History DataFrame with open, high, low, close."""
    np.random.seed(42)
    close = base_price + np.cumsum(np.random.randn(n) * 0.5)
    open_ = np.roll(close, 1)
    open_[0] = base_price
    high = np.maximum(open_, close) + np.abs(np.random.randn(n)) * 0.1
    low = np.minimum(open_, close) - np.abs(np.random.randn(n)) * 0.1
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_attach_indicators_returns_ohlc_and_indicators():
    """attach_indicators_to_forecast_points adds ohlc and indicators to each point."""
    history = _make_history_bars(100)
    points = [
        {"ts": 1738929600, "value": 101.0, "lower": 99.0, "upper": 103.0},
        {"ts": 1738933200, "value": 102.0, "lower": 100.0, "upper": 104.0},
    ]
    out = attach_indicators_to_forecast_points(history, points)
    assert len(out) == 2
    for i, p in enumerate(out):
        assert "ohlc" in p
        assert p["ohlc"]["close"] == points[i]["value"]
        assert set(p["ohlc"].keys()) >= {"open", "high", "low", "close", "volume"}
        assert p["ohlc"]["open"] <= p["ohlc"]["high"] and p["ohlc"]["low"] <= p["ohlc"]["close"]
        assert "indicators" in p
        # RSI/MACD/BB/KDJ should be present after 100 bars
        assert "rsi_14" in p["indicators"] or "macd" in p["indicators"] or "bb_upper" in p["indicators"]
    assert out[0]["value"] == 101.0 and out[1]["value"] == 102.0


def test_attach_indicators_empty_points():
    """Empty points returns empty list."""
    history = _make_history_bars(50)
    assert attach_indicators_to_forecast_points(history, []) == []


def test_attach_indicators_preserves_existing_keys():
    """Existing keys (ts, value, lower, upper) are preserved."""
    history = _make_history_bars(80)
    points = [{"ts": 1738929600, "value": 100.5, "lower": 98.0, "upper": 102.0}]
    out = attach_indicators_to_forecast_points(history, points)
    assert len(out) == 1
    assert out[0]["ts"] == 1738929600
    assert out[0]["value"] == 100.5
    assert out[0]["lower"] == 98.0
    assert out[0]["upper"] == 102.0
    assert "ohlc" in out[0] and "indicators" in out[0]


def test_recompute_indicators_on_series_adds_columns():
    """recompute_indicators_on_series adds rsi_14, macd, bb_*, kdj_* columns."""
    df = _make_history_bars(50)
    out = recompute_indicators_on_series(df)
    assert "rsi_14" in out.columns
    assert "macd" in out.columns
    assert "bb_upper" in out.columns and "bb_middle" in out.columns and "bb_lower" in out.columns
    assert "kdj_k" in out.columns and "kdj_d" in out.columns and "kdj_j" in out.columns
    # Last row should have non-NaN after enough lookback
    assert pd.notna(out["rsi_14"].iloc[-1])
