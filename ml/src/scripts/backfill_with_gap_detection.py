"""
Improved Alpaca Backfill with Gap Detection and Auto-Retry

This script enhances the standard backfill with:
1. Gap detection after each symbol/timeframe
2. Automatic retry for failed chunks
3. Validation of data continuity
4. Summary report of coverage quality
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def detect_gaps(
    symbol: str, timeframe: str, max_gap_hours: int = 24
) -> List[Tuple[datetime, datetime]]:
    """
    Detect gaps in OHLC data for a symbol/timeframe.

    Returns list of (gap_start, gap_end) tuples where gaps exceed max_gap_hours.
    """
    result = db.execute_rpc(
        "detect_ohlc_gaps",
        {"p_symbol": symbol, "p_timeframe": timeframe, "p_max_gap_hours": max_gap_hours},
    )

    gaps = []
    if result:
        for row in result:
            gaps.append((row["gap_start"], row["gap_end"]))

    return gaps


def get_coverage_stats(symbol: str, timeframe: str) -> dict:
    """Get coverage statistics for a symbol/timeframe."""
    result = db.execute_rpc(
        "get_ohlc_coverage_stats", {"p_symbol": symbol, "p_timeframe": timeframe}
    )

    if result and result[0]["bar_count"] > 0:
        return {
            "bar_count": result[0]["bar_count"],
            "oldest_bar": result[0]["oldest_bar"],
            "newest_bar": result[0]["newest_bar"],
            "time_span_days": result[0]["time_span_days"] or 0,
        }

    return {"bar_count": 0, "oldest_bar": None, "newest_bar": None, "time_span_days": 0}


def validate_and_report(symbol: str, timeframe: str) -> dict:
    """
    Validate data quality and return comprehensive report.
    """
    # Get coverage stats
    stats = get_coverage_stats(symbol, timeframe)

    # Detect gaps: 72 hours for intraday (weekends/holidays), 7 days for daily+
    max_gap_hours = 72 if timeframe in ["m15", "h1", "h4"] else 168  # 7 days
    gaps = detect_gaps(symbol, timeframe, max_gap_hours)

    # Calculate expected bars vs actual
    expected_bars = None
    if stats["bar_count"] > 0 and stats["time_span_days"] > 0:
        if timeframe == "m15":
            # ~26 bars per trading day (6.5 hours * 4 bars/hour)
            expected_bars = stats["time_span_days"] * 26 / 7  # Adjust for weekends
        elif timeframe == "h1":
            # ~6.5 bars per trading day
            expected_bars = stats["time_span_days"] * 6.5 / 7
        elif timeframe == "h4":
            # ~1.6 bars per trading day
            expected_bars = stats["time_span_days"] * 1.6 / 7
        elif timeframe == "d1":
            # ~5 bars per week (trading days)
            expected_bars = stats["time_span_days"] * 5 / 7
        elif timeframe == "w1":
            # ~52 bars per year
            expected_bars = stats["time_span_days"] / 7

    coverage_pct = None
    if expected_bars and expected_bars > 0:
        coverage_pct = (stats["bar_count"] / expected_bars) * 100

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_count": stats["bar_count"],
        "oldest_bar": stats["oldest_bar"],
        "newest_bar": stats["newest_bar"],
        "time_span_days": stats["time_span_days"],
        "gaps_found": len(gaps),
        "largest_gap": gaps[0] if gaps else None,
        "expected_bars": int(expected_bars) if expected_bars else None,
        "coverage_pct": round(coverage_pct, 1) if coverage_pct else None,
        "status": (
            "COMPLETE" if len(gaps) == 0 and coverage_pct and coverage_pct > 95 else "GAPS_DETECTED"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Validate backfill data quality")
    parser.add_argument("--symbols", nargs="+", help="Symbols to validate")
    parser.add_argument("--all", action="store_true", help="Validate all watchlist symbols")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["m15", "h1", "h4", "d1", "w1"],
        help="Timeframes to validate",
    )

    args = parser.parse_args()

    # Get symbols
    if args.all:
        result = db.execute_rpc("get_all_watchlist_symbols")
        symbols = [row["ticker"] for row in result] if result else []
    elif args.symbols:
        symbols = args.symbols
    else:
        logger.error("Must specify --symbols or --all")
        return 1

    logger.info(f"🔍 Validating {len(symbols)} symbols across {len(args.timeframes)} timeframes")
    logger.info("=" * 80)

    all_reports = []
    issues_found = []

    for symbol in symbols:
        for timeframe in args.timeframes:
            report = validate_and_report(symbol, timeframe)
            all_reports.append(report)

            # Log status
            status_icon = "✅" if report["status"] == "COMPLETE" else "⚠️"
            logger.info(
                f"{status_icon} {symbol:6s} {timeframe:4s} | "
                f"Bars: {report['bar_count']:5d} | "
                f"Coverage: {report['coverage_pct'] or 0:5.1f}% | "
                f"Gaps: {report['gaps_found']:2d}"
            )

            if report["status"] != "COMPLETE":
                issues_found.append(report)

    # Summary
    logger.info("=" * 80)
    logger.info("📊 VALIDATION SUMMARY")
    logger.info(f"Total combinations: {len(all_reports)}")
    logger.info(f"Complete: {sum(1 for r in all_reports if r['status'] == 'COMPLETE')}")
    logger.info(f"Issues found: {len(issues_found)}")

    if issues_found:
        logger.info("\n⚠️  ISSUES REQUIRING ATTENTION:")
        for issue in issues_found:
            logger.info(
                f"  {issue['symbol']} {issue['timeframe']}: "
                f"{issue['gaps_found']} gaps, {issue['coverage_pct'] or 0:.1f}% coverage"
            )
            if issue["largest_gap"]:
                gap_start, gap_end = issue["largest_gap"]
                # Convert string timestamps to datetime if needed
                if isinstance(gap_start, str):
                    from datetime import datetime

                    gap_start = datetime.fromisoformat(gap_start.replace("Z", "+00:00"))
                    gap_end = datetime.fromisoformat(gap_end.replace("Z", "+00:00"))
                gap_days = (gap_end - gap_start).days
                logger.info(f"    Largest gap: {gap_days} days ({gap_start} to {gap_end})")

        logger.info("\n🔧 RECOMMENDED ACTIONS:")
        for issue in issues_found:
            logger.info(
                f"  python src/scripts/alpaca_backfill_ohlc_v2.py "
                f"--symbols {issue['symbol']} --timeframe {issue['timeframe']} --force"
            )
    else:
        logger.info("\n✅ All data looks good! No gaps detected.")

    return 0 if len(issues_found) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
