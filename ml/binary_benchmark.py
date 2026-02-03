#!/usr/bin/env python3
"""
Benchmark binary classification (bullish vs bearish only).

Filters out small moves (|return| < threshold), focuses on clear directional days.
Random baseline = 50%. Target: 55%+ accuracy.

Usage:
  cd ml && python binary_benchmark.py                    # TSLA, RF
  python binary_benchmark.py --symbol NVDA              # NVDA
  python binary_benchmark.py --threshold 0.008          # ±0.8% threshold
  python binary_benchmark.py --no-tabpfn                # RF (default)
  python binary_benchmark.py                             # TabPFN (omit --no-tabpfn for TabPFN)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report

sys.path.insert(0, str(Path(__file__).resolve().parent))

LIMIT_BARS = 600
TRAIN_VAL_SPLIT = 0.8
MIN_SAMPLES_TRAIN = 30
DEFAULT_THRESHOLD_PCT = 0.005


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


def load_sentiment(symbol: str, start_date, end_date) -> pd.Series | None:
    """Load daily sentiment for symbol over [start_date, end_date]."""
    if start_date is None or end_date is None:
        return None
    try:
        from src.features.stock_sentiment import get_historical_sentiment_series

        return get_historical_sentiment_series(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception as e:
        print(f"  Sentiment error for {symbol}: {e}")
        return None


def predict_batch_binary(forecaster, X: pd.DataFrame, use_tabpfn: bool) -> np.ndarray:
    """Get binary (bullish/bearish) predictions. Works for XGBoost baseline and TabPFN."""
    cols = [c for c in forecaster.feature_columns if c in X.columns]
    X_num = X[cols]
    X_scaled = forecaster.scaler.transform(X_num)

    if use_tabpfn:
        # TabPFN predicts return; convert to binary by sign
        pred_returns = forecaster.model.predict(X_scaled)
        if np.isscalar(pred_returns):
            pred_returns = np.array([pred_returns])
        return np.where(np.atleast_1d(pred_returns) > 0, "bullish", "bearish")
    # Baseline (XGBoost): predicts 0/1/...; decode using forecaster._label_decode (set at train)
    pred_encoded = forecaster.model.predict(X_scaled)
    pred_encoded = np.atleast_1d(pred_encoded)
    decode = getattr(forecaster, "_label_decode", None)
    if not decode:
        from src.models.baseline_forecaster import LABEL_DECODE
        decode = LABEL_DECODE
    return np.array([decode.get(int(p), "neutral") for p in pred_encoded])


def run_binary_benchmark(
    symbol: str = "TSLA",
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    use_tabpfn: bool = False,
    add_regime: bool = False,
) -> float:
    """Run binary train/val benchmark; return validation accuracy."""
    if use_tabpfn:
        from src.models.tabpfn_forecaster import TabPFNForecaster

        forecaster = TabPFNForecaster()
    else:
        from src.models.baseline_forecaster import BaselineForecaster

        forecaster = BaselineForecaster()

    df = load_ohlcv(symbol, limit=LIMIT_BARS)
    if df is None:
        raise ValueError(f"Insufficient OHLCV for {symbol}")

    start_date = pd.to_datetime(df["ts"]).min().date()
    end_date = pd.to_datetime(df["ts"]).max().date()
    sentiment = load_sentiment(symbol, start_date, end_date)

    out = forecaster.prepare_training_data_binary(
        df,
        horizon_days=1,
        sentiment_series=sentiment,
        threshold_pct=threshold_pct,
        add_simple_regime=add_regime,
    )
    X, y = out[0], out[1]
    if len(X) < 50:
        raise ValueError(
            f"Too few binary samples for {symbol}: {len(X)} (need >= 50). "
            f"Try lower threshold_pct (e.g. 0.003)."
        )

    split_idx = int(len(X) * TRAIN_VAL_SPLIT)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    forecaster.train(X_train, y_train, min_samples=MIN_SAMPLES_TRAIN)
    y_pred = predict_batch_binary(forecaster, X_val, use_tabpfn=use_tabpfn)

    # TabPFN binary mode: y_val is continuous returns; convert to labels for metrics
    if use_tabpfn and hasattr(y_val, "values") and np.issubdtype(y_val.dtype, np.floating):
        y_val_labels = np.where(np.asarray(y_val) > 0, "bullish", "bearish")
    else:
        y_val_labels = np.asarray(y_val)

    acc = accuracy_score(y_val_labels, y_pred)
    baseline = 0.50
    lift_pct = (acc - baseline) / baseline * 100 if baseline else 0

    print("\n" + "=" * 60)
    print(f"BINARY CLASSIFICATION: {symbol}")
    print("=" * 60)
    print(f"Model: {'TabPFN' if use_tabpfn else 'XGBoost'}")
    print(f"Threshold: |return| > {threshold_pct:.2%} (filter small moves)")
    print(f"Train samples: {len(X_train)}")
    print(f"Val samples: {len(X_val)}")
    print(f"\nValidation Accuracy: {acc:.1%}")
    print(f"Random baseline: 50.0%")
    print(f"Lift: {lift_pct:+.1f}%")
    print(f"\n{classification_report(y_val_labels, y_pred)}")
    print("=" * 60 + "\n")

    return acc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark binary (bullish vs bearish) classification"
    )
    parser.add_argument(
        "--symbol",
        default="TSLA",
        help="Symbol to benchmark (default: TSLA)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_PCT,
        help=f"Min |return| to keep (default: {DEFAULT_THRESHOLD_PCT})",
    )
    parser.add_argument(
        "--no-tabpfn",
        action="store_true",
        help="Use Random Forest (default). Omit for TabPFN.",
    )
    parser.add_argument(
        "--with-regime",
        action="store_true",
        help="Add regime features (SPY, VIX, sector) for market context",
    )
    args = parser.parse_args()

    acc = run_binary_benchmark(
        symbol=args.symbol,
        threshold_pct=args.threshold,
        use_tabpfn=not args.no_tabpfn,
        add_regime=args.with_regime,
    )
    if acc >= 0.55:
        print("Result: 55%+ accuracy — binary setup looks good for walk-forward.")
    else:
        print("Result: Below 55%. Try lower --threshold or different symbol.")
    sys.exit(0 if acc >= 0.50 else 1)


if __name__ == "__main__":
    main()
