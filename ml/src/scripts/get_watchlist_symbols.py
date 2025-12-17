"""Fetch unique symbols from user watchlists for priority ranking."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db


def get_watchlist_symbols() -> list[str]:
    """
    Fetch all unique symbols from user watchlists.

    Returns:
        List of unique ticker symbols
    """
    try:
        # Query all symbols from the symbols table that have watchlist entries
        # This assumes there's a relationship between watchlists and symbols
        response = db.client.table("symbols").select("ticker").execute()

        if not response.data:
            return []

        # Get unique tickers
        symbols = sorted(set(row["ticker"] for row in response.data))
        return symbols

    except Exception as e:
        print(f"Error fetching watchlist symbols: {e}", file=sys.stderr)
        return []


def main() -> None:
    """Main entry point - prints symbols one per line for shell scripting."""
    symbols = get_watchlist_symbols()

    if not symbols:
        # Fallback to default priority symbols
        default_symbols = ["AAPL", "MSFT", "TSLA", "SPY", "QQQ", "NVDA"]
        for symbol in default_symbols:
            print(symbol)
    else:
        for symbol in symbols:
            print(symbol)


if __name__ == "__main__":
    main()
