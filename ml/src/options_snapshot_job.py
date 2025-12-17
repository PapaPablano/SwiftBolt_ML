"""
Options Price Snapshot Job - Captures daily options price history

This job captures current options prices from the options_ranks table
into the options_price_history table for historical analysis.

Usage:
    python src/options_snapshot_job.py              # Snapshot all symbols with rankings
    python src/options_snapshot_job.py --symbol AAPL # Snapshot specific symbol
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def capture_snapshot(symbol: str = None) -> int:
    """
    Capture options price snapshot for a symbol or all symbols.

    Args:
        symbol: Optional symbol ticker. If None, captures all symbols with rankings.

    Returns:
        Total number of price records captured
    """
    try:
        if symbol:
            # Get symbol ID
            symbol_id = db.get_symbol_id(symbol)

            # Capture snapshot using database function
            result = db.client.rpc(
                "capture_options_snapshot",
                {"p_symbol_id": symbol_id}
            ).execute()

            rows_captured = result.data if result.data else 0
            logger.info(f"✅ Captured {rows_captured} price records for {symbol}")

            return rows_captured

        else:
            # Get all symbols with options rankings
            result = db.client.from_("options_ranks") \
                .select("underlying_symbol_id") \
                .execute()

            if not result.data:
                logger.warning("No options rankings found in database")
                return 0

            # Get unique symbol IDs
            symbol_ids = list(set(row["underlying_symbol_id"] for row in result.data))

            logger.info(f"Found {len(symbol_ids)} symbols with rankings to snapshot")

            total_captured = 0

            for symbol_id in symbol_ids:
                try:
                    snapshot_result = db.client.rpc(
                        "capture_options_snapshot",
                        {"p_symbol_id": symbol_id}
                    ).execute()

                    rows = snapshot_result.data if snapshot_result.data else 0
                    total_captured += rows

                    # Get symbol ticker for logging
                    symbol_result = db.client.from_("symbols") \
                        .select("ticker") \
                        .eq("id", symbol_id) \
                        .single() \
                        .execute()

                    ticker = symbol_result.data["ticker"] if symbol_result.data else symbol_id

                    logger.info(f"  ✓ {ticker}: {rows} records")

                except Exception as e:
                    logger.error(f"  ✗ Error capturing snapshot for {symbol_id}: {e}")

            logger.info(f"✅ Total: Captured {total_captured} price records across all symbols")

            return total_captured

    except Exception as e:
        logger.error(f"Error capturing options snapshot: {e}", exc_info=True)
        return 0


def cleanup_old_snapshots() -> int:
    """
    Remove price history older than 90 days.

    Returns:
        Number of records deleted
    """
    try:
        result = db.client.rpc("cleanup_old_price_history").execute()
        rows_deleted = result.data if result.data else 0

        logger.info(f"🗑️  Cleaned up {rows_deleted} old price history records (>90 days)")

        return rows_deleted

    except Exception as e:
        logger.error(f"Error cleaning up old snapshots: {e}")
        return 0


def main():
    """Main snapshot job entry point."""
    parser = argparse.ArgumentParser(
        description="Capture options price snapshots for historical analysis"
    )

    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to snapshot (e.g., AAPL). If not provided, snapshots all symbols."
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Also cleanup old price history (>90 days)"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Options Price Snapshot Job")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)

    # Capture snapshot
    symbol_arg = args.symbol.upper() if args.symbol else None
    rows_captured = capture_snapshot(symbol_arg)

    # Cleanup if requested
    if args.cleanup:
        logger.info("")
        cleanup_old_snapshots()

    logger.info("=" * 80)
    logger.info("Snapshot Job Complete")
    logger.info(f"Total records captured: {rows_captured}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
