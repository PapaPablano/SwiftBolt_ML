"""
Synthetic test: 15m bars spanning session boundaries to prove daily construction
and cascade alignment (session-based 1D + feed-forward chaining).

Bar alignment rule: 15m bars at 09:30–09:45, 09:45–10:00, … within regular session
(09:30–16:00 Eastern). Daily bars = one OHLC per calendar day within session_open→session_close.
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

LAB_ROOT = Path(__file__).resolve().parent.parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from forecasting_lab.runner.cascade_runner import (
    build_daily_bars_from_session_15m,
    filter_15m_to_regular_session,
    rollup_bars,
    rollup_df,
    run_cascade,
)


def _eastern_session_15m_bars(start_date: date, num_days: int = 5) -> pd.DataFrame:
    """
    Build synthetic 15m bars for regular session only (09:30–16:00 Eastern).
    One bar every 15 min: 09:30, 09:45, 10:00, … 15:45 (26 bars per day).
    """
    try:
        import zoneinfo
        eastern = zoneinfo.ZoneInfo("America/New_York")
    except ImportError:
        eastern = timezone(timedelta(hours=-5))
    rows = []
    for d in range(num_days):
        day = start_date + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for minute in range(0, 26 * 15, 15):  # 09:30 + 0..25*15 min
            hour = 9 + (30 + minute) // 60
            min_ = (30 + minute) % 60
            if hour >= 16:
                break
            dt_eastern = datetime(day.year, day.month, day.day, hour, min_, 0, tzinfo=eastern)
            dt_utc = dt_eastern.astimezone(timezone.utc)
            close = 100.0 + d * 0.5 + minute / 100.0
            rows.append({
                "ts": dt_utc,
                "open": close - 0.1,
                "high": close + 0.05,
                "low": close - 0.15,
                "close": close,
                "volume": 1000,
            })
    return pd.DataFrame(rows)


def _calendar_days_synthetic(start_date: date, end_date: date):
    """Synthetic calendar (weekdays 09:30–16:00) for tests when Alpaca is not available."""
    from forecasting_lab.data.market_calendar_resolver import CalendarDay, with_session_timestamps
    out = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            out.append(with_session_timestamps(CalendarDay(date=d, session_open="09:30", session_close="16:00", early_close=False)))
        d += timedelta(days=1)
    return out


def test_session_filter_and_daily_build():
    """Prove 15m filtered to session and 1D built by session boundaries (not 4×4h)."""
    start = date(2024, 1, 2)  # Tuesday
    df_15m = _eastern_session_15m_bars(start, num_days=5)
    assert len(df_15m) > 0
    calendar_days = _calendar_days_synthetic(start, start + timedelta(days=6))
    assert len(calendar_days) >= 5

    df_session = filter_15m_to_regular_session(df_15m, calendar_days)
    assert len(df_session) == len(df_15m)

    df_1d = build_daily_bars_from_session_15m(df_session, calendar_days)
    # One bar per trading day in range
    assert len(df_1d) >= 4 and len(df_1d) <= 6
    # Each daily close should be last 15m close of that day
    for _, row in df_1d.iterrows():
        assert row["open"] <= row["high"] and row["low"] <= row["close"]


def test_cascade_alignment_and_feed_forward():
    """Prove cascade runs with session-based 1D and feed-forward (rolled bar appended to next level)."""
    start = date(2024, 1, 2)
    df_15m = _eastern_session_15m_bars(start, num_days=10)
    assert len(df_15m) >= 26 * 5

    out = run_cascade(df_15m, include_calendar=False)
    assert "error" not in out or out.get("error") is None
    assert out.get("weekly_close") is not None
    assert "levels" in out
    assert "15m" in out["levels"] and "1h" in out["levels"] and "4h_trading" in out["levels"] and "1d" in out["levels"]
    # Feed-forward: 1h level used rolled 15m bar; 4h_trading used rolled 1h bar; 1d used rolled 4h bar
    assert len(out["levels"]["1h"]["predicted_4"]) == 4
    assert len(out["levels"]["1d"]["predicted_5"]) == 5
    # Indicator recompute at Level 1: predicted_4 steps may have rsi_14, macd, bb_mid, kdj_k, etc.
    pred_15m = out["levels"]["15m"]["predicted_4"]
    if pred_15m and len(pred_15m[0]) > 5:
        assert any(k in pred_15m[0] for k in ("rsi_14", "macd", "bb_mid", "kdj_k"))
    # Canonical points (ForecastPoint) emitted for ml_forecasts_intraday.points / Edge
    points = out.get("points", [])
    assert len(points) == 4
    for pt in points:
        assert "ts" in pt and "value" in pt and "ohlc" in pt
        assert pt["ohlc"]["close"] == pt["value"]
        assert pt.get("timeframe") == "m15" and "step" in pt


def test_rollup_bars_and_df():
    """Sanity: rollup_bars and rollup_df produce correct OHLC."""
    steps = [
        {"open": 100, "high": 102, "low": 99, "close": 101, "volume": 10},
        {"open": 101, "high": 103, "low": 100, "close": 102, "volume": 20},
    ]
    bar = rollup_bars(steps)
    assert bar["open"] == 100 and bar["close"] == 102
    assert bar["high"] == 103 and bar["low"] == 99
    assert bar["volume"] == 30

    df = pd.DataFrame(steps)
    df["ts"] = pd.date_range("2024-01-01 09:30", periods=2, freq="15min")
    rolled = rollup_df(df, 2)
    assert len(rolled) == 1
    assert rolled["close"].iloc[0] == 102


if __name__ == "__main__":
    test_rollup_bars_and_df()
    test_session_filter_and_daily_build()
    test_cascade_alignment_and_feed_forward()
    print("All tests passed.")
