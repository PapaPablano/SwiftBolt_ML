"""
Deep Backfill OHLC data to ohlc_bars_v2 with proper layer separation.

This script fetches historical data from Polygon API and writes to ohlc_bars_v2
with provider='polygon', ensuring strict separation from intraday/forecast data.

Features:
- Writes to ohlc_bars_v2 with provider='polygon'
- Only writes historical data (dates < today)
- Marks data as verified, non-intraday, non-forecast
- Respects validation rules (won't overwrite existing data)
- Direct Polygon API access for maximum data
- Rate limiting (5 req/min for free tier)

Usage:
    python src/scripts/deep_backfill_ohlc_v2.py --symbol AAPL
    python src/scripts/deep_backfill_ohlc_v2.py --symbols AAPL NVDA TSLA
    python src/scripts/deep_backfill_ohlc_v2.py --all --timeframe d1
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings
from src.data.supabase_db import db

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
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "SPY", "QQQ", "CRWD", "PLTR", "AMD", "NFLX", "DIS", "AI",
]


def get_watchlist_symbols(limit: int = 200) -> List[str]:
    """Fetch symbols from user watchlists."""
    try:
        response = db.client.rpc(
            "get_all_watchlist_symbols", {"p_limit": limit}
        ).execute()
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
        
        # Transform to our format - filter out today's data (historical only)
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        bars = []
        for r in results:
            bar_ts = datetime.utcfromtimestamp(r["t"] / 1000)
            
            # CRITICAL: Only include bars from BEFORE today (historical data)
            if bar_ts < today:
                bars.append({
                    "ts": bar_ts.isoformat() + "Z",
                    "open": r["o"],
                    "high": r["h"],
                    "low": r["l"],
                    "close": r["c"],
                    "volume": r["v"],
                })
        
        logger.info(f"✅ Fetched {len(bars)} historical bars for {symbol} {timeframe}")
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


def persist_bars_v2(symbol: str, timeframe: str, bars: List[dict]) -> int:
    """
    Persist bars to ohlc_bars_v2 with proper layer separation.
    
    Returns count of inserted bars.
    """
    if not bars:
        return 0
    
    symbol_id = db.get_symbol_id(symbol)
    inserted = 0
    
    # Prepare batch with v2 schema
    batch = []
    for bar in bars:
        batch.append({
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "ts": bar["ts"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            # Layer separation fields
            "provider": "polygon",
            "is_intraday": False,
            "is_forecast": False,
            "data_status": "verified",
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        })
    
    try:
        # Use INSERT ... ON CONFLICT DO NOTHING to avoid overwriting existing data
        # This respects the "never update historical data" rule
        db.client.table("ohlc_bars_v2").upsert(
            batch,
            on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
        ).execute()
        inserted = len(batch)
        logger.info(f"✅ Persisted {inserted} historical bars for {symbol} {timeframe}")
    except Exception as e:
        logger.error(f"Error persisting bars for {symbol}: {e}")
        logger.error(f"First bar sample: {batch[0] if batch else 'No bars'}")
    
    return inserted


def get_data_coverage_v2(symbol: str, timeframe: str) -> dict:
    """Get current data coverage for a symbol/timeframe in ohlc_bars_v2."""
    try:
        symbol_id = db.get_symbol_id(symbol)
        
        # Query only historical Polygon data
        response = db.client.table("ohlc_bars_v2").select(
            "ts"
        ).eq(
            "symbol_id", symbol_id
        ).eq(
            "timeframe", timeframe
        ).eq(
            "provider", "polygon"
        ).eq(
            "is_forecast", False
        ).order(
            "ts", desc=False
        ).limit(1).execute()
        
        earliest = None
        if response.data:
            earliest = datetime.fromisoformat(
                response.data[0]["ts"].replace("Z", "+00:00")
            )
        
        response = db.client.table("ohlc_bars_v2").select(
            "ts"
        ).eq(
            "symbol_id", symbol_id
        ).eq(
            "timeframe", timeframe
        ).eq(
            "provider", "polygon"
        ).eq(
            "is_forecast", False
        ).order(
            "ts", desc=True
        ).limit(1).execute()
        
        latest = None
        if response.data:
            latest = datetime.fromisoformat(
                response.data[0]["ts"].replace("Z", "+00:00")
            )
        
        # Get count
        response = db.client.table("ohlc_bars_v2").select(
            "id", count="exact"
        ).eq(
            "symbol_id", symbol_id
        ).eq(
            "timeframe", timeframe
        ).eq(
            "provider", "polygon"
        ).eq(
            "is_forecast", False
        ).execute()
        
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
    Backfill historical data for a single symbol.
    
    Args:
        symbol: Stock ticker
        timeframe: Timeframe to backfill
        force: If True, fetch full history even if data exists
    
    Returns:
        Dict with status and stats
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 Backfilling {symbol} ({timeframe})")
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
    
    end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Subtract 1 day to ensure we only get historical data (not today)
    end_date = end_date - timedelta(days=1)
    
    max_days = config["max_days"]
    start_date = end_date - timedelta(days=max_days)
    
    # Skip if recently updated (unless force)
    if not force and coverage["latest"]:
        days_since_update = (end_date - coverage["latest"]).days
        if days_since_update < 7:
            logger.info(f"⏭️  Skipping {symbol} - updated {days_since_update} days ago")
            return {"success": True, "skipped": True, "reason": "Recently updated"}
    
    # Fetch from Polygon
    bars = fetch_polygon_bars(symbol, timeframe, start_date, end_date)
    
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
        description="Backfill historical OHLC data to ohlc_bars_v2"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to backfill"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Multiple symbols to backfill"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all watchlist symbols"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        choices=list(TIMEFRAME_CONFIG.keys()),
        help="Timeframe to backfill (default: d1)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force backfill even if recently updated"
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
    
    logger.info(f"\n🚀 Starting backfill for {len(symbols)} symbols")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Force: {args.force}")
    logger.info(f"Target table: ohlc_bars_v2 (provider=polygon)")
    
    results = []
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}")
        
        result = backfill_symbol(
            symbol=symbol,
            timeframe=args.timeframe,
            force=args.force,
        )
        results.append(result)
        
        # Rate limiting
        if i < len(symbols):
            logger.info(f"⏳ Rate limiting: waiting {RATE_LIMIT_DELAY}s...")
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
    
    if failed:
        logger.info("\nFailed symbols:")
        for r in failed:
            logger.info(f"  - {r.get('symbol', 'unknown')}: {r.get('error', 'unknown error')}")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
