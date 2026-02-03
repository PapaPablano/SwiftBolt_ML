#!/usr/bin/env python3
"""
Compare ARIMA-GARCH vs XGBoost vs TabPFN on binary stock prediction.

Usage:
  cd ml && python compare_models.py --symbol TSLA --threshold 0.005
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))

LIMIT_BARS = 600
TRAIN_VAL_SPLIT = 0.8


def load_ohlcv(symbol: str, limit: int = LIMIT_BARS) -> pd.DataFrame | None:
    """Load OHLCV from Supabase."""
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=limit)
        if df is not None and len(df) >= 250:
            return df
    except Exception as e:
        print(f"  [{symbol}] DB error: {e}")
    return None


def load_sentiment(symbol: str, start_ts, end_ts) -> pd.Series | None:
    """Load daily sentiment for symbol."""
    if start_ts is None or end_ts is None:
        return None
    try:
        from src.features.stock_sentiment import get_historical_sentiment_series
        start_date = pd.to_datetime(start_ts).date()
        end_date = pd.to_datetime(end_ts).date()
        return get_historical_sentiment_series(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception as e:
        print(f"  Sentiment error: {e}")
        return None


def test_model(
    model_class,
    model_name: str,
    df: pd.DataFrame,
    sentiment: pd.Series | None,
    threshold_pct: float,
    use_features: bool,
    horizon_days: int = 1,
) -> float:
    """Test a single model; return validation accuracy."""
    print(f"\n{'='*60}")
    print(f"Testing {model_name}")
    print("="*60)

    forecaster = model_class()
    out = forecaster.prepare_training_data_binary(
        df,
        horizon_days=horizon_days,
        sentiment_series=sentiment,
        threshold_pct=threshold_pct,
        add_simple_regime=use_features,
    )
    X, y, dates = out[0], out[1], out[2]

    if len(X) < 50:
        print(f"  Too few samples: {len(X)}. Skipping.")
        return 0.0

    # Time-based split: train on past 80%, validate on last 20% (no future leakage)
    n = len(X)
    split_idx = int(n * TRAIN_VAL_SPLIT)
    X_train = X.iloc[:split_idx] if hasattr(X, "iloc") else X[:split_idx]
    X_val = X.iloc[split_idx:] if hasattr(X, "iloc") else X[split_idx:]
    y_train = y.iloc[:split_idx] if hasattr(y, "iloc") else y[:split_idx]
    y_val = y.iloc[split_idx:] if hasattr(y, "iloc") else y[split_idx:]

    print(f"Train samples: {len(X_train)}")
    print(f"Val samples: {len(X_val)}")

    forecaster.train(X_train, y_train, min_samples=30)
    y_pred = forecaster.predict_batch(X_val)

    # Ensure same types for accuracy_score
    y_val_labels = np.asarray(y_val).ravel()
    y_pred = np.asarray(y_pred).ravel()
    acc = accuracy_score(y_val_labels, y_pred)
    lift = (acc - 0.5) / 0.5 * 100 if 0.5 else 0

    print(f"\nValidation Accuracy: {acc:.1%}")
    print(f"Random baseline: 50.0%")
    print(f"Lift: {lift:+.1f}%")
    print(f"\n{classification_report(y_val_labels, y_pred)}")
    return float(acc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ARIMA-GARCH vs XGBoost vs TabPFN on binary prediction"
    )
    parser.add_argument("--symbol", default="TSLA", help="Symbol to test")
    parser.add_argument("--horizon", type=int, default=1, help="Prediction horizon in days (default: 1)")
    parser.add_argument("--threshold", type=float, default=0.008, help="Min |return| for binary (0.8%%)")
    parser.add_argument("--no-arima", action="store_true", help="Skip ARIMA-GARCH")
    parser.add_argument("--no-xgboost", action="store_true", help="Skip XGBoost")
    parser.add_argument("--optimized", action="store_true", help="Use XGBoost with top-30 feature selection")
    parser.add_argument("--no-tabpfn", action="store_true", help="Skip TabPFN")
    args = parser.parse_args()

    print(f"Loading {args.symbol} (horizon={args.horizon}d, threshold={args.threshold:.2%})...")
    df = load_ohlcv(args.symbol, limit=LIMIT_BARS)
    if df is None:
        print("Failed to load OHLCV.")
        sys.exit(1)

    start_ts = pd.to_datetime(df["ts"]).min()
    end_ts = pd.to_datetime(df["ts"]).max()
    sentiment = load_sentiment(args.symbol, start_ts, end_ts)

    results: dict[str, float] = {}

    if not args.no_arima:
        try:
            from src.models.arima_garch_forecaster import ARIMAGARCHForecaster
            results["ARIMA-GARCH"] = test_model(
                ARIMAGARCHForecaster,
                "ARIMA-GARCH",
                df,
                sentiment,
                args.threshold,
                use_features=True,
                horizon_days=args.horizon,
            )
        except Exception as e:
            print(f"ARIMA-GARCH failed: {e}")
            results["ARIMA-GARCH"] = 0.0

    if not args.no_xgboost:
        try:
            if args.optimized:
                from src.models.xgboost_forecaster_optimized import XGBoostForecasterOptimized
                results["XGBoost (optimized)"] = test_model(
                    XGBoostForecasterOptimized,
                    "XGBoost (top-30 features)",
                    df,
                    sentiment,
                    args.threshold,
                    use_features=True,
                    horizon_days=args.horizon,
                )
            else:
                from src.models.xgboost_forecaster import XGBoostForecaster
                results["XGBoost"] = test_model(
                    XGBoostForecaster,
                    "XGBoost (with features)",
                    df,
                    sentiment,
                    args.threshold,
                    use_features=True,
                    horizon_days=args.horizon,
                )
        except Exception as e:
            print(f"XGBoost failed: {e}")
            results["XGBoost" if not args.optimized else "XGBoost (optimized)"] = 0.0

    if not args.no_tabpfn:
        try:
            from src.models.tabpfn_forecaster import TabPFNForecaster
            results["TabPFN"] = test_model(
                TabPFNForecaster,
                "TabPFN",
                df,
                sentiment,
                args.threshold,
                use_features=True,
                horizon_days=args.horizon,
            )
        except Exception as e:
            print(f"TabPFN failed: {e}")
            results["TabPFN"] = 0.0

    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print("="*60)
    for model, acc in sorted(results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model:20s}: {acc:.1%}")
    print("="*60)

    if results:
        best_model = max(results.items(), key=lambda x: x[1])
        print(f"\nBest model: {best_model[0]} ({best_model[1]:.1%})")
        if best_model[1] >= 0.55:
            print("  Production ready (>55% accuracy)")
        else:
            print("  Below 55% threshold")
    sys.exit(0)


if __name__ == "__main__":
    main()
