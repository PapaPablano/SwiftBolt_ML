#!/usr/bin/env python3
"""Compare NVDA OHLCV from Kaggle vs Supabase: cleanliness and information."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

SYMBOL = "NVDA"
LIMIT = 600


def main():
    print("=" * 60)
    print(f"NVDA DATA COMPARISON: Kaggle vs Supabase (limit={LIMIT})")
    print("=" * 60)

    # --- Load Kaggle ---
    print("\nLoading Kaggle data...")
    try:
        from src.data.kaggle_stock_data import get_kaggle_path, load_symbol_ohlcv
        kaggle_path = get_kaggle_path()
        df_kaggle = load_symbol_ohlcv(SYMBOL, path=kaggle_path, limit=LIMIT)
    except Exception as e:
        print(f"Kaggle load failed: {e}")
        import traceback
        traceback.print_exc()
        df_kaggle = None

    # --- Load Supabase ---
    print("Loading Supabase data...")
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        df_supabase = db.fetch_ohlc_bars(SYMBOL, timeframe="d1", limit=LIMIT)
    except Exception as e:
        print(f"Supabase load failed: {e}")
        import traceback
        traceback.print_exc()
        df_supabase = None

    # --- Information summary ---
    print("\n" + "=" * 60)
    print("INFORMATION (rows, date range, nulls)")
    print("=" * 60)

    for name, df in [("Kaggle", df_kaggle), ("Supabase", df_supabase)]:
        print(f"\n--- {name} ---")
        if df is None or df.empty:
            print("  No data")
            continue
        print(f"  Rows:        {len(df)}")
        print(f"  Date range:  {df['ts'].min()}  ->  {df['ts'].max()}")
        nulls = df.isnull().sum()
        if nulls.any():
            print("  Nulls:")
            for col in nulls[nulls > 0].index:
                print(f"    {col}: {nulls[col]}")
        else:
            print("  Nulls:       none")
        if "volume" in df.columns:
            print(f"  Volume min:  {df['volume'].min():,.0f}")
            print(f"  Volume max:  {df['volume'].max():,.0f}")
        if "close" in df.columns:
            print(f"  Close range: {df['close'].min():.2f} -> {df['close'].max():.2f}")

    # --- Cleanliness: run validator (no fix, report only) ---
    print("\n" + "=" * 60)
    print("CLEANLINESS (OHLCValidator: relationships, volume, gaps, outliers)")
    print("=" * 60)

    from src.data.data_validator import validate_ohlc_data

    for name, df in [("Kaggle", df_kaggle), ("Supabase", df_supabase)]:
        print(f"\n--- {name} ---")
        if df is None or df.empty:
            print("  No data to validate")
            continue
        df_clean, result = validate_ohlc_data(df.copy(), fix_issues=False)
        print(f"  Valid:         {result.is_valid}")
        print(f"  Rows flagged:  {result.rows_flagged}")
        if result.issues:
            for issue in result.issues:
                print(f"  Issue:         {issue}")
        # With fix
        df_fixed, res2 = validate_ohlc_data(df.copy(), fix_issues=True)
        print(f"  After fix:     {res2.rows_removed} rows removed, {len(df_fixed)} remaining")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
