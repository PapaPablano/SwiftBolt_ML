#!/usr/bin/env python3
"""Compare feature sets between Kaggle (no sentiment) and Supabase (with sentiment)."""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    print("Loading Kaggle TSLA (last 600 bars, no sentiment)...")
    try:
        from src.data.kaggle_stock_data import get_kaggle_path, load_symbol_ohlcv
        kaggle_path = get_kaggle_path()
        df_k = load_symbol_ohlcv("TSLA", path=kaggle_path, limit=600)
    except Exception as e:
        print(f"Kaggle load failed: {e}")
        import traceback
        traceback.print_exc()
        return

    if df_k is None or len(df_k) < 100:
        print("Insufficient Kaggle data")
        return

    print("Loading Supabase TSLA (last 600 bars, with sentiment)...")
    try:
        from src.data.supabase_db import SupabaseDatabase
        from src.data.data_cleaner import DataCleaner
        db = SupabaseDatabase()
        df_s = db.fetch_ohlc_bars("TSLA", timeframe="d1", limit=600)
        df_s = DataCleaner.clean_all(df_s, verbose=False)
    except Exception as e:
        print(f"Supabase load failed: {e}")
        import traceback
        traceback.print_exc()
        return

    try:
        from src.features.stock_sentiment import get_historical_sentiment_series
        start_date = pd.to_datetime(df_s["ts"]).min().date()
        end_date = pd.to_datetime(df_s["ts"]).max().date()
        sentiment = get_historical_sentiment_series(
            symbol="TSLA",
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception:
        sentiment = None

    # Use XGBoost forecaster (same feature pipeline as walk_forward: baseline + sentiment)
    from src.models.xgboost_forecaster import XGBoostForecaster

    forecaster = XGBoostForecaster()

    print("\nPreparing Kaggle features (sentiment=None)...")
    out_k = forecaster.prepare_training_data_binary(
        df_k,
        horizon_days=5,
        threshold_pct=0.02,
        sentiment_series=None,
        add_simple_regime=True,
    )
    X_k, y_k, dates_k = out_k[0], out_k[1], out_k[2] if len(out_k) > 2 else None

    print("Preparing Supabase features (with sentiment)...")
    out_s = forecaster.prepare_training_data_binary(
        df_s,
        horizon_days=5,
        threshold_pct=0.02,
        sentiment_series=sentiment,
        add_simple_regime=True,
    )
    X_s, y_s, dates_s = out_s[0], out_s[1], out_s[2] if len(out_s) > 2 else None

    print(f"\nKaggle:   {len(X_k)} rows, {len(X_k.columns)} columns")
    print(f"Supabase: {len(X_s)} rows, {len(X_s.columns)} columns")

    print("\n" + "=" * 60)
    print("FEATURE COMPARISON")
    print("=" * 60)

    common = set(X_k.columns) & set(X_s.columns)
    kaggle_only = set(X_k.columns) - set(X_s.columns)
    supabase_only = set(X_s.columns) - set(X_k.columns)

    print(f"\nCommon features: {len(common)}")
    for col in sorted(common):
        print(f"  - {col}")

    if kaggle_only:
        print(f"\nKaggle-only features: {len(kaggle_only)}")
        for col in sorted(kaggle_only):
            print(f"  - {col}")

    if supabase_only:
        print(f"\nSupabase-only features: {len(supabase_only)} (likely sentiment-related)")
        for col in sorted(supabase_only):
            print(f"  - {col}")

    print("=" * 60)


if __name__ == "__main__":
    main()
