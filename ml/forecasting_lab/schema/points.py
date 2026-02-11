"""
Canonical ForecastPoint schema for ml_forecasts.points and ml_forecasts_intraday.points.

Maps OHLCStep (+ indicator bundle) to the blueprint contract so the lab, ML job, Edge, and SwiftUI
share the same shape. Required: ts, value. Optional: lower, upper, timeframe, step, ohlc,
indicators, confidence, components, weights (see docs/master_blueprint.md).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from forecasting_lab.features.indicators import INDICATOR_KEYS
except ImportError:
    INDICATOR_KEYS = [
        "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_mid", "bb_lower",
        "kdj_k", "kdj_d", "kdj_j",
    ]


def _ts_iso(ts: datetime) -> str:
    """Return ISO 8601 string; ensure UTC."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


def ohlc_steps_to_points(
    ohlc_steps: list[dict[str, Any]],
    timeframe: str,
    last_ts: datetime | str | None = None,
    step_start: int = 1,
    step_duration_minutes: int | None = None,
) -> list[dict[str, Any]]:
    """
    Convert a list of OHLCStep (lab predict output) to canonical ForecastPoint array.

    Each point has required ts, value and optional ohlc, indicators, step, timeframe.
    Non-ensemble models do not set confidence, components, weights; callers can add them.

    Args:
        ohlc_steps: List of dicts with open, high, low, close, volume?, and optional indicator keys.
        timeframe: One of m15, h1, 4h_trading, d1, w1.
        last_ts: Timestamp of last known bar (start of forecast = last_ts + 1 bar). If None, ts uses step index only (no real time).
        step_start: 1-based step index for first step (default 1).
        step_duration_minutes: Minutes per step. Default: m15=15, h1=60, 4h_trading=240, d1=1440, w1=10080.

    Returns:
        List of ForecastPoint dicts suitable for JSONB points array.
    """
    if not ohlc_steps:
        return []
    duration = step_duration_minutes
    if duration is None:
        duration = {"m15": 15, "h1": 60, "4h_trading": 240, "d1": 1440, "w1": 10080}.get(timeframe, 15)
    if last_ts is not None:
        if isinstance(last_ts, str):
            last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
    points = []
    for i, step in enumerate(ohlc_steps):
        close = float(step.get("close", 0))
        if last_ts is not None:
            ts_dt = last_ts + timedelta(minutes=duration * (i + 1))
            ts_str = _ts_iso(ts_dt)
        else:
            ts_str = ""  # Caller should set last_ts when persisting to ml_forecasts_intraday
        pt: dict[str, Any] = {"ts": ts_str, "value": close, "timeframe": timeframe, "step": step_start + i}
        ohlc = {
            "open": float(step.get("open", close)),
            "high": float(step.get("high", close)),
            "low": float(step.get("low", close)),
            "close": close,
            "volume": float(step.get("volume", 0)),
        }
        pt["ohlc"] = ohlc
        indicators = {k: float(step[k]) for k in INDICATOR_KEYS if k in step and step[k] is not None}
        if indicators:
            if "kdj_k" in indicators and "kdj_d" in indicators:
                j = indicators.get("kdj_j")
                d = indicators.get("kdj_d")
                if j is not None and d is not None:
                    indicators["j_minus_d"] = round(j - d, 4)
                    indicators["j_above_d"] = 1 if j > d else 0
            pt["indicators"] = indicators
        if "lower" in step:
            pt["lower"] = float(step["lower"])
        if "upper" in step:
            pt["upper"] = float(step["upper"])
        if "confidence" in step:
            pt["confidence"] = float(step["confidence"])
        if "components" in step:
            pt["components"] = dict(step["components"])
        if "weights" in step:
            pt["weights"] = dict(step["weights"])
        points.append(pt)
    return points
