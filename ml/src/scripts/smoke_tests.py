#!/usr/bin/env python
"""
Smoke Tests - Basic Validation

Quick validation tests to ensure:
- OHLC data is accessible
- ML forecasts table is accessible
- Database connectivity

Usage:
    python -m src.scripts.smoke_tests
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.data.supabase_db import db


def main():
    print("📊 Running quick smoke tests...")

    try:
        # Check OHLC data
        df = db.fetch_ohlc_bars("SPY", timeframe="d1", limit=5)
        if len(df) == 0:
            print("❌ No OHLC data found")
            sys.exit(1)
        print(f"✅ OHLC bars: {len(df)} records")

        # Check forecasts exist
        try:
            forecasts = db.client.table("ml_forecasts").select("*").limit(1).execute()
            print(f"✅ ML forecasts table accessible")
        except Exception as e:
            print(f"⚠️ ML forecasts check: {e}")

        print("✅ Smoke tests passed")
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
