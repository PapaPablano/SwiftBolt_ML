"""
Backfill OHLC data for symbols by fetching from the /chart Edge Function.

This script fetches historical OHLC data via the chart API (which pulls from Polygon)
and persists it to the database so the options ranking job can use it.

Features:
- Server-side watchlist: fetches symbols from all user watchlists (up to 200)
- Incremental backfill (only fetches missing data)
- Rate limiting to respect API quotas
- Retry with exponential backoff for transient errors (502, 503, 504)
- Deduplication via database unique constraints
- Structured logging for monitoring

Usage:
    python src/scripts/backfill_ohlc.py --symbol CRWD --timeframe d1
    python src/scripts/backfill_ohlc.py --symbols CRWD NVDA TSLA
    python src/scripts/backfill_ohlc.py --all  # Backfill all watchlist symbols from DB
    python src/scripts/backfill_ohlc.py --all --incremental  # Recommended for scheduled runs
"""

import argparse
import logging
import sys
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
import requests
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Validate required environment variables at startup
logger.info(
    f"Supabase URL: {settings.supabase_url[:30]}..."
    if settings.supabase_url
    else "Supabase URL: NOT SET"
)
logger.info(
    f"Supabase Key: {'SET (' + str(len(settings.supabase_key)) + ' chars)' if settings.supabase_key else 'NOT SET'}"
)
if not settings.supabase_url or not settings.supabase_key:
    logger.error("❌ Missing required Supabase credentials!")
    logger.error(f"Environment variables check:")
    logger.error(
        f"  SUPABASE_URL: {os.getenv('SUPABASE_URL', 'NOT SET')[:30] if os.getenv('SUPABASE_URL') else 'NOT SET'}"
    )
    logger.error(
        f"  SUPABASE_KEY: {'SET' if os.getenv('SUPABASE_KEY') else 'NOT SET'}"
    )
    sys.exit(1)


# Fallback symbols if database watchlist is empty
DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "TSLA",
    "META",
    "SPY",
    "QQQ",
    "CRWD",
    "PLTR",
    "AMD",
    "NFLX",
    "DIS",
]

# Rate limiting configuration (respecting free-tier API constraints)
RATE_LIMIT_DELAY = 2.0  # Seconds between API calls
CHUNK_DELAY = 12.0  # Seconds between chunks for strict providers

# Retry configuration for transient errors
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff
RETRYABLE_STATUS_CODES = {
    502,
    503,
    504,
}  # Bad Gateway, Service Unavailable, Gateway Timeout


def get_watchlist_symbols_from_db(limit: int = 200) -> List[str]:
    """
    Fetch all unique symbols from user watchlists in the database.

    Uses the get_all_watchlist_symbols() database function to get symbols
    that users have added to their watchlists (up to the specified limit).

    Falls back to DEFAULT_SYMBOLS if no watchlist symbols found.
    """
    try:
        # Call the database function to get watchlist symbols
        response = db.client.rpc(
            "get_all_watchlist_symbols", {"p_limit": limit}
        ).execute()

        if response.data:
            symbols = [row["ticker"] for row in response.data]
            logger.info(
                f"📋 Fetched {len(symbols)} symbols from user watchlists"
            )
            return symbols
        else:
            logger.warning(
                "No symbols found in user watchlists, using defaults"
            )
            return DEFAULT_SYMBOLS

    except Exception as e:
        logger.warning(f"Could not fetch watchlist symbols from DB: {e}")
        logger.info("Falling back to default symbol list")
        return DEFAULT_SYMBOLS


