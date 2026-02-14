#!/usr/bin/env python3
"""
Hourly canary summary: compare intraday forecast rows vs realized OHLC closes.

Forecast source (--forecast-source):
  intraday: predicted closes from ml_forecasts_intraday (latest created_at <= target)
  bars:     predicted closes from ohlc_bars_v2 where is_forecast=true at target ts

Realized closes: always from ohlc_bars_v2 where is_forecast=false.

Targets are specified in ET (America/New_York, market-native, DST-safe) as HH:MM.
"""

import argparse
import bisect
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import sys

# Add parent for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.supabase_db import db  # noqa: E402


ET = ZoneInfo("America/New_York")
UTC = timezone.utc

PAGE_SIZE = 1000

# Map timeframe to horizon for ml_forecasts_intraday
TIMEFRAME_TO_HORIZON = {"m15": "15m", "h1": "1h"}


def _to_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _parse_symbols(s: str) -> list[str]:
    return [x.strip().upper() for x in (s or "").split(",") if x.strip()]


def _parse_targets_et(s: str) -> list[time]:
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
    return datetime.now(ET).date()


def _target_dt_utc(d: date, t_et: time) -> datetime:
    dt_et = datetime(d.year, d.month, d.day, t_et.hour, t_et.minute, tzinfo=ET)
    return dt_et.astimezone(UTC)


def _infer_target_from_utc_now() -> tuple[date, time]:
    """Infer single target (date, HH:MM) from current UTC. For scheduled hourly_summary."""
    now_utc = datetime.now(UTC)
    now_et = now_utc.astimezone(ET)
    d = now_et.date()
    # At :40 ET we validate the :30 bar that just closed
    t = time(hour=now_et.hour, minute=30)
    return d, t


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


