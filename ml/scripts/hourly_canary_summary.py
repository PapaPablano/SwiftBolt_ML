#!/usr/bin/env python3
"""
Hourly canary summary: compare intraday forecast rows vs realized OHLC closes.

Reads predicted closes from ohlc_bars_v2 where is_forecast=true at target timestamps,
and realized closes from ohlc_bars_v2 where is_forecast=false.

Targets are specified in CST (America/Chicago) as HH:MM times for a given date.
"""

import argparse
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import sys

# Add parent for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.supabase_db import db  # noqa: E402


CST = ZoneInfo("America/Chicago")
UTC = timezone.utc

# Match forecast_bar_writer timestamp format (Z suffix)
def _to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _parse_symbols(s: str) -> list[str]:
    return [x.strip().upper() for x in (s or "").split(",") if x.strip()]


def _parse_targets_cst(s: str) -> list[time]:
    out: list[time] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        hh, mm = part.split(":")
        out.append(time(hour=int(hh), minute=int(mm)))
    return out


def _date_from_arg(s: str | None) -> date:
    if s and s.strip():
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    # default: "today" in CST
    return datetime.now(CST).date()


def _target_dt_utc(d: date, t_cst: time) -> datetime:
    dt_cst = datetime(d.year, d.month, d.day, t_cst.hour, t_cst.minute, tzinfo=CST)
    return dt_cst.astimezone(UTC)


def _get_symbol_id(ticker: str) -> str | None:
    resp = (
        db.client.table("symbols")
        .select("id")
        .eq("ticker", ticker)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    return rows[0]["id"]


def _fetch_close(
    symbol_id: str,
    ts_utc: datetime,
    timeframe: str,
    is_forecast: bool,
    provider_preference: list[str | None] | None = None,
) -> "BarPoint | None":
    ts_iso = _to_iso_z(ts_utc)
    table = db.client.table("ohlc_bars_v2").select("ts, close, provider")
    provider_preference = provider_preference or [None]

    for prov in provider_preference:
        q = (
            table.eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .eq("is_forecast", is_forecast)
            .eq("ts", ts_iso)
        )
        if prov:
            q = q.eq("provider", prov)
        r = q.limit(5).execute()
        rows = r.data or []
        if not rows:
            continue

        row = rows[0]
        row_ts = pd.to_datetime(row["ts"], utc=True).to_pydatetime()
        return BarPoint(ts_utc=row_ts, close=float(row["close"]), provider=row.get("provider"))

    return None


@dataclass
class BarPoint:
    ts_utc: datetime
    close: float
    provider: str | None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="AAPL,MSFT,SPY")
    ap.add_argument("--date-cst", default="", help="YYYY-MM-DD in CST (default: today CST)")
    ap.add_argument(
        "--targets-cst",
        default="09:30,10:30,11:30,12:30,13:30,14:30",
        help="Comma-separated HH:MM targets in CST",
    )
    ap.add_argument("--timeframe", default="m15")
    ap.add_argument("--out", default="validation_results/hourly_canary_summary.csv")
    args = ap.parse_args()

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        raise SystemExit("No symbols provided")

    d = _date_from_arg(args.date_cst)
    targets = _parse_targets_cst(args.targets_cst)
    if not targets:
        raise SystemExit("No targets provided")

    rows_out: list[dict] = []
    missing: list[tuple[str, str]] = []

    for sym in symbols:
        symbol_id = _get_symbol_id(sym)
        if not symbol_id:
            missing.append((sym, "symbol_missing"))
            continue

        for t_cst in targets:
            target_utc = _target_dt_utc(d, t_cst)

            pred = _fetch_close(
                symbol_id=symbol_id,
                ts_utc=target_utc,
                timeframe=args.timeframe,
                is_forecast=True,
                provider_preference=[None],
            )

            real = _fetch_close(
                symbol_id=symbol_id,
                ts_utc=target_utc,
                timeframe=args.timeframe,
                is_forecast=False,
                provider_preference=["alpaca", "polygon", "yfinance", None],
            )

            if pred is None:
                missing.append((sym, f"missing_forecast@{target_utc.isoformat()}"))
            if real is None:
                missing.append((sym, f"missing_realized@{target_utc.isoformat()}"))

            if pred is None or real is None:
                continue

            error_abs = abs(real.close - pred.close)
            error_pct = (error_abs / pred.close) if pred.close != 0 else None

            rows_out.append(
                {
                    "symbol": sym,
                    "target_ts_utc": target_utc.isoformat(),
                    "target_time_cst": f"{t_cst.hour:02d}:{t_cst.minute:02d}",
                    "predicted_close": pred.close,
                    "realized_close": real.close,
                    "error_abs": error_abs,
                    "error_pct": error_pct,
                    "pred_provider": pred.provider,
                    "real_provider": real.provider,
                }
            )

    fieldnames = [
        "symbol",
        "target_ts_utc",
        "target_time_cst",
        "predicted_close",
        "realized_close",
        "error_abs",
        "error_pct",
        "pred_provider",
        "real_provider",
    ]
    out_path = args.out
    out_dir = out_path.rsplit("/", 1)[0] if "/" in out_path else "."
    os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    print("\nHourly Canary Summary")
    print(f"Date (CST): {d.isoformat()}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Targets (CST): {args.targets_cst}")
    print(f"Rows: {len(rows_out)}")
    if missing:
        print("\nMissing items:")
        for m in missing[:50]:
            print(f"  - {m[0]}: {m[1]}")
        if len(missing) > 50:
            print(f"  ... ({len(missing) - 50} more)")

    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
