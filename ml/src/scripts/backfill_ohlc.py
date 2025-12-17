"""
Backfill OHLC data for symbols by fetching from the /chart Edge Function.

This script fetches historical OHLC data via the chart API (which pulls from Polygon)
and persists it to the database so the options ranking job can use it.

Usage:
    python src/scripts/backfill_ohlc.py --symbol CRWD
    python src/scripts/backfill_ohlc.py --symbols CRWD NVDA TSLA
    python src/scripts/backfill_ohlc.py --all  # Backfill watchlist
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import requests
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


WATCHLIST_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "SPY", "QQQ", "CRWD", "PLTR", "AMD", "NFLX", "DIS"
]


def fetch_chart_data(symbol: str, timeframe: str = "d1") -> dict:
    """
    Fetch chart data from the /chart Edge Function.

    This endpoint pulls data from Polygon on-demand.
    """
    url = f"{settings.supabase_url}/functions/v1/chart"
    params = {
        "symbol": symbol,
        "timeframe": timeframe,
    }
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    logger.info(f"Fetching chart data for {symbol} ({timeframe})...")

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        bars_count = len(data.get("bars", []))
        logger.info(f"Fetched {bars_count} bars for {symbol}")

        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch chart data for {symbol}: {e}")
        raise


def persist_ohlc_bars(symbol: str, bars: List[dict]) -> int:
    """
    Persist OHLC bars to the database.

    Returns the number of bars successfully inserted.
    """
    if not bars:
        logger.warning(f"No bars to persist for {symbol}")
        return 0

    # Get symbol_id
    symbol_id = db.get_symbol_id(symbol)

    inserted_count = 0

    for bar in bars:
        try:
            # Extract bar data
            ts = bar["ts"]  # ISO8601 timestamp string
            open_price = float(bar["open"])
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            volume = int(bar["volume"])

            # Insert into database using raw SQL (upsert)
            # We'll use the Supabase client's table.upsert() method
            result = db.client.table("ohlc_bars").upsert({
                "symbol_id": symbol_id,
                "timeframe": "d1",  # Daily bars
                "ts": ts,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "provider": "massive",  # Data originally from Polygon via /chart
            }, on_conflict="symbol_id,timeframe,ts").execute()

            inserted_count += 1

        except Exception as e:
            logger.error(f"Failed to insert bar for {symbol} at {bar.get('ts')}: {e}")
            continue

    logger.info(f"✅ Persisted {inserted_count}/{len(bars)} bars for {symbol}")
    return inserted_count


def backfill_symbol(symbol: str, timeframe: str = "d1") -> bool:
    """
    Backfill OHLC data for a single symbol.

    Returns True if successful, False otherwise.
    """
    logger.info(f"{'='*60}")
    logger.info(f"Backfilling {symbol} ({timeframe})")
    logger.info(f"{'='*60}")

    try:
        # Fetch data from /chart endpoint
        chart_data = fetch_chart_data(symbol, timeframe)
        bars = chart_data.get("bars", [])

        if not bars:
            logger.warning(f"No bars returned for {symbol}")
            return False

        # Persist to database
        inserted = persist_ohlc_bars(symbol, bars)

        if inserted > 0:
            logger.info(f"✅ Successfully backfilled {symbol}: {inserted} bars")
            return True
        else:
            logger.warning(f"⚠️  No bars persisted for {symbol}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to backfill {symbol}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill OHLC data for symbols"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to backfill (e.g., CRWD)"
    )
    group.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Multiple symbols to backfill (e.g., CRWD NVDA TSLA)"
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Backfill all watchlist symbols"
    )

    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        help="Timeframe to backfill (default: d1)"
    )

    args = parser.parse_args()

    # Determine which symbols to process
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:  # --all
        symbols = WATCHLIST_SYMBOLS

    logger.info("="*60)
    logger.info("OHLC Backfill Script")
    logger.info(f"Processing {len(symbols)} symbol(s)")
    logger.info("="*60)

    success_count = 0
    failure_count = 0

    for symbol in symbols:
        if backfill_symbol(symbol, args.timeframe):
            success_count += 1
        else:
            failure_count += 1

    logger.info("")
    logger.info("="*60)
    logger.info("Backfill Complete")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"❌ Failed: {failure_count}")
    logger.info("="*60)

    sys.exit(0 if failure_count == 0 else 1)


if __name__ == "__main__":
    main()
