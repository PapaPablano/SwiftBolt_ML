#!/usr/bin/env python3
"""
Kalman health aggregator: analyze synthesis_data.kalman.health from ml_forecasts_intraday.

Answers:
  (1) How often Kalman is disabled by converged=False vs exog_missing_rate>cutoff
  (2) What cutoff keeps "disabled rate" under target (e.g. <20%)

Output: validation_results/kalman_health_summary.csv
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.supabase_db import db  # noqa: E402

CST = ZoneInfo("America/Chicago")
UTC = timezone.utc

# Cutoff candidates for exog_missing_rate (recommend smallest that keeps disabled < target_pct)
CUTOFF_CANDIDATES = [0.15, 0.20, 0.25]


def _date_from_arg(s: str | None) -> date:
    if s and s.strip():
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    return datetime.now(CST).date()


PAGE_SIZE = 1000


def fetch_intraday_forecasts(start_date: date, end_date: date) -> list[dict]:
    """Fetch ml_forecasts_intraday rows for date range with synthesis_data.
    Paginates to avoid under-fetching (PostgREST default limit ~1000)."""
    start_utc = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
    end_utc = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999, tzinfo=UTC
    )
    start_iso = start_utc.isoformat()
    end_iso = end_utc.isoformat()

    all_data: list[dict] = []
    cursor_created_at: str | None = None
    try:
        while True:
            q = (
                db.client.table("ml_forecasts_intraday")
                .select("id,symbol,horizon,created_at,synthesis_data")
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
        return all_data
    except Exception as e:
        print(f"Error fetching ml_forecasts_intraday: {e}", file=sys.stderr)
        return []


def parse_kalman_health(row: dict) -> tuple[bool, float | None, str | None]:
    """
    Extract (converged, exog_missing_rate, reason) from synthesis_data.kalman.health.
    Returns (converged, exog_missing_rate, None) if parseable; (False, None, "no_kalman") etc.
    """
    synth = row.get("synthesis_data")
    if not synth or not isinstance(synth, dict):
        return (False, None, "no_synthesis_data")
    kalman = synth.get("kalman")
    if not kalman or not isinstance(kalman, dict):
        return (False, None, "no_kalman")
    health = kalman.get("health")
    if not health or not isinstance(health, dict):
        return (False, None, "no_health")
    converged = bool(health.get("converged", False))
    exog_missing_rate = health.get("exog_missing_rate")
    if exog_missing_rate is not None:
        try:
            exog_missing_rate = float(exog_missing_rate)
        except (TypeError, ValueError):
            exog_missing_rate = None
    return (converged, exog_missing_rate, None)


def aggregate(
    rows: list[dict],
    exog_cutoff: float = 0.20,
) -> dict[tuple[str, str, str], dict]:
    """
    Aggregate by (date, symbol, horizon).
    Key: (date_iso, symbol, horizon)
    Value: n_total, n_kalman_present, n_blend_enabled, n_disabled_not_converged,
           n_disabled_exog_missing, exog_rates list for p50/p90/p95
    """
    agg: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {
            "n_total": 0,
            "n_kalman_present": 0,
            "n_blend_enabled": 0,
            "n_disabled_not_converged": 0,
            "n_disabled_exog_missing": 0,
            "exog_rates": [],
        }
    )

    for row in rows:
        created = row.get("created_at")
        if not created:
            continue
        try:
            s = str(created).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dt_cst = dt.astimezone(CST)
            date_iso = dt_cst.date().isoformat()
        except Exception:
            continue
        symbol = str(row.get("symbol", "")).upper()
        horizon = str(row.get("horizon", ""))
        key = (date_iso, symbol, horizon)

        agg[key]["n_total"] += 1

        converged, exog_missing_rate, reason = parse_kalman_health(row)
        if reason is not None:
            continue

        agg[key]["n_kalman_present"] += 1

        if not converged:
            agg[key]["n_disabled_not_converged"] += 1
            continue

        if exog_missing_rate is not None:
            agg[key]["exog_rates"].append(exog_missing_rate)
            if exog_missing_rate > exog_cutoff:
                agg[key]["n_disabled_exog_missing"] += 1
                continue

        agg[key]["n_blend_enabled"] += 1

    return dict(agg)


def compute_percentiles(rates: list[float]) -> tuple[float | None, float | None, float | None]:
    """Return (p50, p90, p95) or (None, None, None) if empty."""
    if not rates:
        return (None, None, None)
    s = sorted(rates)
    n = len(s)
    p50 = s[int(0.50 * (n - 1))] if n > 0 else None
    p90 = s[int(0.90 * (n - 1))] if n > 0 else None
    p95 = s[int(0.95 * (n - 1))] if n > 0 else None
    return (p50, p90, p95)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Aggregate Kalman health from ml_forecasts_intraday for cutoff tuning"
    )
    ap.add_argument("--start", default="", help="Start date YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("--end", default="", help="End date YYYY-MM-DD (default: today CST)")
    ap.add_argument("--cutoff", type=float, default=0.20, help="exog_missing_rate cutoff (default: 0.20)")
    ap.add_argument(
        "--out",
        default="validation_results/kalman_health_summary.csv",
        help="Output CSV path",
    )
    ap.add_argument(
        "--recommend-cutoffs",
        action="store_true",
        help="Print recommended cutoff candidates (0.15/0.20/0.25) with disabled %%",
    )
    args = ap.parse_args()

    end_d = _date_from_arg(args.end)
    start_d = (
        _date_from_arg(args.start)
        if args.start
        else end_d - timedelta(days=7)
    )
    if start_d > end_d:
        start_d, end_d = end_d, start_d

    rows = fetch_intraday_forecasts(start_d, end_d)
    if not rows:
        print(f"No ml_forecasts_intraday rows for {start_d}..{end_d}", file=sys.stderr)
        return 1

    agg = aggregate(rows, exog_cutoff=args.cutoff)
    if not agg:
        print("No Kalman health data in synthesis_data", file=sys.stderr)
        return 1

    out_path = args.out
    out_dir = out_path.rsplit("/", 1)[0] if "/" in out_path else "."
    os.makedirs(out_dir, exist_ok=True)

    fieldnames = [
        "date",
        "symbol",
        "horizon",
        "n_total",
        "n_kalman_present",
        "n_blend_enabled",
        "n_disabled_not_converged",
        "n_disabled_exog_missing",
        "exog_missing_rate_p50",
        "exog_missing_rate_p90",
        "exog_missing_rate_p95",
    ]

    out_rows = []
    for (date_iso, symbol, horizon), v in sorted(agg.items()):
        p50, p90, p95 = compute_percentiles(v["exog_rates"])
        out_rows.append(
            {
                "date": date_iso,
                "symbol": symbol,
                "horizon": horizon,
                "n_total": v["n_total"],
                "n_kalman_present": v["n_kalman_present"],
                "n_blend_enabled": v["n_blend_enabled"],
                "n_disabled_not_converged": v["n_disabled_not_converged"],
                "n_disabled_exog_missing": v["n_disabled_exog_missing"],
                "exog_missing_rate_p50": round(p50, 4) if p50 is not None else "",
                "exog_missing_rate_p90": round(p90, 4) if p90 is not None else "",
                "exog_missing_rate_p95": round(p95, 4) if p95 is not None else "",
            }
        )

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"Wrote: {out_path} ({len(out_rows)} rows)")

    if args.recommend_cutoffs:
        # Compute disabled-by-exog rates (denominator = converged + measurable exog_missing_rate)
        n_eligible = 0
        for row in rows:
            converged, exog_missing_rate, reason = parse_kalman_health(row)
            if reason is None and converged and exog_missing_rate is not None:
                n_eligible += 1
        print(
            "\nCutoff recommendations (target: disable <20% of eligible runs):"
        )
        print(
            f"  Denominator: {n_eligible} runs (converged + measurable exog_missing_rate)"
        )
        for cutoff in CUTOFF_CANDIDATES:
            n_disabled_exog = 0
            for row in rows:
                converged, exog_missing_rate, reason = parse_kalman_health(row)
                if (
                    reason is None
                    and exog_missing_rate is not None
                    and converged
                    and exog_missing_rate > cutoff
                ):
                    n_disabled_exog += 1
            disabled_pct = (
                (n_disabled_exog / n_eligible * 100) if n_eligible > 0 else 0
            )
            status = "OK" if disabled_pct < 20 else ">20%"
            print(
                f"  cutoff={cutoff:.2f}: disables {n_disabled_exog}/{n_eligible} "
                f"({disabled_pct:.1f}%) by exog_missing ({status})"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
