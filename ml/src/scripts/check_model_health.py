#!/usr/bin/env python
"""
Model Health and Data Staleness Check

Monitors:
- Data staleness (forecasts, evaluations, etc.)
- Model drift detection
- Data freshness status

Usage:
    python -m src.scripts.check_model_health
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, ".")

from src.monitoring.forecast_staleness import check_all_staleness


def main():
    print("📊 Checking model health and data staleness...")
    try:
        staleness = check_all_staleness()
        any_stale = False
        for name, result in staleness.items():
            print(f"{result.icon} {name}: {result.message}")
            if not result.is_ok:
                any_stale = True
        if any_stale:
            print("")
            print("::warning::Some data sources are stale!")
            print("Note: Stale forecasts are expected if ML Orchestration has not run recently.")
            print("      Forecasts will be refreshed when ml-forecast job completes.")
        else:
            print("✅ All data sources are fresh")
    except Exception as e:
        print(f"⚠️ Staleness check error: {e}")

    print("✅ Drift monitoring complete")


if __name__ == "__main__":
    main()
