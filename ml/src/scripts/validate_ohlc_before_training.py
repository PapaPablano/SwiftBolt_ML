#!/usr/bin/env python
"""
OHLC Data Quality Validation Before ML Training

Validates OHLC data quality before training to catch data issues early.
Separates critical errors (fail training) from warnings (logged but non-blocking).
Uses parallel processing for improved performance.

Usage:
    python -m src.scripts.validate_ohlc_before_training [--symbols SYMBOL1,SYMBOL2] [--limit 10] [--workers 4]
"""

import os
import sys
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from dotenv import load_dotenv

load_dotenv()

from src.data.data_validator import OHLCValidator
from src.data.supabase_db import db
from src.scripts.universe_utils import get_symbol_universe


def validate_symbol(symbol: str, validator: OHLCValidator, critical_keywords: list, output_lock: Lock):
    """Validate a single symbol (thread-safe)."""
    symbol = symbol.strip()
    if not symbol:
        return None, None

    try:
        # Check daily timeframe (used for training)
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)
        if df.empty:
            with output_lock:
                print(f"⚠️ {symbol}: No data found")
            return f"{symbol}: No data found", None

        df, result = validator.validate(df, fix_issues=False)

        if result.issues:
            # Separate critical issues from warnings
            symbol_critical = []
            symbol_warnings = []

            for issue in result.issues:
                is_critical = any(keyword in issue for keyword in critical_keywords)
                if is_critical:
                    symbol_critical.append(issue)
                else:
                    # Outliers and gaps are warnings, not critical
                    symbol_warnings.append(issue)

            if symbol_critical:
                error_msg = f"{symbol}: {symbol_critical}"
                with output_lock:
                    print(f"❌ {error_msg}")
                return None, error_msg
            else:
                # Only warnings (outliers/gaps) - acceptable
                with output_lock:
                    print(f"⚠️ {symbol}: {symbol_warnings} (non-critical)")
                return f"{symbol}: {symbol_warnings}", None
        else:
            with output_lock:
                print(f"✅ {symbol}: OHLC validation passed ({len(df)} bars)")
            return None, None
    except Exception as e:
        error_msg = f"{symbol}: {str(e)}"
        with output_lock:
            print(f"❌ {symbol}: Validation error - {e}")
        return None, error_msg


def main():
    parser = ArgumentParser(description="Validate OHLC data before ML training")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols to validate")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of symbols to check")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    args = parser.parse_args()

    validator = OHLCValidator()

    # Get symbols - handle watchlist_items.created_at error gracefully
    try:
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        else:
            universe = get_symbol_universe()
            symbols = universe.get("symbols", []) or ["SPY", "AAPL", "NVDA", "MSFT"]
    except Exception as e:
        print(f"⚠️ Unable to fetch watchlist symbols: {e}")
        print("   Using default symbols: SPY, AAPL, NVDA, MSFT")
        symbols = ["SPY", "AAPL", "NVDA", "MSFT"]

    # Limit to specified number of symbols for performance
    symbols_to_check = symbols[: args.limit]
    critical_errors = []
    warnings = []

    # Define critical issues that should fail the workflow
    critical_keywords = [
        "High < max(Open,Close)",
        "Low > min(Open,Close)",
        "Negative volume",
        "Non-positive",
    ]

    output_lock = Lock()

    # Use parallel processing for symbol validation
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(validate_symbol, symbol, validator, critical_keywords, output_lock): symbol
            for symbol in symbols_to_check
        }

        for future in as_completed(futures):
            warning, error = future.result()
            if warning:
                warnings.append(warning)
            if error:
                critical_errors.append(error)

    # Only fail on critical errors
    if critical_errors:
        print("")
        print("❌ OHLC validation failed for some symbols (critical issues):")
        for error in critical_errors:
            print(f"  - {error}")
        print("")
        print("::error::Critical OHLC data quality issues detected. ML training may produce unreliable results.")
        sys.exit(1)

    # Show warnings but don't fail
    if warnings:
        print("")
        print("⚠️ OHLC validation warnings (non-critical):")
        for warning in warnings:
            print(f"  - {warning}")
        print("")
        print("::warning::Some OHLC data quality warnings detected (outliers/gaps). These are common in real market data.")

    print("")
    print("✅ OHLC validation passed for all checked symbols (critical checks only)")


if __name__ == "__main__":
    main()
