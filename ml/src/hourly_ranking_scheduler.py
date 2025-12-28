#!/usr/bin/env python3
"""
Hourly Ranking Scheduler - Ensures watchlist stocks have fresh Momentum Framework rankings.

This script:
1. Queues ranking jobs for all watchlist symbols (or only stale ones)
2. Runs the ranking worker to process all queued jobs
3. Can be run via cron, GitHub Actions, or manually

Usage:
    python src/hourly_ranking_scheduler.py              # Queue all watchlist symbols
    python src/hourly_ranking_scheduler.py --stale      # Only queue symbols with stale rankings
    python src/hourly_ranking_scheduler.py --no-process # Queue only, don't process
    python src/hourly_ranking_scheduler.py --symbols AAPL NVDA TSLA  # Specific symbols

Cron Example (every hour at :05):
    5 * * * * cd /path/to/ml && python src/hourly_ranking_scheduler.py >> logs/ranking.log 2>&1
"""

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def queue_all_watchlist_rankings() -> int:
    """Queue ranking jobs for all watchlist symbols.

    Returns:
        Number of symbols queued
    """
    try:
        result = db.client.rpc("queue_all_watchlist_ranking_jobs").execute()
        count = result.data if result.data else 0
        logger.info(f"Queued ranking jobs for {count} watchlist symbols")
        return count
    except Exception as e:
        logger.error(f"Error queueing watchlist rankings: {e}")
        return 0


def queue_stale_rankings() -> int:
    """Queue ranking jobs only for symbols with stale or missing rankings.

    Returns:
        Number of symbols queued
    """
    try:
        result = db.client.rpc("queue_stale_ranking_jobs").execute()
        count = result.data if result.data else 0
        logger.info(f"Queued ranking jobs for {count} stale symbols")
        return count
    except Exception as e:
        logger.error(f"Error queueing stale rankings: {e}")
        return 0


def queue_specific_symbols(symbols: list[str]) -> int:
    """Queue ranking jobs for specific symbols.

    Args:
        symbols: List of ticker symbols

    Returns:
        Number of symbols queued
    """
    count = 0
    for symbol in symbols:
        try:
            result = db.client.rpc(
                "queue_ranking_job",
                {"p_symbol": symbol.upper(), "p_priority": 2}
            ).execute()
            if result.data:
                count += 1
                logger.info(f"Queued ranking job for {symbol}")
        except Exception as e:
            logger.error(f"Error queueing {symbol}: {e}")

    logger.info(f"Queued {count} of {len(symbols)} symbols")
    return count


def get_ranking_health() -> dict:
    """Get summary of ranking health across watchlist.

    Returns:
        Dict with health metrics
    """
    try:
        result = db.client.rpc("get_ranking_health").execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        logger.warning(f"Could not get ranking health: {e}")

    return {
        "total_symbols": 0,
        "fresh_count": 0,
        "stale_count": 0,
        "never_ranked_count": 0,
        "partial_count": 0,
    }


def run_ranking_worker() -> bool:
    """Run the ranking job worker to process all queued jobs.

    Returns:
        True if successful
    """
    logger.info("Starting ranking worker to process queued jobs...")

    try:
        worker_path = Path(__file__).parent / "ranking_job_worker.py"
        python_path = sys.executable

        # Run the worker in "run once" mode (not watch mode)
        result = subprocess.run(
            [python_path, str(worker_path)],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout for all jobs
        )

        if result.returncode == 0:
            logger.info("Ranking worker completed successfully")
            logger.debug(result.stdout)
            return True
        else:
            logger.error(f"Ranking worker failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Ranking worker timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"Error running ranking worker: {e}")
        return False


def print_summary(health_before: dict, health_after: dict, queued: int):
    """Print a summary of the ranking run."""
    print("\n" + "=" * 60)
    print("HOURLY RANKING SUMMARY")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Jobs Queued: {queued}")
    print()
    print("Ranking Health:")
    print(f"  Total Symbols: {health_after['total_symbols']}")
    print(f"  Fresh: {health_after['fresh_count']} (was {health_before['fresh_count']})")
    print(f"  Stale: {health_after['stale_count']} (was {health_before['stale_count']})")
    print(f"  Never Ranked: {health_after['never_ranked_count']} (was {health_before['never_ranked_count']})")
    print(f"  Partial: {health_after['partial_count']} (was {health_before['partial_count']})")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Queue and process ranking jobs for watchlist symbols"
    )

    parser.add_argument(
        "--stale",
        action="store_true",
        help="Only queue symbols with stale or missing rankings"
    )

    parser.add_argument(
        "--no-process",
        action="store_true",
        help="Queue jobs only, don't run the worker to process them"
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to queue (overrides --stale)"
    )

    parser.add_argument(
        "--health",
        action="store_true",
        help="Only show ranking health status, don't queue anything"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Hourly Ranking Scheduler Started")
    logger.info("=" * 60)

    # Get health before
    health_before = get_ranking_health()

    if args.health:
        # Just show health and exit
        print_summary(health_before, health_before, 0)
        return

    # Queue jobs
    if args.symbols:
        queued = queue_specific_symbols(args.symbols)
    elif args.stale:
        queued = queue_stale_rankings()
    else:
        queued = queue_all_watchlist_rankings()

    if queued == 0:
        logger.info("No symbols to queue")
        return

    # Process jobs unless --no-process
    if not args.no_process:
        success = run_ranking_worker()
        if not success:
            logger.warning("Some ranking jobs may have failed")
    else:
        logger.info("Skipping worker (--no-process specified)")

    # Get health after
    health_after = get_ranking_health()

    # Print summary
    print_summary(health_before, health_after, queued)

    logger.info("Hourly Ranking Scheduler Complete")


if __name__ == "__main__":
    main()
