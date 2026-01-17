"""
Refresh Underlying History Script

Fetches 7-day underlying price history from Alpaca and stores it in
the options_underlying_history table for options ranking enhancement.

Usage:
    python -m src.scripts.refresh_underlying_history --symbol AAPL
    python -m src.scripts.refresh_underlying_history --all --timeframe d1
    python -m src.scripts.refresh_underlying_history --watchlist

Features:
    - Fetches daily OHLC bars from Alpaca API
    - Computes 7-day metrics: return, volatility, drawdown, gap count
    - Stores in options_underlying_history table
    - Rate limiting with exponential backoff
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from root .env file
root_dir = Path(__file__).parent.parent.parent.parent
load_dotenv(root_dir / ".env")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.alpaca_underlying_history import (
    AlpacaUnderlyingHistoryClient,
    compute_all_metrics,
    metrics_to_dict,
)
from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiting
RATE_LIMIT_DELAY = 0.3  # 200 req/min for Alpaca

# Default symbols if no watchlist available
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
    "AMD",
]


def get_watchlist_symbols(limit: int = 100) -> list[str]:
    """Fetch symbols from user watchlists."""
    try:
        response = db.client.rpc(
            "get_all_watchlist_symbols",
            {"p_limit": limit},
        ).execute()
        if response.data:
            symbols = [row["ticker"] for row in response.data]
            logger.info(f"Fetched {len(symbols)} symbols from watchlists")
            return symbols
    except Exception as e:
        logger.warning(f"Could not fetch watchlist: {e}")

    logger.info("Using default symbol list")
    return DEFAULT_SYMBOLS


async def refresh_symbol(
    client: AlpacaUnderlyingHistoryClient,
    symbol: str,
    timeframe: str = "d1",
    lookback_days: int = 7,
) -> dict:
    """
    Refresh underlying history for a single symbol.

    Args:
        client: Alpaca client instance
        symbol: Stock ticker symbol
        timeframe: Timeframe (default 'd1')
        lookback_days: Days of history to fetch

    Returns:
        Dict with status and stats
    """
    try:
        # Get symbol ID
        symbol_id = db.get_symbol_id(symbol)

        # Fetch bars from Alpaca
        bars_df = await client.fetch_bars(symbol, timeframe, lookback_days)

        if bars_df.empty:
            logger.warning(f"No bars returned for {symbol}")
            return {
                "symbol": symbol,
                "success": False,
                "error": "No data returned",
            }

        # Compute metrics
        metrics = compute_all_metrics(bars_df, symbol, timeframe)

        # Prepare records for upsert
        records = []
        for _, row in bars_df.iterrows():
            ts = row["ts"]
            if hasattr(ts, "isoformat"):
                ts = ts.isoformat()

            record = {
                "underlying_symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "ret_7d": metrics.return_7d,
                "vol_7d": metrics.volatility_7d,
                "drawdown_7d": metrics.drawdown_7d,
                "gap_count": metrics.gap_count,
                "source_provider": "alpaca",
            }
            records.append(record)

        # Upsert to database
        count = db.upsert_underlying_history(symbol_id, timeframe, records)

        logger.info(
            f"{symbol}: ret={metrics.return_7d:.2f}%, "
            f"vol={metrics.volatility_7d:.1f}%, "
            f"dd={metrics.drawdown_7d:.1f}%, "
            f"gaps={metrics.gap_count}, "
            f"bars={count}"
        )

        return {
            "symbol": symbol,
            "success": True,
            "bars_upserted": count,
            "ret_7d": metrics.return_7d,
            "vol_7d": metrics.volatility_7d,
            "drawdown_7d": metrics.drawdown_7d,
            "gap_count": metrics.gap_count,
        }

    except Exception as e:
        logger.error(f"Error refreshing {symbol}: {e}")
        return {
            "symbol": symbol,
            "success": False,
            "error": str(e),
        }


async def refresh_all(
    symbols: list[str],
    timeframe: str = "d1",
    lookback_days: int = 7,
) -> list[dict]:
    """
    Refresh underlying history for multiple symbols.

    Args:
        symbols: List of stock ticker symbols
        timeframe: Timeframe
        lookback_days: Days of history

    Returns:
        List of result dicts
    """
    client = AlpacaUnderlyingHistoryClient()
    results = []

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processing {symbol}")

        result = await refresh_symbol(client, symbol, timeframe, lookback_days)
        results.append(result)

        # Rate limiting
        if i < len(symbols):
            await asyncio.sleep(RATE_LIMIT_DELAY)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Refresh underlying history from Alpaca for options ranking"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to refresh",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Multiple symbols to refresh",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh all default symbols",
    )
    parser.add_argument(
        "--watchlist",
        action="store_true",
        help="Refresh all watchlist symbols",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        choices=["m15", "h1", "h4", "d1", "w1"],
        help="Timeframe to refresh (default: d1)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=7,
        help="Days of history to fetch (default: 7)",
    )

    args = parser.parse_args()

    # Determine symbols to process
    symbols = []
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    elif args.watchlist:
        symbols = get_watchlist_symbols()
    elif args.all:
        symbols = DEFAULT_SYMBOLS
    else:
        logger.error("Must specify --symbol, --symbols, --all, or --watchlist")
        return 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Refreshing underlying history for {len(symbols)} symbols")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Lookback: {args.lookback} days")
    logger.info(f"{'='*60}")

    # Run async refresh
    start_time = time.time()
    results = asyncio.run(refresh_all(symbols, args.timeframe, args.lookback))
    elapsed = time.time() - start_time

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("REFRESH SUMMARY")
    logger.info(f"{'='*60}")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    total_bars = sum(r.get("bars_upserted", 0) for r in successful)

    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    logger.info(f"Total bars upserted: {total_bars}")
    logger.info(f"Elapsed time: {elapsed:.1f}s")

    if failed:
        logger.info("\nFailed symbols:")
        for r in failed:
            logger.info(f"  - {r.get('symbol')}: {r.get('error')}")

    # Log aggregate metrics
    if successful:
        avg_ret = sum(r.get("ret_7d", 0) for r in successful) / len(successful)
        avg_vol = sum(r.get("vol_7d", 0) for r in successful) / len(successful)
        logger.info(f"\nAggregate metrics:")
        logger.info(f"  Average 7d return: {avg_ret:.2f}%")
        logger.info(f"  Average 7d volatility: {avg_vol:.1f}%")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
