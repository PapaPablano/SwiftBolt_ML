#!/usr/bin/env python3
"""Generate binary (up/down) forecasts and write to ml_forecasts for chart overlay.

Usage (run from ml/):
    PYTHONPATH=. python scripts/generate_binary_forecasts.py

This will:
  - Loop over a symbol universe (default: AAPL, MSFT, SPY, PG, NVDA)
  - For each horizon (1D, 5D, 10D) train BinaryForecaster and predict
  - Upsert to ml_forecasts with model_type=binary, timeframe=d1

chart-data-v2 and SwiftUI then show these forecasts via mlSummary and forecast layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add ml directory so api.routers is importable
ml_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ml_dir))

from api.routers.binary_forecast import _generate_binary_forecasts_for_symbol

SYMBOLS = ["AAPL", "MSFT", "SPY", "PG", "NVDA"]
HORIZONS = [1, 5, 10]


def main() -> None:
    print("Generating binary forecasts for ml_forecasts (model_type=binary)...")
    total = 0
    for symbol in SYMBOLS:
        try:
            results = _generate_binary_forecasts_for_symbol(symbol, HORIZONS)
            for r in results:
                print(f"  {symbol} {r.horizon_days}D: {r.label} (conf={r.confidence:.2f})")
            total += len(results)
        except Exception as e:
            print(f"  ! {symbol}: {e}")
    print(f"\nDone. Wrote {total} forecasts to ml_forecasts (model_type=binary).")


if __name__ == "__main__":
    main()
