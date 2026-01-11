"""
Deep Backfill OHLC data directly from Polygon API.

This script fetches maximum historical data (up to 2 years for free tier)
directly from Polygon, bypassing the Edge Function limitations.

Features:
- Direct Polygon API access for maximum data
- Configurable lookback period (default: 2 years)
- All timeframes support (d1, w1, h1, h4, m15)
- Rate limiting (5 req/min for free tier)
- Incremental mode to skip recently updated symbols

Usage:
    python src/scripts/deep_backfill_ohlc.py --symbol AAPL
    python src/scripts/deep_backfill_ohlc.py --symbols AAPL NVDA TSLA
    python src/scripts/deep_backfill_ohlc.py --all --timeframe d1
    python src/scripts/deep_backfill_ohlc.py --all --all-timeframes
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests  # noqa: E402

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Polygon API configuration
POLYGON_BASE_URL = "https://api.polygon.io"
POLYGON_API_KEY = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")

# Rate limiting: Polygon free tier = 5 requests/minute
RATE_LIMIT_DELAY = 12.5  # 60/5 = 12 seconds between requests

# Timeframe configurations
TIMEFRAME_CONFIG = {
    "m1": {"multiplier": 1, "timespan": "minute", "max_days": 7},
    "m5": {"multiplier": 5, "timespan": "minute", "max_days": 30},
    "m15": {"multiplier": 15, "timespan": "minute", "max_days": 60},
    "m30": {"multiplier": 30, "timespan": "minute", "max_days": 60},
    "h1": {"multiplier": 1, "timespan": "hour", "max_days": 180},
    "h4": {"multiplier": 4, "timespan": "hour", "max_days": 365},
    "d1": {"multiplier": 1, "timespan": "day", "max_days": 730},  # 2 years
    "w1": {"multiplier": 1, "timespan": "week", "max_days": 1825},  # 5 years
    "mn1": {"multiplier": 1, "timespan": "month", "max_days": 3650},  # 10 years
}

# Default symbols if no watchlist
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
    "AI",
]


def get_watchlist_symbols(limit: int = 200) -> List[str]:
    """Fetch symbols from user watchlists."""
    try:
        response = db.client.rpc("get_all_watchlist_symbols", {"p_limit": limit}).execute()
        if response.data:
            symbols = [row["ticker"] for row in response.data]
            logger.info(f"📋 Fetched {len(symbols)} symbols from watchlists")
            return symbols
    except Exception as e:
        logger.warning(f"Could not fetch watchlist: {e}")

    logger.info("Using default symbol list")
    return DEFAULT_SYMBOLS


def fetch_polygon_bars(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> List[dict]:
    """
    Fetch OHLC bars directly from Polygon API.

    Returns list of bar dicts with keys: ts, open, high, low, close, volume
    """
    if not POLYGON_API_KEY:
        raise ValueError("MASSIVE_API_KEY or POLYGON_API_KEY not set")

    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        raise ValueError(f"Invalid timeframe: {timeframe}")

    multiplier = config["multiplier"]
    timespan = config["timespan"]

    # Format dates
    if timespan in ("day", "week", "month"):
        from_str = start_date.strftime("%Y-%m-%d")
        to_str = end_date.strftime("%Y-%m-%d")
    else:
        from_str = str(int(start_date.timestamp() * 1000))
        to_str = str(int(end_date.timestamp() * 1000))

    url = (
        f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/"
        f"{multiplier}/{timespan}/{from_str}/{to_str}"
    )
    params = {
        "adjusted": "false",  # Use unadjusted prices for accurate historical data
        "sort": "asc",
        "limit": "50000",
        "apiKey": POLYGON_API_KEY,
    }

    logger.info(f"Fetching {symbol} {timeframe} from {from_str} to {to_str}")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "ERROR":
            logger.error(f"Polygon API error: {data}")
            return []

        results = data.get("results", [])
        if not results:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            return []

        # Transform to our format
        bars = []
        for r in results:
            bars.append(
                {
                    "ts": datetime.utcfromtimestamp(r["t"] / 1000).isoformat() + "Z",
                    "open": r["o"],
                    "high": r["h"],
                    "low": r["l"],
                    "close": r["c"],
                    "volume": r["v"],
                }
            )

        logger.info(f"✅ Fetched {len(bars)} bars for {symbol} {timeframe}")
        return bars

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded! Wait before retrying.")
        else:
            logger.error(f"HTTP error fetching {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def persist_bars(symbol: str, timeframe: str, bars: List[dict]) -> int:
    """Persist bars to database. Returns count of inserted bars."""
    if not bars:
        return 0

    symbol_id = db.get_symbol_id(symbol)
    inserted = 0

    # Batch upsert for efficiency
    batch = []
    for bar in bars:
        batch.append(
            {
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": bar["ts"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
                "provider": "massive",
            }
        )

    try:
        db.client.table("ohlc_bars").upsert(
            batch,
            on_conflict="symbol_id,timeframe,ts",
        ).execute()
        inserted = len(batch)
        logger.info(f"✅ Persisted {inserted} bars for {symbol} {timeframe}")
    except Exception as e:
        logger.error(f"Error persisting bars for {symbol}: {e}")

    return inserted


def get_data_coverage(symbol: str, timeframe: str) -> dict:
    """Get current data coverage for a symbol/timeframe."""
    try:
        symbol_id = db.get_symbol_id(symbol)
        response = (
            db.client.table("ohlc_bars")
            .select("ts")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .order("ts", desc=False)
            .limit(1)
            .execute()
        )

        earliest = None
        if response.data:
            earliest = datetime.fromisoformat(response.data[0]["ts"].replace("Z", "+00:00"))

        response = (
            db.client.table("ohlc_bars")
            .select("ts")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )

        latest = None
        if response.data:
            latest = datetime.fromisoformat(response.data[0]["ts"].replace("Z", "+00:00"))

        # Get count
        response = (
            db.client.table("ohlc_bars")
            .select("id", count="exact")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .execute()
        )

        count = response.count or 0

        return {
            "earliest": earliest,
            "latest": latest,
            "count": count,
        }
    except Exception as e:
        logger.warning(f"Could not get coverage for {symbol}: {e}")
        return {"earliest": None, "latest": None, "count": 0}


def backfill_symbol(
    symbol: str,
    timeframe: str,
    days_back: Optional[int] = None,
    force: bool = False,
) -> bool:
    """
    Backfill a single symbol/timeframe.

    Args:
        symbol: Stock ticker
        timeframe: Timeframe (d1, h1, etc.)
        days_back: How many days of history to fetch (default: max for timeframe)
        force: If True, fetch even if recent data exists

    Returns:
        True if successful
    """
    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        logger.error(f"Invalid timeframe: {timeframe}")
        return False

    # Determine date range
    max_days = config["max_days"]
    if days_back:
        max_days = min(days_back, max_days)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=max_days)

    # Check existing coverage
    coverage = get_data_coverage(symbol, timeframe)
    logger.info(
        f"Current coverage for {symbol} {timeframe}: "
        f"{coverage['count']} bars, "
        f"earliest={coverage['earliest']}, latest={coverage['latest']}"
    )

    # Skip if recent data exists and not forcing
    if not force and coverage["latest"]:
        age = end_date.replace(tzinfo=None) - coverage["latest"].replace(tzinfo=None)
        if timeframe == "d1" and age < timedelta(days=1):
            logger.info(f"⏭️  {symbol} {timeframe} is current, skipping")
            return True
        elif timeframe.startswith("h") and age < timedelta(hours=4):
            logger.info(f"⏭️  {symbol} {timeframe} is current, skipping")
            return True

    # Fetch from Polygon
    bars = fetch_polygon_bars(symbol, timeframe, start_date, end_date)

    if not bars:
        logger.warning(f"No bars fetched for {symbol} {timeframe}")
        return False

    # Persist to database
    inserted = persist_bars(symbol, timeframe, bars)

    return inserted > 0


def main():
    parser = argparse.ArgumentParser(
        description="Deep backfill OHLC data directly from Polygon API"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol", type=str, help="Single symbol")
    group.add_argument("--symbols", type=str, nargs="+", help="Multiple symbols")
    group.add_argument("--all", action="store_true", help="All watchlist symbols")

    parser.add_argument("--timeframe", type=str, default="d1", help="Timeframe (default: d1)")
    parser.add_argument(
        "--all-timeframes",
        action="store_true",
        help="Backfill all timeframes (d1, w1, h1, h4, m15)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Days of history to fetch (default: max for timeframe)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force fetch even if recent data exists"
    )

    args = parser.parse_args()

    # Validate API key
    if not POLYGON_API_KEY:
        logger.error("❌ MASSIVE_API_KEY or POLYGON_API_KEY not set!")
        sys.exit(1)

    # Determine symbols
    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.symbols:
        symbols = [s.upper() for s in args.symbols]
    else:
        symbols = get_watchlist_symbols()

    # Determine timeframes
    if args.all_timeframes:
        timeframes = ["d1", "w1", "h1", "h4", "m15"]
    else:
        timeframes = [args.timeframe]

    logger.info("=" * 60)
    logger.info("Deep OHLC Backfill (Direct Polygon API)")
    logger.info(f"Symbols: {len(symbols)}")
    logger.info(f"Timeframes: {timeframes}")
    logger.info(f"Days back: {args.days or 'max'}")
    logger.info(f"Force: {args.force}")
    logger.info("=" * 60)

    success = 0
    failed = 0

    for tf in timeframes:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing timeframe: {tf}")
        logger.info(f"{'='*60}")

        for i, symbol in enumerate(symbols):
            try:
                if backfill_symbol(symbol, tf, args.days, args.force):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"❌ Error processing {symbol}: {e}")
                failed += 1

            # Rate limiting
            if i < len(symbols) - 1:
                logger.info(f"⏱️  Rate limit delay ({RATE_LIMIT_DELAY}s)...")
                time.sleep(RATE_LIMIT_DELAY)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Deep Backfill Complete")
    logger.info(f"✅ Success: {success}")
    logger.info(f"❌ Failed: {failed}")
    logger.info("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
