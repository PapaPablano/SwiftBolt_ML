"""
Alpaca-based OHLC Backfill Script for ohlc_bars_v2

This script fetches historical data from Alpaca API and writes to ohlc_bars_v2
with provider='alpaca', replacing the old Polygon-based backfill.

Features:
- Writes to ohlc_bars_v2 with provider='alpaca'
- Supports all timeframes (m15, h1, h4, d1, w1)
- 7+ years of historical data coverage
- Rate limiting (200 req/min for Alpaca)
- Automatic pagination for large datasets

Usage:
    python src/scripts/alpaca_backfill_ohlc_v2.py --symbol AAPL
    python src/scripts/alpaca_backfill_ohlc_v2.py --symbols AAPL NVDA TSLA
    python src/scripts/alpaca_backfill_ohlc_v2.py --all --timeframe d1
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load environment variables from root .env file
root_dir = Path(__file__).parent.parent.parent.parent
load_dotenv(root_dir / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Alpaca API configuration
ALPACA_BASE_URL = "https://data.alpaca.markets/v2"
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")

# Rate limiting: Alpaca allows 200 requests/minute
RATE_LIMIT_DELAY = 0.3  # 60/200 = 0.3 seconds between requests

# How long we consider existing data "fresh" while markets are closed (hours)
MAX_STALE_HOURS_WHEN_CLOSED = 72

ET_ZONE = ZoneInfo("America/New_York")


def is_us_market_open(ts: datetime) -> bool:
    """Return True when US equities market is open (simple hours check)."""

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    et_time = ts.astimezone(ET_ZONE)

    # Closed on weekends
    if et_time.weekday() >= 5:
        return False

    market_open = et_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = et_time.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= et_time <= market_close


# Timeframe configurations
TIMEFRAME_CONFIG = {
    "m1": {"alpaca_tf": "1Min", "max_days": 7},
    "m5": {"alpaca_tf": "5Min", "max_days": 30},
    "m15": {"alpaca_tf": "15Min", "max_days": 60},
    "m30": {"alpaca_tf": "30Min", "max_days": 60},
    "h1": {"alpaca_tf": "1Hour", "max_days": 180},
    "h4": {"alpaca_tf": "4Hour", "max_days": 365},
    "d1": {"alpaca_tf": "1Day", "max_days": 2555},  # 7 years
    "w1": {"alpaca_tf": "1Week", "max_days": 2555},
    "mn1": {"alpaca_tf": "1Month", "max_days": 3650},
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


def get_alpaca_headers() -> dict:
    """Get authentication headers for Alpaca API."""
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
    }


def fetch_alpaca_bars(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> List[dict]:
    """
    Fetch OHLC bars from Alpaca API with automatic pagination.

    Returns list of bar dicts with keys: ts, open, high, low, close, volume
    """
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")

    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        raise ValueError(f"Invalid timeframe: {timeframe}")

    alpaca_timeframe = config["alpaca_tf"]

    # Format dates to RFC-3339
    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info(f"Fetching {symbol} {timeframe} from {start_str} to {end_str}")

    all_bars = []
    page_token = None
    page_count = 0
    max_pages = 100  # Safety limit

    try:
        while page_count < max_pages:
            # Build URL
            # Use 'iex' feed for paper trading accounts (free tier)
            # Use 'sip' feed for live trading accounts (paid)
            url = (
                f"{ALPACA_BASE_URL}/stocks/bars?"
                f"symbols={symbol.upper()}&"
                f"timeframe={alpaca_timeframe}&"
                f"start={start_str}&"
                f"end={end_str}&"
                f"limit=10000&"
                f"adjustment=raw&"
                f"feed=iex&"
                f"sort=asc"
            )

            if page_token:
                url += f"&page_token={page_token}"

            response = requests.get(url, headers=get_alpaca_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()

            # Extract bars for this symbol
            bars_data = data.get("bars", {}).get(symbol.upper(), [])

            if not bars_data and page_count == 0:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []

            # Transform to our format
            for bar in bars_data:
                bar_ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))

                all_bars.append(
                    {
                        "ts": bar_ts.isoformat().replace("+00:00", "Z"),
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"],
                        "volume": bar["v"],
                    }
                )

            # Check for next page
            page_token = data.get("next_page_token")
            page_count += 1

            if page_token:
                logger.info(f"Fetched page {page_count} with {len(bars_data)} bars, continuing...")
                time.sleep(RATE_LIMIT_DELAY)  # Rate limiting between pages
            else:
                break

        logger.info(
            f"✅ Fetched {len(all_bars)} bars for {symbol} {timeframe} across {page_count} page(s)"
        )
        return all_bars

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded! Wait before retrying.")
        elif e.response.status_code == 401:
            logger.error("Authentication failed! Check ALPACA_API_KEY and ALPACA_API_SECRET.")
        else:
            logger.error(f"HTTP error fetching {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def persist_bars_v2(symbol: str, timeframe: str, bars: List[dict]) -> int:
    """
    Persist bars to ohlc_bars_v2 with provider='alpaca'.

    Returns count of inserted bars.
    """
    if not bars:
        return 0

    symbol_id = db.get_symbol_id(symbol)

    # Prepare batch with v2 schema
    batch = []
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for bar in bars:
        bar_ts = datetime.fromisoformat(bar["ts"].replace("Z", "+00:00"))
        bar_date = bar_ts.replace(hour=0, minute=0, second=0, microsecond=0)

        # Determine if this is intraday data (today's data only)
        is_intraday = (bar_date == today) and timeframe in ["m15", "h1", "h4"]

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
                "provider": "alpaca",
                "is_intraday": is_intraday,
                "is_forecast": False,
                "data_status": "verified",
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            }
        )

    try:
        # Batch upsert (1000 rows per request limit)
        inserted = 0
        batch_size = 1000

        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            db.client.table("ohlc_bars_v2").upsert(
                chunk,
                on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
            ).execute()
            inserted += len(chunk)

        logger.info(f"✅ Persisted {inserted} bars for {symbol} {timeframe}")
        return inserted
    except Exception as e:
        logger.error(f"Error persisting bars for {symbol}: {e}")
        logger.error(f"First bar sample: {batch[0] if batch else 'No bars'}")
        return 0


def get_data_coverage_v2(symbol: str, timeframe: str) -> dict:
    """Get current data coverage for a symbol/timeframe in ohlc_bars_v2."""
    try:
        symbol_id = db.get_symbol_id(symbol)

        # Query any existing non-forecast bars regardless of provider.
        response = (
            db.client.table("ohlc_bars_v2")
            .select("ts")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .eq("is_forecast", False)
            .order("ts", desc=False)
            .limit(1)
            .execute()
        )

        earliest = None
        if response.data:
            earliest = datetime.fromisoformat(response.data[0]["ts"].replace("Z", "+00:00"))

        response = (
            db.client.table("ohlc_bars_v2")
            .select("ts")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .eq("is_forecast", False)
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )

        latest = None
        if response.data:
            latest = datetime.fromisoformat(response.data[0]["ts"].replace("Z", "+00:00"))

        # Get count
        response = (
            db.client.table("ohlc_bars_v2")
            .select("id", count="exact")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", timeframe)
            .eq("is_forecast", False)
            .execute()
        )

        count = response.count or 0

        return {
            "earliest": earliest,
            "latest": latest,
            "count": count,
        }
    except Exception as e:
        logger.error(f"Error getting coverage for {symbol}: {e}")
        return {"earliest": None, "latest": None, "count": 0}


def backfill_symbol(
    symbol: str,
    timeframe: str = "d1",
    force: bool = False,
) -> dict:
    """
    Backfill historical data for a single symbol using Alpaca.

    Args:
        symbol: Stock ticker
        timeframe: Timeframe to backfill
        force: If True, fetch full history even if data exists

    Returns:
        Dict with status and stats
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 Backfilling {symbol} ({timeframe}) via Alpaca")
    logger.info(f"{'='*60}")

    # Check existing coverage
    coverage = get_data_coverage_v2(symbol, timeframe)
    logger.info(
        f"Current coverage: {coverage['count']} bars "
        f"({coverage['earliest']} to {coverage['latest']})"
    )

    # Determine date range
    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        logger.error(f"Invalid timeframe: {timeframe}")
        return {"success": False, "error": "Invalid timeframe"}

    now_utc = datetime.now(timezone.utc)
    end_date = now_utc
    max_days = config["max_days"]
    start_date = end_date - timedelta(days=max_days)

    market_open_now = is_us_market_open(now_utc)

    # When the market is closed, reuse existing Supabase data.
    # Only hit Alpaca if we have no bars at all (seed) or the user forces a refresh.
    if (not force) and (not market_open_now) and coverage.get("count", 0) > 0:
        logger.info("⏭️  Skipping %s - market closed, reusing existing data", symbol)
        return {
            "success": True,
            "skipped": True,
            "reason": "Market closed",
        }

    # Skip if recently updated (unless force)
    latest_bar = coverage["latest"]
    if (not force) and latest_bar:
        if latest_bar.tzinfo is None:
            latest_bar = latest_bar.replace(tzinfo=timezone.utc)

        hours_since_update = (end_date - latest_bar).total_seconds() / 3600.0

        if hours_since_update < 24:
            logger.info(
                "⏭️  Skipping %s - updated %.1f hours ago",
                symbol,
                hours_since_update,
            )
            return {
                "success": True,
                "skipped": True,
                "reason": "Recently updated",
            }

    # Fetch from Alpaca
    bars = fetch_alpaca_bars(symbol, timeframe, start_date, end_date)

    if not bars:
        logger.warning(f"No bars fetched for {symbol}")
        return {"success": False, "error": "No data returned"}

    # Persist to database
    inserted = persist_bars_v2(symbol, timeframe, bars)

    logger.info(f"✅ Completed {symbol}: {inserted} bars inserted")

    return {
        "success": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_fetched": len(bars),
        "bars_inserted": inserted,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical OHLC data to ohlc_bars_v2 using Alpaca"
    )
    parser.add_argument("--symbol", type=str, help="Single symbol to backfill")
    parser.add_argument("--symbols", nargs="+", help="Multiple symbols to backfill")
    parser.add_argument("--all", action="store_true", help="Backfill all watchlist symbols")
    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        choices=list(TIMEFRAME_CONFIG.keys()),
        help="Timeframe to backfill (default: d1)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force backfill even if recently updated"
    )

    args = parser.parse_args()

    # Determine symbols to process
    symbols = []
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    elif args.all:
        symbols = get_watchlist_symbols()
    else:
        logger.error("Must specify --symbol, --symbols, or --all")
        return 1

    logger.info(f"\n🚀 Starting Alpaca backfill for {len(symbols)} symbols")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Force: {args.force}")
    logger.info("Target table: ohlc_bars_v2 (provider=alpaca)")

    results = []
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}")

        result = backfill_symbol(
            symbol=symbol,
            timeframe=args.timeframe,
            force=args.force,
        )
        results.append(result)

        # Rate limiting between symbols
        if i < len(symbols):
            time.sleep(RATE_LIMIT_DELAY)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 BACKFILL SUMMARY")
    logger.info(f"{'='*60}")

    successful = [r for r in results if r.get("success")]
    skipped = [r for r in results if r.get("skipped")]
    failed = [r for r in results if not r.get("success")]

    total_bars = sum(r.get("bars_inserted", 0) for r in successful)

    logger.info(f"✅ Successful: {len(successful)}")
    logger.info(f"⏭️  Skipped: {len(skipped)}")
    logger.info(f"❌ Failed: {len(failed)}")
    logger.info(f"📊 Total bars inserted: {total_bars}")
    logger.info(f"Inserted {total_bars} bars")

    if failed:
        logger.info("\nFailed symbols:")
        for r in failed:
            logger.info(f"  - {r.get('symbol', 'unknown')}: {r.get('error', 'unknown error')}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
