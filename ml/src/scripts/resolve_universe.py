"""CLI to resolve symbol/timeframe universe for workflows."""

from __future__ import annotations

import argparse
import json

from src.scripts.universe_utils import get_symbol_universe, format_env_exports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        choices={"env", "json"},
        default="env",
        help="Output format: shell env lines or JSON payload.",
    )
    parser.add_argument(
        "--include-timeframes",
        action="store_true",
        default=True,
        help="Include timeframe list in the payload (default true).",
    )
    parser.add_argument(
        "--no-timeframes",
        action="store_true",
        help="Exclude timeframe list (overrides --include-timeframes).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_timeframes = not args.no_timeframes and args.include_timeframes
    universe = get_symbol_universe(include_timeframes=include_timeframes)
    symbols = universe.get("symbols", [])
    timeframes = universe.get("timeframes", [])
    if args.output == "json":
        print(json.dumps(universe))
    else:
        print(format_env_exports(symbols, timeframes), end="")


if __name__ == "__main__":
    main()
