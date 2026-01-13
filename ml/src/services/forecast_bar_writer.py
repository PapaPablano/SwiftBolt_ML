from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Literal, Optional

from src.data.supabase_db import db

TF = Literal["m15", "h1", "h4", "d1", "w1"]


def _to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _bucket_ts(ts: datetime, timeframe: TF) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    if timeframe == "m15":
        minute = (ts.minute // 15) * 15
        return ts.replace(minute=minute, second=0, microsecond=0)

    if timeframe == "h1":
        return ts.replace(minute=0, second=0, microsecond=0)

    if timeframe == "h4":
        hour = (ts.hour // 4) * 4
        return ts.replace(hour=hour, minute=0, second=0, microsecond=0)

    if timeframe == "d1":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)

    if timeframe == "w1":
        monday = ts - timedelta(days=ts.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)

    return ts


def upsert_forecast_bars(
    *,
    symbol: str,
    timeframe: TF,
    rows: Iterable[Dict],
    status: str = "provisional",
    fetched_at: Optional[datetime] = None,
    skip_non_future_dates: bool = True,
) -> int:
    symbol_id = db.get_symbol_id(symbol)

    now = fetched_at or datetime.now(tz=timezone.utc)
    today_utc = now.date()
    allow_today = timeframe in ("m15", "h1", "h4")

    payload = []
    for r in rows:
        ts = r.get("ts")
        if ts is None:
            continue
        if isinstance(ts, (int, float)):
            ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        elif isinstance(ts, datetime):
            ts_dt = ts
        else:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))

        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        else:
            ts_dt = ts_dt.astimezone(timezone.utc)

        ts_dt = _bucket_ts(ts_dt, timeframe)

        if skip_non_future_dates:
            if allow_today:
                if ts_dt.date() < today_utc:
                    continue
            else:
                if ts_dt.date() <= today_utc:
                    continue

        open_v = r.get("open")
        high_v = r.get("high")
        low_v = r.get("low")
        close_v = r.get("close")

        upper_band = r.get("upper_band")
        lower_band = r.get("lower_band")

        bands = r.get("bands")
        if isinstance(bands, dict):
            if upper_band is None:
                upper_band = bands.get("upper")
            if lower_band is None:
                lower_band = bands.get("lower")

        conf_score = r.get("confidence_score")

        payload.append(
            {
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": _to_iso_z(ts_dt),
                "open": float(open_v) if open_v is not None else None,
                "high": float(high_v) if high_v is not None else None,
                "low": float(low_v) if low_v is not None else None,
                "close": float(close_v) if close_v is not None else None,
                "volume": int(r.get("volume", 0) or 0),
                "provider": "ml_forecast",
                "is_intraday": False,
                "is_forecast": True,
                "data_status": status,
                "fetched_at": _to_iso_z(now),
                "confidence_score": (
                    float(conf_score)
                    if conf_score is not None
                    else None
                ),
                "upper_band": (
                    float(upper_band)
                    if upper_band is not None
                    else None
                ),
                "lower_band": (
                    float(lower_band)
                    if lower_band is not None
                    else None
                ),
            }
        )

    if not payload:
        return 0

    db.client.table("ohlc_bars_v2").upsert(
        payload,
        on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
    ).execute()

    return len(payload)


def point_forecast_to_bars(
    *,
    points: Iterable[Dict],
    price_key: str = "value",
    lower_key: str = "lower",
    upper_key: str = "upper",
) -> list[dict]:
    rows: list[dict] = []
    for p in points:
        ts = p.get("ts")
        if ts is None:
            continue
        price = p.get(price_key)
        if price is None:
            continue
        price_f = float(price)
        upper_v = p.get(upper_key)
        lower_v = p.get(lower_key)
        rows.append(
            {
                "ts": ts,
                "open": price_f,
                "high": price_f,
                "low": price_f,
                "close": price_f,
                "volume": 0,
                "upper_band": float(upper_v) if upper_v is not None else None,
                "lower_band": float(lower_v) if lower_v is not None else None,
            }
        )
    return rows


def path_points_to_bars(
    *,
    points: Iterable[Dict],
    timeframe: TF,
) -> list[dict]:
    buckets: dict[datetime, list[dict]] = {}
    for p in points:
        ts = p.get("ts")
        if ts is None:
            continue

        if isinstance(ts, (int, float)):
            ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        elif isinstance(ts, datetime):
            ts_dt = ts
        else:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))

        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        else:
            ts_dt = ts_dt.astimezone(timezone.utc)

        bucket = _bucket_ts(ts_dt, timeframe)
        buckets.setdefault(bucket, []).append(dict(p))

    rows: list[dict] = []
    for bucket_ts in sorted(buckets.keys()):
        pts = sorted(buckets[bucket_ts], key=lambda x: x.get("ts", 0))
        values = [float(p.get("value", 0) or 0) for p in pts]
        uppers = [p.get("upper") for p in pts if p.get("upper") is not None]
        lowers = [p.get("lower") for p in pts if p.get("lower") is not None]

        if not values:
            continue

        open_v = values[0]
        close_v = values[-1]
        high_v = max(values)
        low_v = min(values)

        upper_band = max(float(upper) for upper in uppers) if uppers else None
        lower_band = min(float(lower) for lower in lowers) if lowers else None

        rows.append(
            {
                "ts": bucket_ts,
                "open": open_v,
                "high": high_v,
                "low": low_v,
                "close": close_v,
                "volume": 0,
                "upper_band": upper_band,
                "lower_band": lower_band,
            }
        )

    return rows


def prune_forecast_bars(
    *,
    timeframes: Iterable[TF],
    older_than_days: int,
) -> int:
    cutoff = datetime.now(tz=timezone.utc).replace(microsecond=0) - timedelta(
        days=int(older_than_days)
    )
    timeframes_list = list(timeframes)
    if not timeframes_list:
        return 0

    resp = (
        db.client.table("ohlc_bars_v2")
        .delete()
        .eq("provider", "ml_forecast")
        .eq("is_forecast", True)
        .in_("timeframe", timeframes_list)
        .lt("ts", _to_iso_z(cutoff))
        .execute()
    )

    return len(resp.data or [])
