"""Utilities to detect look-ahead bias in feature engineering."""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from src.features.temporal_indicators import compute_simplified_features

logger = logging.getLogger(__name__)


class LookaheadViolation(RuntimeError):
    """Raised when a guard detects look-ahead bias."""


def _build_synthetic_ohlc(length: int = 260) -> pd.DataFrame:
    """Create a deterministic OHLCV frame with monotonic structure."""
    if length < 10:
        length = 10
    start = pd.Timestamp("2020-01-01")
    dates = pd.date_range(start, periods=length, freq="B")
    base = np.arange(length, dtype=float)
    df = pd.DataFrame(
        {
            "ts": dates,
            "open": 100 + base * 0.5,
            "high": 100.5 + base * 0.5,
            "low": 99.5 + base * 0.5,
            "close": 100 + base * 0.5,
            "volume": 1_000_000 + base * 100,
        }
    )
    return df


def _assert_frames_equal(lhs: pd.DataFrame, rhs: pd.DataFrame, context: str) -> None:
    """Compare frames with tolerance and raise descriptive violation."""
    try:
        assert_frame_equal(lhs, rhs, check_dtype=False, check_like=False, atol=1e-9, rtol=1e-9)
    except AssertionError as exc:
        raise LookaheadViolation(f"{context} mismatch detected") from exc


def run_synthetic_feature_guard(length: int = 260) -> None:
    """
    Ensure that changing future rows has zero effect on historical features.

    Builds a synthetic OHLC frame, mutates the final window, and compares
    the resulting feature matrix (excluding the mutated rows).
    """
    df = _build_synthetic_ohlc(length)
    baseline = compute_simplified_features(df)

    mutated = df.copy()
    # Zero out the final 3 rows to simulate extreme revisions.
    tail = 3
    mutated.loc[df.index[-tail:], ["open", "high", "low", "close"]] = 0.0
    mutated.loc[df.index[-tail:], "volume"] = 0.0
    mutated_features = compute_simplified_features(mutated)

    lhs = baseline.iloc[:-tail].reset_index(drop=True)
    rhs = mutated_features.iloc[:-tail].reset_index(drop=True)
    _assert_frames_equal(lhs, rhs, context="synthetic_future_mutation")


def assert_truncation_stable(
    df: pd.DataFrame,
    *,
    sentiment_series: pd.Series | None = None,
) -> None:
    """
    Recompute features after dropping the last bar and ensure earlier rows match.
    """
    if df is None or len(df) < 3:
        return

    baseline = compute_simplified_features(df, sentiment_series=sentiment_series)
    truncated = compute_simplified_features(df.iloc[:-1], sentiment_series=sentiment_series)

    lhs = baseline.iloc[:-1].reset_index(drop=True)
    rhs = truncated.reset_index(drop=True)
    _assert_frames_equal(lhs, rhs, context="truncation_guard")


def assert_label_gap(df: pd.DataFrame, feature_idx: int, horizon_bars: int) -> None:
    """
    Validate that the label reference is at least `horizon_bars` ahead of feature_idx.
    """
    if horizon_bars <= 0:
        raise LookaheadViolation("Horizon must be >= 1 for label gap validation")

    target_idx = feature_idx + horizon_bars
    if target_idx >= len(df):
        raise LookaheadViolation(
            f"Label index {target_idx} exceeds dataframe length {len(df)} (feature_idx={feature_idx})"
        )

    ts_col = None
    if "ts" in df.columns:
        ts_col = pd.to_datetime(df["ts"], errors="coerce")
    elif "date" in df.columns:
        ts_col = pd.to_datetime(df["date"], errors="coerce")

    if ts_col is not None and ts_col.notna().all():
        feature_ts = ts_col.iloc[feature_idx]
        label_ts = ts_col.iloc[target_idx]
        if label_ts <= feature_ts:
            raise LookaheadViolation(
                f"Label timestamp {label_ts} is not ahead of feature timestamp {feature_ts}"
            )


__all__ = [
    "LookaheadViolation",
    "assert_label_gap",
    "assert_truncation_stable",
    "run_synthetic_feature_guard",
]
