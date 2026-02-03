#!/usr/bin/env python3
"""
Validate sentiment variance for all benchmark symbols after backfill.

Run from ml/ after Phase 2 (90-day backfill):
  cd ml && python validate_all_sentiment.py
  cd ml && python validate_all_sentiment.py --lookback 90

Success criteria per symbol: std > 0.01, mean_abs_daily_change > 0.005, range > 0.05.
If all pass, you can re-enable sentiment in SIMPLIFIED_FEATURES and set ENABLE_SENTIMENT_FEATURES=true.
"""

import argparse
import sys
from pathlib import Path

# Run from ml/
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_SYMBOLS = [
    "TSLA",
    "NVDA",
    "AAPL",
    "MSFT",
    "META",
    "GOOG",
    "GOOGL",
    "SPY",
    "AMD",
    "CRWD",
    "HL",
    "MU",
]


def main():
    parser = argparse.ArgumentParser(description="Validate sentiment variance for all symbols")
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbols",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=90,
        help="Lookback days for variance check (default 90)",
    )
    args = parser.parse_args()

    try:
        from src.features.stock_sentiment import validate_sentiment_variance
    except ImportError as e:
        print(f"Import error: {e}")
        sys.exit(1)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    lookback = max(30, args.lookback)

    print("\n" + "=" * 60)
    print(f"SENTIMENT VARIANCE VALIDATION (lookback={lookback} days)")
    print("=" * 60 + "\n")

    results = {}
    for symbol in symbols:
        try:
            passed = validate_sentiment_variance(symbol, lookback_days=lookback)
            results[symbol] = "PASS" if passed else "FAIL"
        except Exception as e:
            results[symbol] = f"ERROR: {str(e)[:40]}"

    for symbol, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {symbol:6s}: {status}")

    all_passed = all(v == "PASS" for v in results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL SYMBOLS VALIDATED — Ready to enable sentiment features")
        print("   Next: set ENABLE_SENTIMENT_FEATURES=true and re-add sentiment to SIMPLIFIED_FEATURES")
    else:
        failing = [s for s, v in results.items() if v != "PASS"]
        print(f"⚠️  {len(failing)} symbol(s) failed: {', '.join(failing)}")
        print("   Check backfill logs and FinViz/API response quality; low-news symbols may fail.")
    print("=" * 60 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
