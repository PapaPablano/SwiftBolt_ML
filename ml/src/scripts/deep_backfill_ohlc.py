"""
Deep Backfill OHLC data directly from Alpaca API.

This script fetches maximum historical data (up to 7 years)
directly from Alpaca, bypassing the Edge Function limitations.

Features:
- Direct Alpaca API access for maximum data
- Configurable lookback period (default: 7 years)
- All timeframes support (d1, w1, h1, h4, m15)
- Rate limiting (200 req/min for Alpaca)
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

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from src.data.supabase_db import db  # noqa: E402
from src.data.data_validator import OHLCValidator  # noqa: E402

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

# OHLC data validator for pre-insertion validation
_ohlc_validator = OHLCValidator()

# Timeframe configurations (Alpaca format)
TIMEFRAME_CONFIG = {
    "m1": {"alpaca_tf": "1Min", "max_days": 7},
    "m5": {"alpaca_tf": "5Min", "max_days": 30},
    "m15": {"alpaca_tf": "15Min", "max_days": 60},
    "m30": {"alpaca_tf": "30Min", "max_days": 60},
    "h1": {"alpaca_tf": "1Hour", "max_days": 180},
    "h4": {"alpaca_tf": "4Hour", "max_days": 365},
    "d1": {"alpaca_tf": "1Day", "max_days": 2555},  # 7 years
    "w1": {"alpaca_tf": "1Week", "max_days": 2555},  # 7 years
    "mn1": {"alpaca_tf": "1Month", "max_days": 3650},  # 10 years
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
    Fetch OHLC bars directly from Alpaca API with automatic pagination.

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

            response = requests.get(
                url,
                headers=get_alpaca_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Extract bars for this symbol
            bars_data = data.get("bars", {}).get(symbol.upper(), [])

            if not bars_data and page_count == 0:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []

            # Transform to our format
            for bar in bars_data:
                all_bars.append(
                    {
                        "ts": bar["t"],  # Already RFC-3339 format
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
                time.sleep(RATE_LIMIT_DELAY)
            else:
                break

        logger.info(f"✅ Fetched {len(all_bars)} bars for {symbol} {timeframe}")
        return all_bars

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded! Wait before retrying.")
        elif e.response.status_code == 401:
            logger.error("Authentication failed! Verify Alpaca API credentials.")
        else:
            logger.error(f"HTTP error fetching {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def persist_bars(symbol: str, timeframe: str, bars: List[dict]) -> int:
    """
    Persist bars to ohlc_bars_v2 with provider='alpaca'.

    Validates OHLC data before insertion to prevent contaminated data
    from reaching Supabase.

    Returns count of inserted bars.
    """
    if not bars:
        return 0

    # Convert to DataFrame for validation
    df = pd.DataFrame(bars)

    # Validate OHLC data before insertion
    df, validation_result = _ohlc_validator.validate(df, fix_issues=True)

    if validation_result.rows_removed > 0:
        logger.warning(
            f"Removed {validation_result.rows_removed} invalid rows for {symbol} {timeframe}"
        )

    if validation_result.issues:
        for issue in validation_result.issues:
            logger.warning(f"{symbol} {timeframe}: {issue}")

    # If all rows were removed, don't proceed
    if df.empty:
        logger.error(f"All data removed during validation for {symbol} {timeframe}")
        return 0

    symbol_id = db.get_symbol_id(symbol)
    inserted = 0

    # Batch upsert for efficiency
    batch = []
    for _, row in df.iterrows():
        batch.append(
            {
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": row["ts"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "provider": "alpaca",
                "is_forecast": False,
                "data_status": "verified",
            }
        )

    try:
        # Batch upsert (1000 rows per request limit)
        batch_size = 1000
        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            db.client.table("ohlc_bars_v2").upsert(
                chunk,
                on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
            ).execute()
            inserted += len(chunk)

        logger.info(f"✅ Persisted {inserted} bars for {symbol} {timeframe}")
    except Exception as e:
        logger.error(f"Error persisting bars for {symbol}: {e}")

    return inserted


def get_data_coverage(symbol: str, timeframe: str) -> dict:
    """Get current data coverage for a symbol/timeframe in ohlc_bars_v2."""
    try:
        symbol_id = db.get_symbol_id(symbol)
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
        logger.warning(f"Could not get coverage for {symbol}: {e}")
        return {"earliest": None, "latest": None, "count": 0}


def backfill_symbol(
    symbol: str,
    timeframe: str,
    days_back: Optional[int] = None,
    force: bool = False,
) -> bool:
    """
    Backfill a single symbol/timeframe using Alpaca API.

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

    # Fetch from Alpaca
    bars = fetch_alpaca_bars(symbol, timeframe, start_date, end_date)

    if not bars:
        logger.warning(f"No bars fetched for {symbol} {timeframe}")
        return False

    # Persist to database
    inserted = persist_bars(symbol, timeframe, bars)

    return inserted > 0


def main():
    parser = argparse.ArgumentParser(description="Deep backfill OHLC data directly from Alpaca API")

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

    # Validate Alpaca credentials
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        logger.error("❌ ALPACA_API_KEY and ALPACA_API_SECRET must be set!")
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
    logger.info("Deep OHLC Backfill (Alpaca API)")
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
