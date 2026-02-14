#!/usr/bin/env python3
"""
Blind Intraday Day-Replay Validator.

Mimics live 15-minute updates for a replay day, scores 1-hour-ahead outcomes
from realized m15 bars, with zero DB writes. Uses run_intraday_forecast_in_memory
for in-memory forecasts.

Session bounds use America/New_York (market-native). 1h-ahead target = close of
the 4th m15 bar after decision time t, i.e. bar starting at t+45min. We only
score timestamps where that target bar exists (t <= session_end - 1h).

Usage:
    python scripts/blind_intraday_replay_validation.py --symbols AAPL --date-et 2025-02-11
    python scripts/blind_intraday_replay_validation.py --symbols AAPL,MSFT,SPY --date-et 2025-02-10 --fail-on-missing-realized
"""

import argparse
import csv
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.supabase_db import db  # noqa: E402
from src.intraday_forecast_job import run_intraday_forecast_in_memory  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# US regular session: 9:30 - 16:00 ET (market-native, DST-safe)
MARKET_OPEN_ET = (9, 30)
MARKET_CLOSE_ET = (16, 0)
BAR_INTERVAL_MINUTES = 15
# 1h-ahead target = bar at t+45min; last scorable t = session_end - 1h
HORIZON_MINUTES = 45

# Historical lookback: need enough for indicators + min_training_bars (~60)
FETCH_LIMIT = 3000
MIN_BARS_FOR_REPLAY = 60  # matches HORIZON_CONFIG["15m"]["min_training_bars"]


def _parse_symbols(s: str) -> list[str]:
    return [x.strip().upper() for x in (s or "").split(",") if x.strip()]


def _date_from_arg(s: str | None) -> date:
    if s and s.strip():
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    return datetime.now(ET).date()


def _replay_day_bounds(d: date) -> tuple[datetime, datetime]:
    """Return (start_utc, end_utc) for replay day trading session (9:30-16:00 ET)."""
    start_et = datetime(
        d.year, d.month, d.day,
        MARKET_OPEN_ET[0], MARKET_OPEN_ET[1], 0, tzinfo=ET
    )
    end_et = datetime(
        d.year, d.month, d.day,
        MARKET_CLOSE_ET[0], MARKET_CLOSE_ET[1], 0, tzinfo=ET
    )
    return start_et.astimezone(UTC), end_et.astimezone(UTC)


def _replay_timestamps(d: date) -> list[datetime]:
    """
    Generate m15 decision timestamps for the trading day (bar start times). Only
    includes timestamps where the 1h-ahead target bar (t+45min) exists within the
    session, so we don't penalize end-of-day inevitables.
    """
    start_et = datetime(
        d.year, d.month, d.day,
        MARKET_OPEN_ET[0], MARKET_OPEN_ET[1], 0, tzinfo=ET
    )
    end_et = datetime(
        d.year, d.month, d.day,
        MARKET_CLOSE_ET[0], MARKET_CLOSE_ET[1], 0, tzinfo=ET
    )
    # Last scorable t: target_bar_ts = t+45min must be <= last bar start (15:45 ET)
    last_bar_start_et = end_et - timedelta(minutes=BAR_INTERVAL_MINUTES)
    last_scorable_et = last_bar_start_et - timedelta(minutes=HORIZON_MINUTES)
    timestamps = []
    t = start_et
    while t <= last_scorable_et:
        timestamps.append(t.astimezone(UTC))
        t += timedelta(minutes=BAR_INTERVAL_MINUTES)
    return timestamps


