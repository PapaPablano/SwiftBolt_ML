#!/usr/bin/env python
"""
Unified ML Validation Report

Runs comprehensive validation with real database scores including:
- Live predictions validation
- Drift detection with severity classification
- Multi-timeframe reconciliation
- Retraining trigger detection

Uses parallel async processing for improved performance.

Usage:
    python -m src.scripts.run_unified_validation_report [--symbols SYMBOL1,SYMBOL2] [--workers 4]
"""

import asyncio
import os
import sys
from argparse import ArgumentParser

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, "src")

from src.services.validation_service import ValidationService


DEFAULT_SYMBOLS = ["AAPL", "NVDA", "MSFT", "TSLA", "META", "AMD", "CRWD", "GOOGL", "AMZN"]


def main():
    parser = ArgumentParser(description="Run unified ML validation report")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols to validate")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel validation workers")
    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = DEFAULT_SYMBOLS

    service = ValidationService()

    print("=" * 60)
    print("UNIFIED VALIDATION REPORT (Real Database Scores)")
    print("=" * 60)
    print("")
    print("Note: If live_predictions table is empty, scores will use conservative defaults.")
    print("      This is expected until predictions are written to the database.")
    print("")

    drift_alerts = []
    validation_errors = []
    missing_live_data = []

    async def validate_symbol(symbol, semaphore):
        async with semaphore:
            try:
                # Fetch actual validation from database
                # Use BULLISH as default direction (can be enhanced to fetch actual direction)
                result = await service.get_live_validation(symbol, "BULLISH")

                # Check if using default scores (indicates missing data)
                using_defaults = (
                    result.live_score == 0.50 and
                    result.backtesting_score == 0.55 and
                    result.walkforward_score == 0.60
                )

                status = result.get_status_emoji()
                print(f"{status} {symbol}: {result.unified_confidence:.1%} confidence")
                print(f"   Drift: {result.drift_severity} ({result.drift_magnitude:.0%})")
                print(f"   Consensus: {result.consensus_direction}")

                if using_defaults:
                    missing_live_data.append(symbol)
                    print(f"   ℹ️  Using default scores (live_predictions table empty)")

                if result.drift_detected:
                    drift_alerts.append({
                        "symbol": symbol,
                        "severity": result.drift_severity,
                        "magnitude": result.drift_magnitude,
                        "recommendation": result.recommendation,
                    })

                if result.retraining_trigger:
                    print(f"   ⚠️ RETRAINING TRIGGERED: {result.retraining_reason}")

                return None
            except Exception as e:
                error_msg = f"{symbol}: {str(e)}"
                validation_errors.append(error_msg)
                print(f"⚠️ {error_msg}")
                return error_msg

    # Run async validation for all symbols with concurrency control
    async def run_all_validations():
        semaphore = asyncio.Semaphore(args.workers)
        tasks = [validate_symbol(symbol, semaphore) for symbol in symbols]
        await asyncio.gather(*tasks)

    asyncio.run(run_all_validations())

    print("")
    print("=" * 60)

    if validation_errors:
        print(f"⚠️ VALIDATION ERRORS: {len(validation_errors)} symbols")
        for error in validation_errors:
            print(f"   - {error}")
        print("")

    if missing_live_data:
        print(f"ℹ️  MISSING LIVE DATA: {len(missing_live_data)} symbols using default scores")
        print(f"   Symbols: {', '.join(missing_live_data)}")
        print("   This is expected until predictions are written to live_predictions table.")
        print("")

    if drift_alerts:
        print(f"⚠️ DRIFT ALERTS: {len(drift_alerts)} symbols")
        for alert in drift_alerts:
            print(f"   - {alert['symbol']}: {alert['severity']} drift ({alert['magnitude']:.0%})")
    else:
        print("✅ No drift alerts")

    print("=" * 60)
    print("✅ Unified validation complete")

    # Return non-zero exit code if there were validation errors
    if validation_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
