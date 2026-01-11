"""
ML Forecast Staleness Monitoring.

Alerts if ML forecasts are older than the configured threshold.
"""

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db

logger = logging.getLogger(__name__)

# Default threshold: 6 hours
STALENESS_THRESHOLD_HOURS = 6


@dataclass
class StalenessResult:
    """Result of staleness check."""

    status: str  # 'OK', 'STALE', 'CRITICAL'
    message: str
    last_forecast: datetime | None
    hours_old: float | None

    @property
    def is_ok(self) -> bool:
        return self.status == "OK"

    @property
    def icon(self) -> str:
        icons = {"OK": "✅", "STALE": "⚠️", "CRITICAL": "🔴"}
        return icons.get(self.status, "❓")


def check_forecast_staleness(
    threshold_hours: float = STALENESS_THRESHOLD_HOURS,
) -> StalenessResult:
    """
    Check if ML forecasts are stale.

    Args:
        threshold_hours: Hours after which forecasts are stale

    Returns:
        StalenessResult with status and details
    """
    try:
        # Get most recent forecast timestamp
        response = (
            db.client.table("ml_forecasts")
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not response.data:
            return StalenessResult(
                status="CRITICAL",
                message="No forecasts found in database",
                last_forecast=None,
                hours_old=None,
            )

        # Parse timestamp
        created_at = response.data[0]["created_at"]
        if isinstance(created_at, str):
            # Handle ISO format with Z suffix
            created_at = created_at.replace("Z", "+00:00")
            last_forecast = datetime.fromisoformat(created_at)
        else:
            last_forecast = created_at

        # Ensure timezone-aware
        if last_forecast.tzinfo is None:
            last_forecast = last_forecast.replace(tzinfo=timezone.utc)

        # Calculate age
        now = datetime.now(timezone.utc)
        age = now - last_forecast
        hours_old = age.total_seconds() / 3600

        # Determine status
        if hours_old > threshold_hours * 2:
            status = "CRITICAL"
            message = (
                f"Forecasts are critically stale: {hours_old:.1f}h old "
                f"(threshold: {threshold_hours}h)"
            )
        elif hours_old > threshold_hours:
            status = "STALE"
            message = (
                f"Forecasts are stale: {hours_old:.1f}h old " f"(threshold: {threshold_hours}h)"
            )
        else:
            status = "OK"
            message = f"Forecasts are fresh ({hours_old:.1f}h old)"

        return StalenessResult(
            status=status,
            message=message,
            last_forecast=last_forecast,
            hours_old=hours_old,
        )

    except Exception as e:
        logger.error(f"Error checking forecast staleness: {e}")
        return StalenessResult(
            status="CRITICAL",
            message=f"Error checking staleness: {e}",
            last_forecast=None,
            hours_old=None,
        )


def check_all_staleness() -> dict[str, StalenessResult]:
    """
    Check staleness for all data types.

    Returns:
        Dict mapping data type to StalenessResult
    """
    results = {}

    # Check ML forecasts
    results["ml_forecasts"] = check_forecast_staleness()

    # Check options ranks
    try:
        response = (
            db.client.table("options_ranks")
            .select("created_at")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            created_at = response.data[0]["created_at"]
            if isinstance(created_at, str):
                created_at = created_at.replace("Z", "+00:00")
                last_rank = datetime.fromisoformat(created_at)
            else:
                last_rank = created_at

            if last_rank.tzinfo is None:
                last_rank = last_rank.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            hours_old = (now - last_rank).total_seconds() / 3600

            # Options ranks should be updated daily (24h threshold)
            if hours_old > 48:
                status = "CRITICAL"
            elif hours_old > 24:
                status = "STALE"
            else:
                status = "OK"

            results["options_ranks"] = StalenessResult(
                status=status,
                message=f"Options ranks are {hours_old:.1f}h old",
                last_forecast=last_rank,
                hours_old=hours_old,
            )
        else:
            results["options_ranks"] = StalenessResult(
                status="CRITICAL",
                message="No options ranks found",
                last_forecast=None,
                hours_old=None,
            )
    except Exception as e:
        results["options_ranks"] = StalenessResult(
            status="CRITICAL",
            message=f"Error: {e}",
            last_forecast=None,
            hours_old=None,
        )

    return results


def main() -> None:
    """CLI entry point for staleness check."""
    import argparse

    parser = argparse.ArgumentParser(description="Check ML forecast staleness")
    parser.add_argument(
        "--threshold",
        type=float,
        default=STALENESS_THRESHOLD_HOURS,
        help="Staleness threshold in hours",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all data types",
    )
    args = parser.parse_args()

    if args.all:
        results = check_all_staleness()
        print("\n📊 DATA STALENESS REPORT")
        print("=" * 40)

        any_stale = False
        for name, result in results.items():
            print(f"{result.icon} {name}: {result.message}")
            if not result.is_ok:
                any_stale = True

        if any_stale:
            sys.exit(1)
    else:
        result = check_forecast_staleness(args.threshold)
        print(f"{result.icon} {result.message}")

        if not result.is_ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
