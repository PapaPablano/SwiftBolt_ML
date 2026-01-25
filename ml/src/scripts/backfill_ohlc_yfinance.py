"""
Backfill historical OHLC data using Yahoo Finance.
Yahoo Finance is more reliable than Polygon for historical data.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.data_validator import OHLCValidator  # noqa: E402
from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OHLC data validator for pre-insertion validation
_ohlc_validator = OHLCValidator()


def get_symbols(limit: int = None) -> list[str]:
    """Fetch symbols from watchlists."""
    try:
        response = db.client.rpc("get_all_watchlist_symbols", {"p_limit": limit}).execute()
        if response.data:
            symbols = [row["ticker"] for row in response.data]
            logger.info(f"📋 Fetched {len(symbols)} symbols from watchlists")
            return symbols
        return []
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return []


def backfill_symbol(symbol: str, days: int = 730, timeframe: str = "d1") -> int:
    """
    Backfill historical data for a symbol using Yahoo Finance.

    Validates OHLC data before insertion to prevent contaminated data
    from reaching Supabase.

    Args:
        symbol: Stock ticker
        days: Number of days to backfill
        timeframe: Timeframe (d1 only for now)

    Returns:
        Number of bars inserted
    """
    try:
        # Get symbol_id
        symbol_response = (
            db.client.table("symbols").select("id").eq("ticker", symbol.upper()).single().execute()
        )
        symbol_id = symbol_response.data["id"]

        # Fetch data from Yahoo Finance
        logger.info(f"📥 Fetching {symbol} data from Yahoo Finance...")
        ticker = yf.Ticker(symbol)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        df = ticker.history(start=start_date, end=end_date, interval="1d")

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return 0

        logger.info(f"✅ Fetched {len(df)} bars for {symbol}")

        # Convert to DataFrame format for validation
        validation_df = pd.DataFrame(
            {
                "ts": [idx.isoformat() for idx in df.index],
                "open": df["Open"].values,
                "high": df["High"].values,
                "low": df["Low"].values,
                "close": df["Close"].values,
                "volume": df["Volume"].values,
            }
        )

        # Validate OHLC data before insertion
        validation_df, validation_result = _ohlc_validator.validate(validation_df, fix_issues=True)

        if validation_result.rows_removed > 0:
            logger.warning(
                f"Removed {validation_result.rows_removed} invalid rows for {symbol} {timeframe}"
            )

        if validation_result.issues:
            for issue in validation_result.issues:
                logger.warning(f"{symbol} {timeframe}: {issue}")

        # If all rows were removed, don't proceed
        if validation_df.empty:
            logger.error(f"All data removed during validation for {symbol} {timeframe}")
            return 0

        # Convert to database format
        bars = []
        for _, row in validation_df.iterrows():
            bars.append(
                {
                    "symbol_id": symbol_id,
                    "timeframe": timeframe,
                    "ts": row["ts"],
                    "open": round(float(row["open"]), 4),
                    "high": round(float(row["high"]), 4),
                    "low": round(float(row["low"]), 4),
                    "close": round(float(row["close"]), 4),
                    "volume": int(row["volume"]),
                    "provider": "yfinance",
                    "is_intraday": False,
                    "is_forecast": False,
                    "data_status": "verified",
                }
            )

        if not bars:
            logger.warning(f"No valid bars to insert for {symbol}")
            return 0

        # Upsert to database (handles duplicates gracefully)
        logger.info(f"💾 Upserting {len(bars)} bars for {symbol}...")
        db.client.table("ohlc_bars_v2").upsert(
            bars,
            on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
        ).execute()

        logger.info(f"✅ Successfully backfilled {len(bars)} bars for {symbol}")
        return len(bars)

    except Exception as e:
        logger.error(f"❌ Error backfilling {symbol}: {e}")
        return 0


def main():
    """Main backfill process."""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill OHLC data from Yahoo Finance")
    parser.add_argument("--symbol", type=str, help="Single symbol to backfill (e.g., AAPL)")
    parser.add_argument(
        "--days", type=int, default=730, help="Number of days to backfill (default: 730)"
    )
    parser.add_argument("--limit", type=int, help="Limit number of symbols to process")
    parser.add_argument(
        "--timeframe", type=str, default="d1", choices=["d1"], help="Timeframe (default: d1)"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Starting Yahoo Finance Historical Data Backfill")
    logger.info("=" * 80)

    if args.symbol:
        # Single symbol mode
        symbols = [args.symbol.upper()]
    else:
        # Batch mode - get all watchlist symbols
        symbols = get_symbols(limit=args.limit)

    if not symbols:
        logger.error("No symbols to process")
        return

    total_bars = 0
    success_count = 0

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}...")

        bars_inserted = backfill_symbol(symbol=symbol, days=args.days, timeframe=args.timeframe)

        if bars_inserted > 0:
            success_count += 1
            total_bars += bars_inserted

    logger.info("\n" + "=" * 80)
    logger.info("✅ Backfill Complete!")
    logger.info(f"   Symbols processed: {success_count}/{len(symbols)}")
    logger.info(f"   Total bars inserted: {total_bars}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