def _fetch_intraday_forecasts_batch(
    symbols: list[str],
    timeframe: str,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[tuple[str, str], list[dict]]:
    """
    Batch fetch ml_forecasts_intraday for date range, per (symbol, horizon).
    Returns dict[(symbol, horizon)] -> list of rows sorted by created_at asc.
    """
    horizon = TIMEFRAME_TO_HORIZON.get(timeframe, "15m")
    start_iso = start_utc.isoformat()
    end_iso = end_utc.isoformat()

    result: dict[tuple[str, str], list[dict]] = {}
    for sym in symbols:
        result[(sym, horizon)] = []

    try:
        all_data: list[dict] = []
        cursor_created_at: str | None = None
        while True:
            q = (
                db.client.table("ml_forecasts_intraday")
                .select("symbol,horizon,created_at,points,target_price")
                .in_("symbol", [s.upper() for s in symbols])
                .eq("horizon", horizon)
                .gte("created_at", start_iso)
                .lte("created_at", end_iso)
                .order("created_at", desc=False)
                .limit(PAGE_SIZE)
            )
            if cursor_created_at is not None:
                q = q.gt("created_at", cursor_created_at)
            resp = q.execute()
            chunk = resp.data or []
            all_data.extend(chunk)
            if len(chunk) < PAGE_SIZE:
                break
            cursor_created_at = chunk[-1]["created_at"]

        for row in all_data:
            sym = str(row.get("symbol", "")).upper()
            h = str(row.get("horizon", ""))
            key = (sym, h)
            if key in result:
                result[key].append(row)
    except Exception as e:
        print(f"Error fetching ml_forecasts_intraday: {e}", file=sys.stderr)
    return result


def _parse_created_at(row: dict) -> datetime | None:
    created = row.get("created_at")
    if not created:
        return None
    try:
        s = str(created).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return None


def _predicted_close_from_forecast(
    row: dict,
    target_utc: datetime,
) -> tuple[float | None, str]:
    """
    Extract predicted_close from ml_forecasts_intraday row.
    Prefer: point with ts == target_utc, else nearest point with ts <= target.
    Fallback: target_price.
    Returns (value, source) where source is "points_exact", "points_nearest", or "target_price".
    """
    points = row.get("points")
    if not isinstance(points, list) or not points:
        val = _target_price_from_row(row)
        return (val, "target_price") if val is not None else (None, "target_price")

    # Build list of (ts_dt, value) for points with ts <= target
    candidates: list[tuple[datetime, float]] = []
    target_ts = target_utc
    if target_utc.tzinfo is None:
        target_ts = target_utc.replace(tzinfo=UTC)

    for p in points:
        ts_raw = p.get("ts")
        val = p.get("value")
        if val is None:
            continue
        try:
            val_f = float(val)
        except (TypeError, ValueError):
            continue
        if not ts_raw:
            continue
        try:
            s = str(ts_raw).replace("Z", "+00:00")
            pt_dt = datetime.fromisoformat(s)
            if pt_dt.tzinfo is None:
                pt_dt = pt_dt.replace(tzinfo=UTC)
            if pt_dt <= target_ts:
                candidates.append((pt_dt, val_f))
        except Exception:
            continue

    if not candidates:
        val = _target_price_from_row(row)
        return (val, "target_price") if val is not None else (None, "target_price")

    # Exact match
    for pt_dt, val in candidates:
        if pt_dt == target_ts:
            return (val, "points_exact")

    # Nearest point with ts <= target (largest ts)
    candidates.sort(key=lambda x: x[0])
    return (candidates[-1][1], "points_nearest")


def _target_price_from_row(row: dict) -> float | None:
    tp = row.get("target_price")
    if tp is None:
        return None
    try:
        return float(tp)
    except (TypeError, ValueError):
        return None


def _predicted_close_from_intraday(
    forecast_index: dict[tuple[str, str], list[tuple[datetime, dict]]],
    symbol: str,
    timeframe: str,
    target_utc: datetime,
) -> tuple["BarPoint | None", str | None]:
    """
    Binary-search for latest forecast with created_at <= target_utc, extract predicted_close.
    Returns (BarPoint, pred_source) or (None, None). pred_source is "points_exact",
    "points_nearest", or "target_price".
    """
    horizon = TIMEFRAME_TO_HORIZON.get(timeframe, "15m")
    key = (symbol.upper(), horizon)
    rows = forecast_index.get(key, [])
    if not rows:
        return (None, None)

    # Binary search: rightmost created_at <= target_utc
    created_at_list = [r[0] for r in rows]
    idx = bisect.bisect_right(created_at_list, target_utc) - 1
    if idx < 0:
        return (None, None)

    _, row = rows[idx]
    close, pred_source = _predicted_close_from_forecast(row, target_utc)
    if close is None:
        return (None, None)
    return (BarPoint(ts_utc=target_utc, close=close, provider="intraday"), pred_source)


def _fetch_close(
    symbol_id: str,
    ts_utc: datetime,
    timeframe: str,
    is_forecast: bool,
    provider_preference: list[str | None] | None = None,
    tolerance_minutes: int = 0,
) -> "BarPoint | None":
    """
    Fetch close from ohlc_bars_v2.
    If tolerance_minutes > 0, search for nearest bar within ±tolerance_minutes (realized only).
    Default (0) uses exact timestamp match.
    """
    provider_preference = provider_preference or [None]
    table = db.client.table("ohlc_bars_v2").select("ts, close, provider")

    if tolerance_minutes <= 0:
        ts_iso = _to_iso_z(ts_utc)
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

    # ±tolerance_minutes: fetch bars in window, pick nearest (realized only)
    delta = timedelta(minutes=tolerance_minutes)
    start_utc = ts_utc - delta
    end_utc = ts_utc + delta
    start_iso = _to_iso_z(start_utc)
    end_iso = _to_iso_z(end_utc)
    for prov in provider_preference:
        q = (
            table.eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .eq("is_forecast", is_forecast)
            .gte("ts", start_iso)
            .lte("ts", end_iso)
        )
        if prov:
            q = q.eq("provider", prov)
        r = q.order("ts").limit(50).execute()
        rows = r.data or []
        if not rows:
            continue
        target_ts = ts_utc.replace(tzinfo=UTC) if ts_utc.tzinfo else ts_utc
        best = min(
            rows,
            key=lambda rw: abs(
                (pd.to_datetime(rw["ts"], utc=True).to_pydatetime() - target_ts).total_seconds()
            ),
        )
        row_ts = pd.to_datetime(best["ts"], utc=True).to_pydatetime()
        return BarPoint(ts_utc=row_ts, close=float(best["close"]), provider=best.get("provider"))
    return None


@dataclass
class BarPoint:
    ts_utc: datetime
    close: float
    provider: str | None


def _fetch_m15_bars_for_date(symbol: str, d: date) -> pd.DataFrame:
    """Fetch m15 realized bars for the trading day (9:30-16:00 ET)."""
    end_et = datetime(d.year, d.month, d.day, 16, 1, tzinfo=ET)
    end_utc = end_et.astimezone(UTC)
    df = db.fetch_ohlc_bars(symbol, timeframe="m15", limit=50, end_ts=end_utc)
    if df.empty or "ts" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    start_et = datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
    start_utc = start_et.astimezone(UTC)
    df = df[df["ts"] >= start_utc].copy()
    return df.sort_values("ts").reset_index(drop=True)


# Min |return| to count as a real turn (avoid micro-flips from choppy days)
TURN_RETURN_THRESHOLD = 0.0015  # ~0.15% m15 move


def _detect_m15_turns(df: pd.DataFrame) -> list[tuple[int, datetime]]:
    """Detect bar-level turns from m15 returns (sign flip). Returns (bar_index, ts).
    Only counts turns where both bars have |r| >= threshold to avoid noise."""
    if len(df) < 3:
        return []
    returns = df["close"].pct_change().dropna()
    turns = []
    for i in range(1, len(returns)):
        r_prev = returns.iloc[i - 1]
        r_curr = returns.iloc[i]
        if r_prev == 0 or r_curr == 0:
            continue
        if abs(r_prev) < TURN_RETURN_THRESHOLD or abs(r_curr) < TURN_RETURN_THRESHOLD:
            continue
        sign_prev = 1 if r_prev > 0 else -1
        sign_curr = 1 if r_curr > 0 else -1
        if sign_prev != sign_curr:
            ts = df["ts"].iloc[i + 1]
            turns.append((i + 1, pd.Timestamp(ts).to_pydatetime()))
    return turns


def _compute_turn_metrics(rows_out: list[dict], d: date) -> list[dict]:
    """Compute flip_lag and post_turn_directional_accuracy per symbol.
    Uses m15 bar-level turn detection for a faithful measure of regime flips.
    Skips rows with missing_realized (no realized data for comparison)."""
    from collections import defaultdict

    by_sym: dict[str, list[dict]] = defaultdict(list)
    for r in rows_out:
        if r.get("missing_realized"):
            continue
        by_sym[r["symbol"]].append(r)

    result = []
    for sym, rows in by_sym.items():
        rows = sorted(rows, key=lambda x: x["target_time_et"])
        flip_lags: list[int] = []
        post_turn_correct = 0
        post_turn_total = 0
        m15_turns: list[datetime] = []

        try:
            m15_df = _fetch_m15_bars_for_date(sym, d)
            if len(m15_df) >= 3:
                for _idx, ts in _detect_m15_turns(m15_df):
                    m15_turns.append(ts)
        except Exception:
            pass

        for turn_ts in m15_turns:
            targets_after = [
                j for j in range(len(rows))
                if datetime.fromisoformat(rows[j]["target_ts_utc"].replace("Z", "+00:00")) > turn_ts
            ]
            if not targets_after:
                continue
            i = targets_after[0]

            lag = None
            for j in range(i + 1, len(rows)):
                if rows[j].get("predicted_direction") == rows[j].get("realized_direction") and rows[j].get("realized_direction") != 0:
                    lag = j - i - 1
                    break
            if lag is not None:
                flip_lags.append(lag)

            for j in range(i, min(i + 4, len(rows))):
                dc = rows[j].get("direction_correct")
                if dc != "" and dc is not None:
                    post_turn_total += 1
                    if dc == 1:
                        post_turn_correct += 1

        flip_lag_mean = sum(flip_lags) / len(flip_lags) if flip_lags else 0
        post_turn_acc = post_turn_correct / post_turn_total if post_turn_total > 0 else 0
        result.append({
            "symbol": sym,
            "flip_lag_mean": round(flip_lag_mean, 2),
            "post_turn_directional_accuracy": round(post_turn_acc, 4),
            "n_turns": len(m15_turns),
            "n_post_turn": post_turn_total,
        })
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="AAPL,MSFT,SPY")
    ap.add_argument("--date-et", default="", help="YYYY-MM-DD in ET (default: today ET)")
    ap.add_argument(
        "--days",
        type=int,
        default=1,
        help="Run for N days ending at --date-et (default: 1). Writes combined turn_metrics with date column.",
    )
    ap.add_argument(
        "--targets-et",
        default="09:30,10:30,11:30,12:30,13:30,14:30",
        help="Comma-separated HH:MM targets in ET (market-native)",
    )
    ap.add_argument(
        "--infer-target-from-now",
        action="store_true",
        help="Infer single target from current UTC (for scheduled hourly_summary). Overrides --targets-et.",
    )
    ap.add_argument("--timeframe", default="m15")
    ap.add_argument(
        "--forecast-source",
        default="intraday",
        choices=["intraday", "bars"],
        help="intraday=ml_forecasts_intraday (latest created_at<=target), bars=ohlc_bars_v2 is_forecast=true",
    )
    ap.add_argument(
        "--realized-tolerance-minutes",
        type=int,
        default=0,
        help="Match realized bar within ±N minutes (default 0=exact). Use 5 for provider timestamp drift.",
    )
    ap.add_argument(
        "--include-missing-realized",
        action="store_true",
        help="Write rows with realized_close=null when forecast exists but realized bar missing (for debugging).",
    )
    ap.add_argument("--out", default="validation_results/hourly_canary_summary.csv")
    args = ap.parse_args()

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        raise SystemExit("No symbols provided")

    if args.infer_target_from_now:
        base_d, t_inferred = _infer_target_from_utc_now()
        targets = [t_inferred]
    else:
        base_d = _date_from_arg(args.date_et)
        targets = _parse_targets_et(args.targets_et)
        if not targets:
            raise SystemExit("No targets provided")

    dates = [base_d - timedelta(days=i) for i in range(args.days)]
    all_rows: list[dict] = []
    all_turn_metrics: list[dict] = []
    missing: list[tuple[str, str]] = []
    pred_source_counts: dict[str, int] = {"points_exact": 0, "points_nearest": 0, "target_price": 0}

    # Batch fetch intraday forecasts for date range (when source=intraday)
    forecast_index: dict[tuple[str, str], list[tuple[datetime, dict]]] = {}
    if args.forecast_source == "intraday":
        start_utc = datetime(dates[-1].year, dates[-1].month, dates[-1].day, 0, 0, 0, tzinfo=UTC)
        end_utc = datetime(
            dates[0].year, dates[0].month, dates[0].day, 23, 59, 59, 999999, tzinfo=UTC
        )
        batch = _fetch_intraday_forecasts_batch(
            symbols, args.timeframe, start_utc, end_utc
        )
        horizon = TIMEFRAME_TO_HORIZON.get(args.timeframe, "15m")
        for (sym, h), rows in batch.items():
            # Sort by created_at asc for binary search
            sorted_rows: list[tuple[datetime, dict]] = []
            for r in rows:
                ct = _parse_created_at(r)
                if ct is not None:
                    sorted_rows.append((ct, r))
            sorted_rows.sort(key=lambda x: x[0])
            forecast_index[(sym, h)] = sorted_rows

    for d in dates:
        rows_out: list[dict] = []
        for sym in symbols:
            symbol_id = _get_symbol_id(sym)
            if not symbol_id:
                missing.append((sym, "symbol_missing"))
                continue

            prev_realized: float | None = None
            prev_realized_direction: int | None = None
            for t_et in targets:
                target_utc = _target_dt_utc(d, t_et)

                if args.forecast_source == "intraday":
                    pred, pred_source = _predicted_close_from_intraday(
                        forecast_index, sym, args.timeframe, target_utc
                    )
                    if pred is not None and pred_source:
                        pred_source_counts[pred_source] = pred_source_counts.get(pred_source, 0) + 1
                else:
                    pred = _fetch_close(
                        symbol_id=symbol_id,
                        ts_utc=target_utc,
                        timeframe=args.timeframe,
                        is_forecast=True,
                        provider_preference=[None],
                    )
                    pred_source = None

                real = _fetch_close(
                    symbol_id=symbol_id,
                    ts_utc=target_utc,
                    timeframe=args.timeframe,
                    is_forecast=False,
                    provider_preference=["alpaca", "polygon", "yfinance", None],
                    tolerance_minutes=args.realized_tolerance_minutes,
                )

                if pred is None:
                    missing.append((sym, f"missing_forecast@{target_utc.isoformat()}"))
                if real is None:
                    missing.append((sym, f"missing_realized@{target_utc.isoformat()}"))

                if pred is None:
                    continue

                # Include row when we have pred but no real, if --include-missing-realized
                if real is None:
                    if not args.include_missing_realized:
                        continue
                    row_dict = {
                        "symbol": sym,
                        "target_ts_utc": target_utc.isoformat(),
                        "target_time_et": f"{t_et.hour:02d}:{t_et.minute:02d}",
                        "predicted_close": pred.close,
                        "realized_close": None,
                        "error_abs": None,
                        "error_pct": None,
                        "predicted_direction": 0,
                        "realized_direction": 0,
                        "direction_correct": "",
                        "turn_detected": False,
                        "pred_provider": pred.provider,
                        "real_provider": None,
                        "missing_realized": True,
                    }
                    if pred_source is not None:
                        row_dict["pred_source"] = pred_source
                    rows_out.append(row_dict)
                    prev_realized = None
                    prev_realized_direction = None
                    continue

                error_abs = abs(real.close - pred.close)
                error_pct = (error_abs / pred.close) if pred.close != 0 else None

                # Direction vs previous realized (for turn metrics)
                pred_dir = 0
                real_dir = 0
                direction_correct = ""  # Empty for first target per symbol
                turn_detected = False
                if prev_realized is not None:
                    pred_dir = 1 if pred.close > prev_realized else (-1 if pred.close < prev_realized else 0)
                    real_dir = 1 if real.close > prev_realized else (-1 if real.close < prev_realized else 0)
                    direction_correct = 1 if (pred_dir == real_dir and pred_dir != 0) else 0
                    turn_detected = prev_realized_direction is not None and real_dir != prev_realized_direction and prev_realized_direction != 0

                row_dict = {
                    "symbol": sym,
                    "target_ts_utc": target_utc.isoformat(),
                    "target_time_et": f"{t_et.hour:02d}:{t_et.minute:02d}",
                    "predicted_close": pred.close,
                    "realized_close": real.close,
                    "error_abs": error_abs,
                    "error_pct": error_pct,
                    "predicted_direction": pred_dir,
                    "realized_direction": real_dir,
                    "direction_correct": direction_correct,
                    "turn_detected": turn_detected,
                    "pred_provider": pred.provider,
                    "real_provider": real.provider,
                }
                if args.include_missing_realized:
                    row_dict["missing_realized"] = False
                if pred_source is not None:
                    row_dict["pred_source"] = pred_source
                rows_out.append(row_dict)

                prev_realized = real.close
                prev_realized_direction = real_dir

        turn_metrics = _compute_turn_metrics(rows_out, d)
        for r in turn_metrics:
            r["date"] = d.isoformat()
            all_turn_metrics.append(r)
        for r in rows_out:
            if args.days > 1:
                r["date"] = d.isoformat()
            all_rows.append(r)

    rows_out = all_rows
    fieldnames = [
        "symbol",
        "target_ts_utc",
        "target_time_et",
        "predicted_close",
        "realized_close",
        "error_abs",
        "error_pct",
        "predicted_direction",
        "realized_direction",
        "direction_correct",
        "turn_detected",
        "pred_provider",
        "real_provider",
    ]
    if args.forecast_source == "intraday":
        fieldnames.append("pred_source")
    if args.include_missing_realized:
        fieldnames.append("missing_realized")
    if args.days > 1:
        fieldnames = ["date"] + fieldnames
    out_path = args.out
    out_dir = out_path.rsplit("/", 1)[0] if "/" in out_path else "."
    os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    # Write turn metrics (flip_lag, post_turn_directional_accuracy)
    turn_path = out_path.replace(".csv", "_turn_metrics.csv")
    if all_turn_metrics:
        turn_fieldnames = ["date", "symbol", "flip_lag_mean", "post_turn_directional_accuracy", "n_turns", "n_post_turn"]
        with open(turn_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=turn_fieldnames)
            w.writeheader()
            for r in all_turn_metrics:
                w.writerow(r)
        print(f"Turn metrics: {turn_path}")

    print("\nHourly Canary Summary")
    if args.days == 1:
        print(f"Date (ET): {dates[0].isoformat()}")
    else:
        print(f"Dates (ET): {dates[-1].isoformat()} ... {dates[0].isoformat()} ({args.days} days)")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Forecast source: {args.forecast_source}")
    targets_str = f"{targets[0].hour:02d}:{targets[0].minute:02d}" if args.infer_target_from_now else args.targets_et
    print(f"Targets (ET): {targets_str}")
    print(f"Rows: {len(rows_out)}")
    if args.forecast_source == "intraday" and any(pred_source_counts.values()):
        print(f"Pred source: points_exact={pred_source_counts.get('points_exact', 0)}, "
              f"points_nearest={pred_source_counts.get('points_nearest', 0)}, "
              f"target_price={pred_source_counts.get('target_price', 0)}")
    if args.realized_tolerance_minutes > 0:
        print(f"Realized tolerance: ±{args.realized_tolerance_minutes} min")
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
