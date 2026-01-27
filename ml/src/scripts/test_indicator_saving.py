#!/usr/bin/env python
"""
Test indicator snapshot saving to identify failures.

This replicates the indicator saving logic from intraday_forecast_job
with detailed error reporting.
"""

import os
import sys
import json
from argparse import ArgumentParser

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features


def test_indicator_saving(symbol: str, timeframe: str = "h1"):
    """Test indicator snapshot saving for a symbol."""
    print(f"\n{'='*70}")
    print(f"TESTING INDICATOR SAVE: {symbol} / {timeframe}")
    print(f"{'='*70}")

    # Get symbol ID
    symbol_id = db.get_symbol_id(symbol)
    if not symbol_id:
        print(f"❌ Symbol not found: {symbol}")
        return False

    print(f"✅ Symbol ID: {symbol_id}")

    # Fetch OHLC data
    print(f"\n1️⃣  Fetching OHLC bars ({timeframe})...")
    df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=100)

    if df.empty:
        print(f"❌ No OHLC data found")
        return False

    print(f"✅ Fetched {len(df)} bars")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Last bar: {df.iloc[-1].to_dict()}")

    # Add technical indicators
    print(f"\n2️⃣  Adding technical indicators...")
    try:
        df = add_technical_features(df)
        print(f"✅ Indicators added")
        print(f"   Indicator columns: {[c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume', 'ts']]}")
    except Exception as e:
        print(f"❌ Failed to add indicators: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Prepare indicator records (same as intraday_forecast_job.py lines 517-585)
    print(f"\n3️⃣  Preparing indicator records...")
    try:
        snapshot_bars = min(len(df), 20)
        indicator_records = []

        for idx in range(-snapshot_bars, 0):
            row = df.iloc[idx]
            record = {
                "ts": row.get("ts") if "ts" in df.columns else row.name,
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                # Momentum indicators
                "rsi_14": row.get("rsi_14"),
                "macd": row.get("macd"),
                "macd_signal": row.get("macd_signal"),
                "macd_hist": row.get("macd_hist"),
                # ADX
                "adx": row.get("adx"),
                "atr_14": row.get("atr_14"),
                # Volatility bands
                "bb_upper": row.get("bb_upper"),
                "bb_lower": row.get("bb_lower"),
                # Additional momentum/trend
                "stoch_k": row.get("stoch_k"),
                "stoch_d": row.get("stoch_d"),
                "williams_r": row.get("williams_r"),
                "cci": row.get("cci"),
                "mfi": row.get("mfi") or row.get("mfi_14"),
                "obv": row.get("obv"),
            }
            indicator_records.append(record)

        print(f"✅ Created {len(indicator_records)} indicator records")
        print(f"   Sample record (last bar):")
        last_rec = indicator_records[-1]
        print(f"   ts: {last_rec.get('ts')}")
        print(f"   close: {last_rec.get('close')}")
        print(f"   rsi_14: {last_rec.get('rsi_14')}")
        print(f"   macd: {last_rec.get('macd')}")
    except Exception as e:
        print(f"❌ Failed to prepare records: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Try to save indicators
    print(f"\n4️⃣  Saving indicator snapshot to database...")
    try:
        db.save_indicator_snapshot(
            symbol_id=symbol_id,
            timeframe=timeframe,
            indicators=indicator_records,
        )
        print(f"✅ Successfully saved indicator snapshot!")

        # Verify it was saved
        print(f"\n5️⃣  Verifying saved data...")
        query = db.client.table("indicator_values").select(
            "symbol_id,timeframe,created_at,rsi_14,macd"
        ).eq("symbol_id", symbol_id).eq("timeframe", timeframe).order(
            "created_at", desc=True
        ).limit(1).execute()

        if query.data:
            saved = query.data[0]
            print(f"✅ Found saved record:")
            print(f"   Symbol ID: {saved.get('symbol_id')}")
            print(f"   Timeframe: {saved.get('timeframe')}")
            print(f"   Created at: {saved.get('created_at')}")
            print(f"   RSI: {saved.get('rsi_14')}")
            print(f"   MACD: {saved.get('macd')}")
            return True
        else:
            print(f"❌ Could not find saved record (possible timing issue)")
            return False

    except Exception as e:
        print(f"❌ Failed to save indicators: {e}")
        import traceback
        traceback.print_exc()

        # Try to provide more details
        print(f"\n   Debugging info:")
        print(f"   - Database connected: {db.client is not None}")
        print(f"   - First indicator record keys: {list(indicator_records[0].keys())}")
        print(f"   - Sample values: ts={indicator_records[0]['ts']}, close={indicator_records[0]['close']}")

        return False


def main():
    parser = ArgumentParser(description="Test indicator snapshot saving")
    parser.add_argument("--symbol", type=str, default="AMD", help="Symbol to test")
    parser.add_argument("--timeframe", type=str, default="h1", help="Timeframe (m15, h1, h4, d1)")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("INDICATOR SNAPSHOT SAVING TEST")
    print("="*70)

    success = test_indicator_saving(args.symbol, args.timeframe)

    print(f"\n{'='*70}")
    if success:
        print("✅ TEST PASSED - Indicators saving correctly!")
    else:
        print("❌ TEST FAILED - Indicators not saving!")
        print("\nCheck the error messages above for the root cause.")
        print("\nCommon issues:")
        print("1. Column name mismatch (check indicator_values schema)")
        print("2. Type conversion (e.g., JSON vs JSONB)")
        print("3. Required fields missing")
        print("4. Database permissions")
    print("="*70)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
