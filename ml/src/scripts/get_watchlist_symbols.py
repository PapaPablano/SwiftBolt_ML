"""Fetch unique symbols from user watchlists for priority ranking."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scripts.universe_utils import resolve_symbol_list  # noqa: E402


def get_watchlist_symbols() -> list[str]:
    """
    Fetch all unique symbols from user watchlists.

    Returns:
        List of unique ticker symbols
    """
    try:
        return resolve_symbol_list()
    except Exception as e:  # pragma: no cover - CLI helper fallback
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
