"""
Unit tests for canonical intraday ForecastPoint shape (Option A).

Validates that canonicalize_intraday_points produces storage-ready points:
- ts is ISO 8601 string (UTC), not unix int
- step is 1-based
- timeframe is present (m15/h1/h4)
- value, lower, upper unchanged (no model math change)

Also asserts short-points path anchor removal: first stored point is strictly
in the future vs current bar time (so the anchor at i=0 is not persisted).
"""

import re
from datetime import datetime

import pytest

from src.intraday_forecast_job import (
    build_intraday_short_points,
    canonicalize_intraday_points,
)


def test_writer_emits_canonical_points():
    """Writer emits canonical points: ts ISO string, step 1-based, timeframe present."""
    raw = [
        {"ts": 1738929600, "value": 100.0, "lower": 98.0, "upper": 102.0},
        {"ts": 1738933200, "value": 101.0, "lower": 99.0, "upper": 103.0},
    ]
    out = canonicalize_intraday_points(raw, "m15")
    assert len(out) == 2
    # ts must be ISO 8601 string (not unix int)
    for p in out:
        assert isinstance(p["ts"], str), "ts must be string"
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", p["ts"]), "ts must be ISO 8601 UTC"
    # step 1-based
    assert out[0]["step"] == 1
    assert out[1]["step"] == 2
    # timeframe present
    assert out[0]["timeframe"] == "m15"
    assert out[1]["timeframe"] == "m15"
    # value, lower, upper unchanged
    assert out[0]["value"] == 100.0 and out[0]["lower"] == 98.0 and out[0]["upper"] == 102.0
    assert out[1]["value"] == 101.0 and out[1]["lower"] == 99.0 and out[1]["upper"] == 103.0


def test_canonicalize_empty_list():
    """Empty input returns empty list."""
    assert canonicalize_intraday_points([], "h1") == []


def test_canonicalize_timeframe_tokens():
    """timeframe m15, h1, h4 are passed through."""
    raw = [{"ts": 1738929600, "value": 1.0, "lower": 0.9, "upper": 1.1}]
    for tf in ("m15", "h1", "h4"):
        out = canonicalize_intraday_points(raw, tf)
        assert out[0]["timeframe"] == tf


def test_canonicalize_ts_string_normalized_to_utc_iso():
    """When ts is already a string, it is parsed and re-emitted as YYYY-MM-DDTHH:MM:SSZ (UTC)."""
    raw = [
        {"ts": "2026-02-10T15:30:00Z", "value": 100.0, "lower": 98.0, "upper": 102.0},
        {"ts": "2026-02-10T10:00:00-05:00", "value": 101.0, "lower": 99.0, "upper": 103.0},
    ]
    out = canonicalize_intraday_points(raw, "m15")
    assert len(out) == 2
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", out[0]["ts"])
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", out[1]["ts"])
    assert out[0]["ts"] == "2026-02-10T15:30:00Z"
    # Second was -05:00 -> UTC
    assert out[1]["ts"] == "2026-02-10T15:00:00Z"


def test_short_points_anchor_not_persisted_first_point_in_future():
    """
    Short-points write path must slice off the anchor before persist.
    After slice + canonicalize, the first stored point's ts must be strictly
    after the current bar time (base_ts_sec), so the anchor was not persisted.
    """
    base_ts_sec = 1738929600  # current bar open (e.g. 15m bar)
    interval_sec = 900  # 15m
    steps = 3
    short_points = build_intraday_short_points(
        base_ts_sec=base_ts_sec,
        interval_sec=interval_sec,
        steps=steps,
        current_price=100.0,
        target_price=102.0,
        confidence=0.7,
    )
    assert len(short_points) == steps + 1  # anchor at i=0 + 3 future
    assert short_points[0]["ts"] == base_ts_sec  # anchor = current bar

    # Same logic as job: slice off anchor before canonicalize
    short_points_future = short_points[1:] if len(short_points) > 1 else []
    stored = canonicalize_intraday_points(short_points_future, "m15")

    assert len(stored) == steps, "only future points stored"
    assert stored[0]["step"] == 1 and stored[1]["step"] == 2 and stored[2]["step"] == 3

    # First stored point must be strictly in the future vs current bar time
    first_ts_str = stored[0]["ts"]
    assert isinstance(first_ts_str, str)
    dt = datetime.fromisoformat(first_ts_str.replace("Z", "+00:00"))
    first_ts_sec = int(dt.timestamp())
    assert first_ts_sec > base_ts_sec, (
        "first stored point must be strictly after current bar (anchor removed); "
        f"got first_ts_sec={first_ts_sec}, base_ts_sec={base_ts_sec}"
    )
    assert first_ts_sec == base_ts_sec + interval_sec, (
        "first stored point should be base_ts_sec + interval_sec (first future bar)"
    )
