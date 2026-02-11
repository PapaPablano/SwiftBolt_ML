"""
Market calendar resolver for Forecasting Lab.

Uses Alpaca trading API calendar to get the next N trading days with
regular session open/close (early-close aware). For cascade and session-only bars.
Exposes session open/close as timestamps for filtering 15m bars and building daily bars.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import aiohttp
import asyncio

# Alpaca trading API (calendar lives here)
ALPACA_TRADING_BASE = os.getenv("ALPACA_TRADING_BASE", "https://paper-api.alpaca.markets")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")

# Market session is US Eastern; use for session_open/close timestamps
try:
    import zoneinfo
    EASTERN = zoneinfo.ZoneInfo("America/New_York")
except ImportError:
    from datetime import timezone as tz
    EASTERN = tz(timedelta(hours=-5))  # fallback UTC-5


def _time_str_to_dt(d: date, t_str: str) -> datetime:
    """Combine date with time string (HH:MM or ISO) into Eastern datetime, then UTC."""
    if isinstance(t_str, str) and "T" in t_str:
        t_str = t_str.split("T")[1][:5]
    parts = t_str.strip().split(":")
    hour = int(parts[0]) if len(parts) > 0 else 9
    minute = int(parts[1]) if len(parts) > 1 else 30
    dt_eastern = datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=EASTERN)
    return dt_eastern.astimezone(timezone.utc)


@dataclass
class CalendarDay:
    """One trading day: date and session open/close (regular session only). Early-close preserved."""

    date: date
    session_open: str
    session_close: str
    early_close: bool = False
    session_open_ts: Optional[datetime] = None
    session_close_ts: Optional[datetime] = None


def with_session_timestamps(day: CalendarDay) -> CalendarDay:
    """Fill session_open_ts and session_close_ts (UTC) from date + session_open/close."""
    so = day.session_open if isinstance(day.session_open, str) else "09:30"
    sc = day.session_close if isinstance(day.session_close, str) else "16:00"
    if "T" in so:
        so = so.split("T")[1][:5]
    if "T" in sc:
        sc = sc.split("T")[1][:5]
    day.session_open_ts = _time_str_to_dt(day.date, so)
    day.session_close_ts = _time_str_to_dt(day.date, sc)
    return day


def _parse_calendar_item(item: dict) -> CalendarDay:
    """Parse one calendar day from Alpaca response."""
    d = item.get("date") or item.get("date_str", "")
    if isinstance(d, str) and "T" in d:
        d = d.split("T")[0]
    dt = datetime.fromisoformat(d.replace("Z", "+00:00")) if isinstance(d, str) else d
    if hasattr(dt, "date"):
        day = dt.date()
    else:
        day = date.fromisoformat(d[:10]) if isinstance(d, str) else d
    so = item.get("session_open") or item.get("open", "09:30")
    sc = item.get("session_close") or item.get("close", "16:00")
    if isinstance(so, str) and "T" in so:
        so = so.split("T")[1][:5]
    if isinstance(sc, str) and "T" in sc:
        sc = sc.split("T")[1][:5]
    early = sc < "16:00" if isinstance(sc, str) else False
    return CalendarDay(date=day, session_open=str(so), session_close=str(sc), early_close=early)


async def _fetch_calendar(start: date, end: date) -> list[CalendarDay]:
    """Fetch calendar from Alpaca (async)."""
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        return []
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    params = {"start": start.isoformat(), "end": end.isoformat()}
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
    items = data if isinstance(data, list) else data.get("calendar", data.get("days", []))
    return [with_session_timestamps(_parse_calendar_item(item)) for item in items]


def get_calendar_days(start_date: date, end_date: date) -> list[CalendarDay]:
    """
    Return trading days with session open/close timestamps for a date range.
    Use for building session-based daily bars (1D from 15m within session windows).
    Early-close days are preserved (session_close_ts reflects early close).
    """
    days = asyncio.run(_fetch_calendar(start_date, end_date))
    return [d for d in days if start_date <= d.date <= end_date]


def next_n_trading_days(
    from_date: Optional[date | datetime] = None,
    n: int = 5,
) -> list[CalendarDay]:
    """
    Return the next n trading days (regular session only) via Alpaca calendar.
    Each CalendarDay has session_open_ts and session_close_ts (UTC) set for bar filtering.
    """
    if from_date is None:
        from_date = datetime.now(timezone.utc).date()
    if hasattr(from_date, "date"):
        from_date = from_date.date()
    end = from_date + timedelta(days=max(30, n * 2))
    days = asyncio.run(_fetch_calendar(from_date, end))
    out: list[CalendarDay] = []
    for d in days:
        if d.date >= from_date and len(out) < n:
            out.append(d)
    return out[:n]


def get_next_5_trading_days(from_date: Optional[date | datetime] = None) -> list[CalendarDay]:
    """Convenience: next 5 trading days for cascade weekly close (day 5 close)."""
    return next_n_trading_days(from_date=from_date, n=5)


def session_timestamps_for_next_n_days(
    n: int = 5,
    from_date: Optional[date | datetime] = None,
) -> list[tuple[datetime, datetime]]:
    """
    Return (session_open_ts, session_close_ts) in UTC for the next n trading days.
    Use to filter 15m bars to regular session or to build session-based daily bars.
    Early-close days have session_close_ts at early-close time.
    """
    days = next_n_trading_days(from_date=from_date, n=n)
    out = []
    for d in days:
        if d.session_open_ts is not None and d.session_close_ts is not None:
            out.append((d.session_open_ts, d.session_close_ts))
    return out