def _load_m15_bars_supabase(symbol: str, replay_date: date) -> pd.DataFrame:
    """
    Load m15 bars from Supabase with adequate historical lookback.

    Uses end_ts = replay_day_end + 1h and limit=FETCH_LIMIT.
    fetch_ohlc_bars returns timezone-naive; we treat as UTC-naive.
    """
    _, end_utc = _replay_day_bounds(replay_date)
    end_utc = end_utc + timedelta(hours=1)

    df = db.fetch_ohlc_bars(
        symbol,
        timeframe="m15",
        limit=FETCH_LIMIT,
        end_ts=end_utc,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def _preflight_check(
    df: pd.DataFrame,
    symbol: str,
    replay_date: date,
    replay_ts_list: list[datetime],
    min_bars: int = MIN_BARS_FOR_REPLAY,
) -> tuple[bool, str]:
    """
    Assert we have realized m15 bars for replay date and 1h-ahead target bars.
    Target bar = t + 45min (4th bar's start; its close is the 1h-ahead outcome).

    Returns (ok, message).
    """
    if df.empty or len(df) < min_bars:
        return False, f"{symbol}: insufficient bars ({len(df)} < {min_bars})"

    start_utc, end_utc = _replay_day_bounds(replay_date)
    day_bars = df[(df["ts"] >= start_utc) & (df["ts"] <= end_utc)]
    if len(day_bars) < 5:
        return (
            False,
            f"{symbol}: only {len(day_bars)} m15 bars on replay date "
            f"(need 5+). DB may lack data for {replay_date}. "
            "Try a different date, backfill m15, or --skip-preflight.",
        )

    # Warn if target bars missing (ingestion gaps; replay_ts_list already excludes EOD inevitables)
    missing = sum(
        1
        for t in replay_ts_list
        if not (df["ts"] == (t + timedelta(minutes=HORIZON_MINUTES))).any()
    )
    if missing > 0:
        logger.warning(
            "%s: %d/%d target bars (t+45min) missing - ingestion gap, will mark missing_realized",
            symbol,
            missing,
            len(replay_ts_list),
        )
    return True, "ok"


def _lookup_realized_close(
    df: pd.DataFrame,
    target_ts: datetime,
) -> float | None:
    """Lookup close of m15 bar at target_ts from preloaded DataFrame."""
    if target_ts.tzinfo is None:
        target_ts = target_ts.replace(tzinfo=UTC)
    match = df[df["ts"] == target_ts]
    if match.empty:
        return None
    return float(match["close"].iloc[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Blind intraday day-replay validation (1h-ahead from m15 bars)"
    )
    parser.add_argument(
        "--symbols",
        default="AAPL",
        help="Comma-separated symbols (default: AAPL)",
    )
    parser.add_argument(
        "--date-et",
        default="",
        help="Replay date YYYY-MM-DD (default: today ET). Session bounds: 9:30-16:00 ET.",
    )
    parser.add_argument(
        "--source",
        choices=["supabase", "alpaca"],
        default="supabase",
        help="Bar source (default: supabase)",
    )
    parser.add_argument(
        "--output",
        default="validation_results/blind_intraday_replay.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--fail-on-missing-realized",
        action="store_true",
        help="Hard-fail when realized coverage drops below 90%%",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip preflight bar-existence check (use for debugging)",
    )
    parser.add_argument(
        "--min-bars",
        type=int,
        default=60,
        help="Minimum m15 bars required (default: 60). Lower for testing with sparse data.",
    )
    args = parser.parse_args()

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        logger.error("No symbols provided")
        return 1

    replay_date = _date_from_arg(args.date_et)
    replay_ts_list = _replay_timestamps(replay_date)

    logger.info("Blind Intraday Replay Validation")
    logger.info("  Date: %s (session 9:30-16:00 ET)", replay_date.isoformat())
    logger.info("  Symbols: %s", ", ".join(symbols))
    logger.info("  Source: %s", args.source)
    logger.info("  Replay timestamps: %d", len(replay_ts_list))

    if args.source != "supabase":
        logger.error("Only --source supabase is implemented")
        return 1

    all_rows: list[dict] = []
    missing_realized_count = 0
    total_predictions = 0

    for symbol in symbols:
        df = _load_m15_bars_supabase(symbol, replay_date)
        if df.empty:
            logger.error("%s: no m15 bars loaded", symbol)
            if args.fail_on_missing_realized:
                return 1
            continue

        if not args.skip_preflight:
            ok, msg = _preflight_check(
                df, symbol, replay_date, replay_ts_list, min_bars=args.min_bars
            )
            if not ok:
                logger.error("Preflight failed: %s", msg)
                if args.fail_on_missing_realized:
                    return 1
                continue

        prev_realized: float | None = None

        for t in tqdm(replay_ts_list, desc=symbol, leave=False):
            df_at_t = df[df["ts"] <= t]
            if len(df_at_t) < args.min_bars:
                continue
            forecast = run_intraday_forecast_in_memory(
                df,
                symbol,
                horizon="15m",
                cutoff_ts=t,
                dry_run=True,
                min_bars_override=args.min_bars,
            )

            if forecast is None:
                continue

            predicted_close = forecast["target_price"]
            # 1h ahead = close of 4th m15 bar; target bar starts at t+45min
            target_bar_ts = t + timedelta(minutes=HORIZON_MINUTES)
            realized_close = _lookup_realized_close(df, target_bar_ts)
            missing_realized = realized_close is None

            if missing_realized:
                missing_realized_count += 1

            total_predictions += 1

            row: dict = {
                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "symbol": symbol,
                "predicted_close": round(predicted_close, 4),
                "realized_close": round(realized_close, 4) if realized_close is not None else "",
                "error_pct": "",
                "direction_correct": "",
                "missing_realized": "true" if missing_realized else "false",
            }

            if not missing_realized and realized_close is not None:
                error_pct = abs(predicted_close - realized_close) / predicted_close
                row["error_pct"] = round(error_pct, 6)

                pred_dir = 0
                real_dir = 0
                if prev_realized is not None:
                    pred_dir = 1 if predicted_close > prev_realized else (-1 if predicted_close < prev_realized else 0)
                    real_dir = 1 if realized_close > prev_realized else (-1 if realized_close < prev_realized else 0)
                    if pred_dir != 0 and real_dir != 0:
                        row["direction_correct"] = 1 if pred_dir == real_dir else 0

                prev_realized = realized_close

            all_rows.append(row)

    if args.fail_on_missing_realized and total_predictions > 0:
        coverage = 1.0 - (missing_realized_count / total_predictions)
        if coverage < 0.90:
            logger.error(
                "Coverage %.1f%% < 90%% (missing_realized=%d, total=%d)",
                coverage * 100,
                missing_realized_count,
                total_predictions,
            )
            return 1

    out_path = args.output
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    fieldnames = [
        "timestamp",
        "symbol",
        "predicted_close",
        "realized_close",
        "error_pct",
        "direction_correct",
        "missing_realized",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    logger.info("Wrote %d rows to %s", len(all_rows), out_path)
    if total_predictions > 0:
        coverage = 1.0 - (missing_realized_count / total_predictions)
        logger.info("Realized coverage: %.1f%%", coverage * 100)
        rows_with_realized = [r for r in all_rows if r.get("realized_close") != ""]
        if rows_with_realized:
            errors = [float(r["error_pct"]) for r in rows_with_realized if r.get("error_pct")]
            if errors:
                logger.info("Mean error_pct: %.4f%%", sum(errors) / len(errors) * 100)
            correct = sum(1 for r in rows_with_realized if r.get("direction_correct") == 1)
            total_dc = sum(1 for r in rows_with_realized if r.get("direction_correct") in (0, 1))
            if total_dc > 0:
                logger.info("Direction accuracy: %.1f%% (%d/%d)", correct / total_dc * 100, correct, total_dc)
    elif not all_rows:
        logger.warning("No predictions generated (insufficient bars or preflight failed)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
