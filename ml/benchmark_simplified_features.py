#!/usr/bin/env python3
"""
Benchmark simplified (28-feature) pipeline on real data for multiple symbols.
Reports training accuracy, validation accuracy, training time per symbol.
Saves one model per symbol to trained_models/ for analyze_feature_importance.py.

Runs sentiment backfill (7 days) automatically before benchmarking unless
--skip-sentiment-backfill is passed.
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.models.baseline_forecaster import BaselineForecaster

BENCHMARK_SYMBOLS = [
    "AAPL",
    "AMD",
    "CRWD",
    "GOOG",
    "GOOGL",
    "HL",
    "META",
    "MSFT",
    "MU",
    "NVDA",
    "SPY",
    "TSLA",
]

LIMIT_BARS = 600
TRAIN_VAL_SPLIT = 0.8
MIN_SAMPLES_TRAIN = 50


def load_ohlcv(symbol: str, limit: int = LIMIT_BARS) -> pd.DataFrame | None:
    """Load OHLCV from Supabase for symbol."""
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=limit)
        if df is not None and len(df) >= 250:
            return df
    except Exception as e:
        print(f"  [{symbol}] DB error: {e}")
    return None


def load_sentiment_for_symbol(symbol: str, start_date=None, end_date=None):
    """
    Load daily sentiment for symbol over [start_date, end_date].
    Returns None (disabled) until sentiment pipeline has verified variance (std > 0.01).
    When re-enabled, use get_historical_sentiment_series and validate_sentiment_variance first.
    """
    # DISABLED: Sentiment had zero variance (constant -0.186633). Re-enable after fixing
    # FinViz integration and running validate_sentiment_variance(symbol).
    return None


def run_one_symbol(
    symbol: str,
    forecaster: BaselineForecaster,
    horizon_days: int = 1,
) -> dict | None:
    """Train/val on one symbol; return metrics dict or None if insufficient data."""
    df = load_ohlcv(symbol, limit=LIMIT_BARS)
    if df is None:
        return None

    start_date = pd.to_datetime(df["ts"]).min().date()
    end_date = pd.to_datetime(df["ts"]).max().date()
    sentiment_series = load_sentiment_for_symbol(symbol, start_date=start_date, end_date=end_date)
    X, y = forecaster.prepare_training_data(
        df, horizon_days=horizon_days, sentiment_series=sentiment_series
    )
    if len(X) < 100 or len(y) < 100:
        return None

    split_idx = int(len(X) * TRAIN_VAL_SPLIT)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    t0 = time.perf_counter()
    forecaster.train(X_train, y_train, min_samples=MIN_SAMPLES_TRAIN)
    train_time_sec = time.perf_counter() - t0

    train_acc = forecaster.training_stats.get("accuracy", 0.0)
    numeric_cols = [c for c in forecaster.feature_columns if c in X_val.columns]
    X_val_num = X_val[numeric_cols]
    X_val_scaled = forecaster.scaler.transform(X_val_num)
    y_val_pred = forecaster.model.predict(X_val_scaled)
    val_acc = accuracy_score(y_val, y_val_pred)

    return {
        "symbol": symbol,
        "bars": len(df),
        "n_samples": len(X),
        "n_train": len(X_train),
        "n_val": len(X_val),
        "train_accuracy": train_acc,
        "val_accuracy": val_acc,
        "train_time_sec": train_time_sec,
        "forecaster": forecaster,
        "feature_columns": forecaster.feature_columns,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark simplified feature pipeline")
    parser.add_argument(
        "--skip-sentiment-backfill",
        action="store_true",
        help="Skip automatic sentiment backfill before benchmarking",
    )
    args = parser.parse_args()

    # Pre-run: sentiment backfill (7 days) for benchmark symbols
    if not args.skip_sentiment_backfill:
        try:
            from backfill_sentiment import run_sentiment_backfill

            print("Running sentiment backfill (7 days) before benchmark...")
            written, err = run_sentiment_backfill(
                symbols=BENCHMARK_SYMBOLS,
                days=7,
                delay=0.5,
                quiet=True,
            )
            if err:
                print(f"  Sentiment backfill skipped: {err}")
            else:
                print(f"  Sentiment backfill done: {written} rows written\n")
        except Exception as e:
            print(f"  Sentiment backfill skipped: {e}\n")

    print("Benchmarking simplified 28-feature pipeline on real data (sentiment disabled)")
    print(f"Symbols: {', '.join(BENCHMARK_SYMBOLS)}")
    print(f"Bars per symbol: {LIMIT_BARS}, train/val split: {TRAIN_VAL_SPLIT:.0%}\n")

    results: list[dict] = []
    trained_models_dir = Path(__file__).resolve().parent / "trained_models"
    trained_models_dir.mkdir(exist_ok=True)

    for symbol in BENCHMARK_SYMBOLS:
        forecaster = BaselineForecaster()
        out = run_one_symbol(symbol, forecaster, horizon_days=1)
        if out is None:
            print(f"  {symbol}: skip (no data or insufficient samples)")
            continue

        results.append(out)
        # Save artifact for analyze_feature_importance.py
        artifact = {
            "symbol": symbol,
            "timeframe": "d1",
            "models": {"baseline": forecaster.model},
            "feature_names": out["feature_columns"],
            "weights": {"baseline": 1.0},
            "performances": {
                "baseline": {
                    "train_accuracy": out["train_accuracy"],
                    "val_accuracy": out["val_accuracy"],
                    "train_time_sec": out["train_time_sec"],
                },
            },
            "n_features": len(out["feature_columns"]),
        }
        out_path = trained_models_dir / f"{symbol}_simplified_28feat.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(artifact, f)
        print(
            f"  {symbol}: bars={out['bars']}, samples={out['n_samples']}, "
            f"train_acc={out['train_accuracy']:.1%}, val_acc={out['val_accuracy']:.1%}, "
            f"time={out['train_time_sec']:.2f}s"
        )

    if not results:
        print("No symbols had sufficient real data. Check Supabase and symbol list.")
        sys.exit(1)

    # Summary table
    print("\n" + "=" * 90)
    print("BENCHMARK RESULTS (28 features, sentiment disabled)")
    print("=" * 90)
    print(f"{'Symbol':<8} {'Bars':>6} {'Samples':>8} {'Train%':>8} {'Val%':>8} {'Time(s)':>8}")
    print("-" * 90)
    for r in results:
        print(
            f"{r['symbol']:<8} {r['bars']:>6} {r['n_samples']:>8} "
            f"{r['train_accuracy']:>7.1%} {r['val_accuracy']:>7.1%} {r['train_time_sec']:>8.2f}"
        )
    print("-" * 90)
    n = len(results)
    avg_train = sum(r["train_accuracy"] for r in results) / n
    avg_val = sum(r["val_accuracy"] for r in results) / n
    avg_time = sum(r["train_time_sec"] for r in results) / n
    med_val = sorted(r["val_accuracy"] for r in results)[n // 2]
    print(f"{'MEAN':<8} {'':>6} {'':>8} {avg_train:>7.1%} {avg_val:>7.1%} {avg_time:>8.2f}")
    print(f"{'MED(val)':<8} {'':>6} {'':>8} {'':>8} {med_val:>7.1%}")
    print("=" * 90)
    print(f"Models saved to {trained_models_dir} (*_simplified_28feat.pkl)")
    print("Run: python ml/analyze_feature_importance.py")


if __name__ == "__main__":
    main()
