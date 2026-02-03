#!/usr/bin/env python3
"""Test Kaggle vs Supabase on SAME time period (date ranges and overlap)."""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    print("Loading Kaggle TSLA (full range)...")
    try:
        from src.data.kaggle_stock_data import get_kaggle_path, load_symbol_ohlcv
        kaggle_path = get_kaggle_path()
        df_kaggle = load_symbol_ohlcv("TSLA", path=kaggle_path, limit=None)
    except Exception as e:
        print(f"Kaggle load failed: {e}")
        import traceback
        traceback.print_exc()
        return

    if df_kaggle is None or df_kaggle.empty:
        print("No Kaggle data")
        return

    df_kaggle["ts"] = pd.to_datetime(df_kaggle["ts"])
    df_kaggle = df_kaggle.sort_values("ts")

    print("Loading Supabase TSLA...")
    try:
        from src.data.supabase_db import SupabaseDatabase
        from src.data.data_cleaner import DataCleaner
        db = SupabaseDatabase()
        df_supa = db.fetch_ohlc_bars("TSLA", timeframe="d1", limit=2000)
        df_supa = DataCleaner.clean_all(df_supa, verbose=False)
    except Exception as e:
        print(f"Supabase load failed: {e}")
        import traceback
        traceback.print_exc()
        return

    df_supa["ts"] = pd.to_datetime(df_supa["ts"])
    df_supa = df_supa.sort_values("ts")

    print(f"\nKaggle date range:   {df_kaggle['ts'].min()} → {df_kaggle['ts'].max()} ({len(df_kaggle)} rows)")
    print(f"Supabase date range: {df_supa['ts'].min()} → {df_supa['ts'].max()} ({len(df_supa)} rows)")

    kaggle_start = df_kaggle["ts"].min()
    kaggle_end = df_kaggle["ts"].max()
    supa_start = df_supa["ts"].min()
    supa_end = df_supa["ts"].max()

    overlap_start = max(kaggle_start, supa_start)
    overlap_end = min(kaggle_end, supa_end)

    print(f"\nOverlapping period:  {overlap_start} → {overlap_end}")

    df_kaggle_overlap = df_kaggle[(df_kaggle["ts"] >= overlap_start) & (df_kaggle["ts"] <= overlap_end)]
    df_supa_overlap = df_supa[(df_supa["ts"] >= overlap_start) & (df_supa["ts"] <= overlap_end)]

    print(f"Kaggle rows in overlap:   {len(df_kaggle_overlap)}")
    print(f"Supabase rows in overlap: {len(df_supa_overlap)}")

    if len(df_kaggle_overlap) < 300 or len(df_supa_overlap) < 300:
        print("\n⚠️ NO SIGNIFICANT OVERLAP! Sources cover different time periods.")
        print("This explains the performance difference - you're testing on different market regimes.")
    else:
        print("\n✅ Sufficient overlap. Can run comparison on same period.")


if __name__ == "__main__":
    main()
