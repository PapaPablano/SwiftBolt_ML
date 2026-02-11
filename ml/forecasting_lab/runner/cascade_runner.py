"""
Cascade runner for Forecasting Lab (Option A OHLC + cascade).

Flow: 15m predict(4) → indicator recompute on history+pred → rollup to 1h → [append bar to 1h history]
→ predict(4) → rollup to 4h_trading → append → predict(4) → rollup to 1D (session-based) → append
→ predict(5) → weekly close = day 5 close.

- Daily (1D) bars are built by session boundaries from the Alpaca calendar (open→close, early-close aware),
  resampling 15m within those windows; we do not derive 1D from "4×4h."
- Lower TF guides higher TF: at each level we append the rolled-up predicted bar as the next input row
  before predicting the next horizon (feed-forward cascade).
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Lab root
LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from forecasting_lab.models.base import OHLCStep, BaseForecaster


def _attach_indicator_bundle(
    df_history: pd.DataFrame,
    pred_steps: list[OHLCStep],
) -> list[OHLCStep]:
    """
    Recompute indicators on history + predicted OHLC and attach an indicator forecast bundle
    to each predicted step (Level 1). Each OHLCStep may get extra keys: rsi_14, macd, macd_signal,
    macd_hist, bb_upper, bb_mid, bb_lower, kdj_k, kdj_d, kdj_j. Modifies pred_steps in place; returns it.
    """
    if not pred_steps:
        return pred_steps
    try:
        from forecasting_lab.features.indicators import INDICATOR_KEYS, compute_indicator_bundle
    except ImportError:
        return pred_steps
    n_hist = len(df_history)
    close_hist = df_history["close"].astype(float).values
    close_pred = np.array([float(p["close"]) for p in pred_steps])
    close_full = np.concatenate([close_hist, close_pred])
    high_hist = df_history["high"].astype(float).values if "high" in df_history.columns else close_hist
    high_pred = np.array([float(p.get("high", p["close"])) for p in pred_steps])
    high_full = np.concatenate([high_hist, high_pred])
    low_hist = df_history["low"].astype(float).values if "low" in df_history.columns else close_hist
    low_pred = np.array([float(p.get("low", p["close"])) for p in pred_steps])
    low_full = np.concatenate([low_hist, low_pred])
    bundle = compute_indicator_bundle(close_full, high_full, low_full)
    for i, step in enumerate(pred_steps):
        idx = n_hist + i
        if idx >= len(bundle):
            continue
        row = bundle.iloc[idx]
        for k in INDICATOR_KEYS:
            if k not in row:
                continue
            v = row[k]
            if pd.isna(v):
                continue
            step[k] = float(v)
    return pred_steps


def rollup_bars(steps: list[OHLCStep]) -> OHLCStep:
    """
    Roll up N OHLC steps into one bar: open=first open, high=max high, low=min low,
    close=last close, volume=sum volume.
    """
    if not steps:
        return {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0}
    o = float(steps[0].get("open", steps[0]["close"]))
    c = float(steps[-1].get("close", steps[-1]["open"]))
    h = max(float(s.get("high", s.get("close", 0))) for s in steps)
    l_ = min(float(s.get("low", s.get("close", float("inf")))) for s in steps)
    v = sum(float(s.get("volume", 0)) for s in steps)
    return {"open": o, "high": h, "low": l_, "close": c, "volume": v}


def rollup_df(df: pd.DataFrame, group_size: int) -> pd.DataFrame:
    """
    Roll up a DataFrame of OHLC bars by grouping every group_size rows.
    Used for 4×15m → 1h and 4×1h → 4h_trading within session-only data.
    """
    if df is None or len(df) == 0 or group_size <= 0:
        return pd.DataFrame()
    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            df = df.copy()
            df[col] = df["close"] if col == "close" else df.get("close", 0)
    if "volume" not in df.columns:
        df = df.copy()
        df["volume"] = 0
    n = (len(df) // group_size) * group_size
    if n == 0:
        return pd.DataFrame()
    df = df.iloc[:n]
    rows = []
    for i in range(0, n, group_size):
        block = df.iloc[i : i + group_size]
        rows.append({
            "open": block["open"].iloc[0],
            "high": block["high"].max(),
            "low": block["low"].min(),
            "close": block["close"].iloc[-1],
            "volume": block["volume"].sum(),
        })
    out = pd.DataFrame(rows)
    if "ts" in df.columns:
        out["ts"] = df["ts"].iloc[group_size - 1 :: group_size].values
    return out


def _bar_to_row(bar: OHLCStep, ts: datetime | pd.Timestamp | None = None) -> pd.Series:
    """Represent a rolled-up predicted bar as a single DataFrame row for appending to history."""
    row = pd.Series({
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "volume": bar.get("volume", 0),
    })
    if ts is not None:
        row["ts"] = ts
    return row


def append_bar(df: pd.DataFrame, bar: OHLCStep, ts: datetime | pd.Timestamp | None = None) -> pd.DataFrame:
    """
    Append a rolled-up predicted bar as the next input row (feed-forward: lower TF guides higher TF).
    The model at the next level will see this bar as the last observation when predicting.
    """
    row = _bar_to_row(bar, ts)
    if "ts" in df.columns and ts is None:
        last = df["ts"].iloc[-1]
        try:
            row["ts"] = last + pd.Timedelta(hours=1)
        except Exception:
            row["ts"] = last
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def _filter_df_to_session(df: pd.DataFrame, session_open_ts: datetime, session_close_ts: datetime) -> pd.DataFrame:
    """Keep rows where ts is within [session_open_ts, session_close_ts). ts is bar-start; exclude bar at close."""
    if df is None or df.empty or "ts" not in df.columns:
        return pd.DataFrame()
    ts = pd.to_datetime(df["ts"])
    if ts.dt.tz is None and session_open_ts.tzinfo is not None:
        ts = ts.dt.tz_localize(timezone.utc)
    elif ts.dt.tz is not None and session_open_ts.tzinfo is None:
        session_open_ts = session_open_ts.replace(tzinfo=timezone.utc)
        session_close_ts = session_close_ts.replace(tzinfo=timezone.utc)
    mask = (ts >= session_open_ts) & (ts < session_close_ts)
    return df.loc[mask].copy()


def _calendar_for_df_range(df_15m: pd.DataFrame) -> list:
    """
    Get calendar days with session timestamps for the date range of df_15m.
    Uses Alpaca when credentials exist; otherwise synthetic weekdays 09:30–16:00 Eastern.
    """
    if df_15m is None or df_15m.empty or "ts" not in df_15m.columns:
        return []
    ts = pd.to_datetime(df_15m["ts"])
    start_date = ts.min().date() if hasattr(ts.min(), "date") else date.fromisoformat(str(ts.min())[:10])
    end_date = ts.max().date() if hasattr(ts.max(), "date") else date.fromisoformat(str(ts.max())[:10])

    try:
        from forecasting_lab.data.market_calendar_resolver import get_calendar_days, CalendarDay, with_session_timestamps
        days = get_calendar_days(start_date, end_date)
        if days:
            return days
    except Exception:
        pass

    # Fallback: synthetic weekdays 09:30–16:00 Eastern for tests / no API
    try:
        from forecasting_lab.data.market_calendar_resolver import CalendarDay, with_session_timestamps
    except ImportError:
        return []
    out = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Mon–Fri
            out.append(with_session_timestamps(CalendarDay(date=d, session_open="09:30", session_close="16:00", early_close=False)))
        d += timedelta(days=1)
    return out


def filter_15m_to_regular_session(df_15m: pd.DataFrame, calendar_days: list) -> pd.DataFrame:
    """Filter 15m bars to regular session only (open→close per calendar day). Early-close aware."""
    if not calendar_days or df_15m is None or df_15m.empty:
        return df_15m
    pieces = []
    for day in calendar_days:
        if getattr(day, "session_open_ts", None) is None or getattr(day, "session_close_ts", None) is None:
            continue
        chunk = _filter_df_to_session(df_15m, day.session_open_ts, day.session_close_ts)
        if not chunk.empty:
            pieces.append(chunk)
    if not pieces:
        return df_15m
    out = pd.concat(pieces, ignore_index=True).sort_values("ts").reset_index(drop=True)
    return out


def build_daily_bars_from_session_15m(df_15m_session: pd.DataFrame, calendar_days: list) -> pd.DataFrame:
    """
    Build 1D bars by session boundaries: for each calendar day, take 15m bars within
    session_open_ts → session_close_ts and roll up to one OHLC bar. Does not use 4×4h.
    """
    if not calendar_days or df_15m_session is None or df_15m_session.empty:
        return pd.DataFrame()
    rows = []
    for day in calendar_days:
        if getattr(day, "session_open_ts", None) is None or getattr(day, "session_close_ts", None) is None:
            continue
        chunk = _filter_df_to_session(df_15m_session, day.session_open_ts, day.session_close_ts)
        if chunk.empty:
            continue
        o = chunk["open"].iloc[0]
        h = chunk["high"].max()
        l_ = chunk["low"].min()
        c = chunk["close"].iloc[-1]
        v = chunk["volume"].sum() if "volume" in chunk.columns else 0
        ts = chunk["ts"].iloc[-1] if "ts" in chunk.columns else day.date
        rows.append({"ts": ts, "open": o, "high": h, "low": l_, "close": c, "volume": v})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)


def run_cascade(
    df_15m: pd.DataFrame,
    model_factory: None | type[BaseForecaster] = None,
    include_calendar: bool = True,
) -> dict:
    """
    Run single cascade with session-based 1D and feed-forward chaining.

    - 15m and 1h/4h_trading: built from 15m filtered to regular session; 1h = 4×15m, 4h_trading = 4×1h (trading-time, not calendar 4h).
    - 1D: built by calendar session boundaries (one bar per trading day, open→close).
    - At each level, the rolled-up predicted bar from the lower level is appended to history
      before predicting the next horizon (lower timeframe guides higher timeframe).
    """
    if model_factory is None:
        from forecasting_lab.models.naive_forecaster import NaiveForecaster
        model_factory = NaiveForecaster

    calendar_days = _calendar_for_df_range(df_15m)
    df_15m_session = filter_15m_to_regular_session(df_15m, calendar_days)
    if df_15m_session.empty:
        df_15m_session = df_15m

    # 1h and 4h_trading from session-only 15m (4×15m = 1h, 4×1h = 4h_trading; not calendar 4h)
    df_1h = rollup_df(df_15m_session, 4)
    df_4h_trading = rollup_df(df_1h, 4)
    # 1D by session boundaries (not 4×4h)
    df_1d = build_daily_bars_from_session_15m(df_15m_session, calendar_days)

    if df_1h.empty or df_4h_trading.empty:
        return {
            "weekly_close": None,
            "levels": {},
            "error": "Insufficient 15m session data to build 1h/4h_trading",
        }
    if df_1d.empty:
        return {
            "weekly_close": None,
            "levels": {},
            "error": "Insufficient calendar/session data to build 1D bars",
        }

    # L1: 15m predict(4) → rollup to 1h; then indicator recompute on history+pred (Option A)
    m_15m = model_factory()
    m_15m.train(df_15m_session, target_col="close", horizon=4)
    pred_15m_4 = m_15m.predict(df_15m_session, horizon=4)
    pred_15m_4 = _attach_indicator_bundle(df_15m_session, pred_15m_4)
    bar_1h = rollup_bars(pred_15m_4)

    # L2: append bar_1h to 1h history, then predict(4) → rollup to 4h_trading (feed-forward)
    df_1h_aug = append_bar(df_1h, bar_1h)
    m_1h = model_factory()
    m_1h.train(df_1h, target_col="close", horizon=4)
    pred_1h_4 = m_1h.predict(df_1h_aug, horizon=4)
    bar_4h = rollup_bars(pred_1h_4)

    # L3: append bar_4h to 4h_trading history, then predict(4) → rollup to 1D bar (one session bar)
    df_4h_aug = append_bar(df_4h_trading, bar_4h)
    m_4h = model_factory()
    m_4h.train(df_4h_trading, target_col="close", horizon=4)
    pred_4h_4 = m_4h.predict(df_4h_aug, horizon=4)
    bar_1d_rolled = rollup_bars(pred_4h_4)

    # L4: append that 1D bar to 1D history, then predict(5) → weekly close = day 5 close
    df_1d_aug = append_bar(df_1d, bar_1d_rolled)
    m_1d = model_factory()
    m_1d.train(df_1d, target_col="close", horizon=5)
    pred_1d_5 = m_1d.predict(df_1d_aug, horizon=5)
    weekly_close = pred_1d_5[4]["close"] if len(pred_1d_5) > 4 else None

    result = {
        "weekly_close": weekly_close,
        "levels": {
            "15m": {"predicted_4": pred_15m_4, "rolled_1h": bar_1h},
            "1h": {"predicted_4": pred_1h_4, "rolled_4h": bar_4h},
            "4h_trading": {"predicted_4": pred_4h_4, "rolled_1d": bar_1d_rolled},
            "1d": {"predicted_5": pred_1d_5},
        },
    }

    # Emit canonical ForecastPoint array (Level 1, 15m) for ml_forecasts_intraday.points / Edge
    try:
        from forecasting_lab.schema.points import ohlc_steps_to_points
        last_ts = df_15m_session["ts"].iloc[-1] if "ts" in df_15m_session.columns and len(df_15m_session) > 0 else None
        result["points"] = ohlc_steps_to_points(pred_15m_4, "m15", last_ts=last_ts, step_start=1, step_duration_minutes=15)
    except Exception:
        result["points"] = []

    if include_calendar:
        try:
            from forecasting_lab.data.market_calendar_resolver import get_next_5_trading_days
            result["calendar_days"] = [
                {"date": d.date.isoformat(), "session_open": d.session_open, "session_close": d.session_close}
                for d in get_next_5_trading_days()
            ]
        except Exception:
            result["calendar_days"] = []

    return result
