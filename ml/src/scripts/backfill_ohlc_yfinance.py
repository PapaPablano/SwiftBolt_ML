"""
Backfill historical OHLC data using Yahoo Finance.
Yahoo Finance is more reliable than Polygon for historical data.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

import yfinance as yf

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_symbols(limit: int = None) -> list[str]:
    """Fetch symbols from watchlists."""
    try:
        response = db.client.rpc(
            "get_all_watchlist_symbols", {"p_limit": limit}
        ).execute()
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
            db.client.table("symbols")
            .select("id")
            .eq("ticker", symbol.upper())
            .single()
            .execute()
        )
        symbol_id = symbol_response.data["id"]
        
        # Fetch data from Yahoo Finance
        logger.info(f"📥 Fetching {symbol} data from Yahoo Finance...")
        ticker = yf.Ticker(symbol)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df = ticker.history(start=start_date, end=end_date, interval='1d')
        
        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return 0
        
        logger.info(f"✅ Fetched {len(df)} bars for {symbol}")
        
        # Convert to database format
        bars = []
        for idx, row in df.iterrows():
            # Skip bars with extreme intraday ranges (>25%) - likely data errors
            intraday_range_pct = ((row['High'] - row['Low']) / row['Close']) * 100
            if intraday_range_pct > 25:
                logger.warning(
                    f"⚠️  Skipping {symbol} {idx.date()}: extreme range {intraday_range_pct:.1f}%"
                )
                continue
            
            # Skip bars with zero range (placeholder data)
            if row['High'] == row['Low'] == row['Open'] == row['Close']:
                logger.warning(f"⚠️  Skipping {symbol} {idx.date()}: zero range bar")
                continue
            
            bars.append({
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": idx.isoformat(),
                "open": round(float(row['Open']), 4),
                "high": round(float(row['High']), 4),
                "low": round(float(row['Low']), 4),
                "close": round(float(row['Close']), 4),
                "volume": int(row['Volume']),
                "provider": "yfinance",
                "is_intraday": False,
                "is_forecast": False,
                "data_status": "verified",
            })
        
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
    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to backfill (e.g., AAPL)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of days to backfill (default: 730)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of symbols to process"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="d1",
        choices=["d1"],
        help="Timeframe (default: d1)"
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
        
        bars_inserted = backfill_symbol(
            symbol=symbol,
            days=args.days,
            timeframe=args.timeframe
        )
        
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
