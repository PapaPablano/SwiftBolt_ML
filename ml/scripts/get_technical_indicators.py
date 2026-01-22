#!/usr/bin/env python3
"""
CLI script to fetch and calculate technical indicators for a symbol/timeframe.
Returns JSON output for use by Edge Functions.

Usage:
    python get_technical_indicators.py --symbol AAPL --timeframe d1

Output:
    JSON object with all technical indicators for the latest bar.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.features.technical_indicators import add_technical_features

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs
logger = logging.getLogger(__name__)


def get_latest_indicators(symbol: str, timeframe: str = "d1", lookback_bars: int = 500) -> dict:
    """
    Fetch OHLC data and calculate technical indicators.
    
    Args:
        symbol: Stock ticker symbol
        timeframe: Timeframe (d1, h1, m15, etc.)
        lookback_bars: Number of bars to fetch for indicator calculation
        
    Returns:
        Dictionary with latest indicator values
    """
    try:
        # Initialize database
        db = SupabaseDatabase()
        
        # Fetch OHLC bars
        df = db.fetch_ohlc_bars(symbol=symbol, timeframe=timeframe, limit=lookback_bars)
        
        if df.empty:
            return {
                "error": f"No OHLC data found for {symbol} ({timeframe})",
                "symbol": symbol,
                "timeframe": timeframe
            }
        
        # Calculate technical indicators
        df_with_indicators = add_technical_features(df)
        
        # Get latest bar (most recent)
        latest = df_with_indicators.iloc[-1]
        
        # Extract all indicator columns (exclude OHLC base columns)
        base_columns = {"ts", "open", "high", "low", "close", "volume"}
        indicator_columns = [col for col in df_with_indicators.columns if col not in base_columns]
        
        # Build indicators dictionary
        indicators = {}
        for col in indicator_columns:
            value = latest[col]
            # Convert numpy types to native Python types for JSON serialization
            if hasattr(value, 'item'):  # numpy scalar
                indicators[col] = value.item()
            elif pd.isna(value):
                indicators[col] = None
            else:
                indicators[col] = float(value) if isinstance(value, (int, float)) else str(value)
        
        # Get timestamp
        timestamp = latest["ts"]
        if hasattr(timestamp, 'isoformat'):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)
        
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "timestamp": timestamp_str,
            "indicators": indicators,
            "price": {
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "close": float(latest["close"]),
                "volume": float(latest["volume"])
            },
            "bars_used": len(df_with_indicators)
        }
        
    except Exception as e:
        logger.error(f"Error calculating indicators for {symbol}: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol,
            "timeframe": timeframe
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Get technical indicators for a symbol")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, m15, etc.)")
    parser.add_argument("--lookback", type=int, default=500, help="Number of bars to fetch")
    
    args = parser.parse_args()
    
    result = get_latest_indicators(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_bars=args.lookback
    )
    
    # Output JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