def get_latest_bar_timestamp(
    symbol: str, timeframe: str
) -> Optional[datetime]:
    """
    Get the timestamp of the most recent bar for a symbol/timeframe.

    Returns None if no bars exist (full backfill needed).
    """
    try:
        symbol_id = db.get_symbol_id(symbol)
        response = (
            db.client.table("ohlc_bars")
            .select("ts")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            ts_str = response.data[0]["ts"]
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return None
    except Exception as e:
        logger.warning(f"Could not fetch latest bar for {symbol}: {e}")
        return None


def fetch_chart_data(symbol: str, timeframe: str = "d1") -> dict:
    """
    Fetch chart data from the /chart Edge Function.

    This endpoint pulls data from Polygon on-demand.
    Includes retry logic with exponential backoff for transient errors.
    """
    url = f"{settings.supabase_url}/functions/v1/chart"
    params = {
        "symbol": symbol,
        "timeframe": timeframe,
    }
    headers = {
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
    }

    logger.info(f"Fetching chart data for {symbol} ({timeframe})...")

    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            bars_count = len(data.get("bars", []))
            logger.info(f"Fetched {bars_count} bars for {symbol}")

            return data
        except requests.exceptions.HTTPError as e:
            last_exception = e
            status_code = (
                e.response.status_code if e.response is not None else 0
            )

            if (
                status_code in RETRYABLE_STATUS_CODES
                and attempt < MAX_RETRIES - 1
            ):
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    f"⚠️  Transient error ({status_code}) for {symbol}, "
                    f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(delay)
                continue
            else:
                logger.error(f"Failed to fetch chart data for {symbol}: {e}")
                raise
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    f"⚠️  Request error for {symbol}, "
                    f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(delay)
                continue
            else:
                logger.error(f"Failed to fetch chart data for {symbol}: {e}")
                raise

    # Should not reach here, but just in case
    raise last_exception or Exception(
        f"Failed to fetch chart data for {symbol} after {MAX_RETRIES} attempts"
    )


def persist_ohlc_bars(
    symbol: str, timeframe: str, bars: List[dict]
) -> tuple[int, int]:
    """
    Persist OHLC bars to the database.

    Returns tuple of (inserted_count, skipped_count).
    Uses upsert to handle duplicates gracefully (idempotent).
    """
    if not bars:
        logger.warning(f"No bars to persist for {symbol}")
        return 0, 0

    # Get symbol_id
    symbol_id = db.get_symbol_id(symbol)

    inserted_count = 0
    skipped_count = 0

    for bar in bars:
        try:
            # Extract bar data
            ts = bar["ts"]  # ISO8601 timestamp string
            open_price = float(bar["open"])
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            volume = int(bar["volume"])

            # Insert into database using upsert (dedupe via unique constraint)
            result = (
                db.client.table("ohlc_bars")
                .upsert(
                    {
                        "symbol_id": symbol_id,
                        "timeframe": timeframe,
                        "ts": ts,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                        "provider": "massive",  # Data originally from Polygon via /chart
                    },
                    on_conflict="symbol_id,timeframe,ts",
                )
                .execute()
            )

            inserted_count += 1

        except Exception as e:
            logger.debug(
                f"Skipped duplicate or error for {symbol} at {bar.get('ts')}: {e}"
            )
            skipped_count += 1
            continue

    logger.info(
        f"✅ Persisted {inserted_count} bars for {symbol} ({skipped_count} skipped)"
    )
    return inserted_count, skipped_count


def backfill_symbol(
    symbol: str, timeframe: str = "d1", incremental: bool = False
) -> bool:
    """
    Backfill OHLC data for a single symbol.

    Args:
        symbol: Stock ticker
        timeframe: Timeframe (d1, h1, etc.)
        incremental: If True, only fetch data newer than latest bar

    Returns:
        True if successful, False otherwise.
    """
    start_time = time.time()
    logger.info(f"{'='*60}")
    logger.info(
        f"Backfilling {symbol} ({timeframe}) [incremental={incremental}]"
    )
    logger.info(f"{'='*60}")

    try:
        # Check for existing data if incremental mode
        latest_bar_ts = None
        if incremental:
            latest_bar_ts = get_latest_bar_timestamp(symbol, timeframe)
            if latest_bar_ts:
                logger.info(f"Latest bar: {latest_bar_ts.isoformat()}")
                # If data is recent (within 1 day for d1, 1 hour for h1), skip
                now = datetime.now(latest_bar_ts.tzinfo)
                if timeframe == "d1" and (now - latest_bar_ts) < timedelta(
                    days=1
                ):
                    logger.info(f"⏭️  Data is current, skipping {symbol}")
                    return True
                elif timeframe.startswith("h") and (
                    now - latest_bar_ts
                ) < timedelta(hours=1):
                    logger.info(f"⏭️  Data is current, skipping {symbol}")
                    return True
            else:
                logger.info("No existing data, performing full backfill")

        # Fetch data from /chart endpoint
        chart_data = fetch_chart_data(symbol, timeframe)
        bars = chart_data.get("bars", [])

        if not bars:
            logger.warning(f"No bars returned for {symbol}")
            return False

        # Filter to only new bars if incremental
        if incremental and latest_bar_ts:
            original_count = len(bars)
            bars = [
                bar
                for bar in bars
                if datetime.fromisoformat(bar["ts"].replace("Z", "+00:00"))
                > latest_bar_ts
            ]
            logger.info(f"Filtered {original_count} → {len(bars)} new bars")

        if not bars and incremental:
            logger.info(f"✅ No new bars for {symbol} (already up to date)")
            return True

        # Persist to database
        inserted, skipped = persist_ohlc_bars(symbol, timeframe, bars)
        elapsed = time.time() - start_time

        if inserted > 0:
            logger.info(
                f"✅ Successfully backfilled {symbol}: "
                f"{inserted} inserted, {skipped} skipped "
                f"({elapsed:.1f}s)"
            )
            return True
        else:
            logger.warning(f"⚠️  No bars persisted for {symbol}")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to backfill {symbol}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill OHLC data for symbols with incremental support and rate limiting"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol", type=str, help="Single symbol to backfill (e.g., CRWD)"
    )
    group.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Multiple symbols to backfill (e.g., CRWD NVDA TSLA)",
    )
    group.add_argument(
        "--all", action="store_true", help="Backfill all watchlist symbols"
    )

    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        help="Timeframe to backfill (default: d1)",
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only fetch data newer than latest bar (recommended for scheduled runs)",
    )

    parser.add_argument(
        "--all-timeframes",
        action="store_true",
        help="Backfill all timeframes (m15, h1, d1, w1) for multi-timeframe analysis",
    )

    args = parser.parse_args()

    # Determine which symbols to process
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:  # --all
        # Fetch symbols from database watchlists (with fallback to defaults)
        symbols = get_watchlist_symbols_from_db(limit=200)

    overall_start_time = time.time()

    # Determine timeframes to process
    if args.all_timeframes:
        timeframes = ["d1", "h1", "m15", "w1"]  # Order: most important first
    else:
        timeframes = [args.timeframe]

    logger.info("=" * 60)
    logger.info("OHLC Backfill Script")
    logger.info(f"Mode: {'INCREMENTAL' if args.incremental else 'FULL'}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")
    logger.info(f"Processing {len(symbols)} symbol(s)")
    logger.info("=" * 60)

    success_count = 0
    failure_count = 0

    for timeframe in timeframes:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing timeframe: {timeframe}")
        logger.info(f"{'='*60}")

        for i, symbol in enumerate(symbols):
            # Process the symbol
            if backfill_symbol(
                symbol, timeframe, incremental=args.incremental
            ):
                success_count += 1
            else:
                failure_count += 1

            # Rate limiting between symbols (respect API quotas)
            if i < len(symbols) - 1:  # Don't delay after last symbol
                logger.info(f"⏱️  Rate limit delay ({RATE_LIMIT_DELAY}s)...")
                time.sleep(RATE_LIMIT_DELAY)

        # Extra delay between timeframes
        if len(timeframes) > 1 and timeframe != timeframes[-1]:
            logger.info(f"⏱️  Timeframe delay ({CHUNK_DELAY}s)...")
            time.sleep(CHUNK_DELAY)

    overall_elapsed = time.time() - overall_start_time

    logger.info("")
    logger.info("=" * 60)
    logger.info("Backfill Complete")
    logger.info(f"Timeframes processed: {len(timeframes)}")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"❌ Failed: {failure_count}")
    logger.info(f"⏱️  Total time: {overall_elapsed:.1f}s")
    logger.info("=" * 60)

    # Exit with non-zero code if any failures
    sys.exit(0 if failure_count == 0 else 1)


if __name__ == "__main__":
    main()
