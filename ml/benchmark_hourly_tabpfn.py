#!/usr/bin/env python3
"""
Benchmark TabPFN on 4-hour (h4) data for multiple symbols.

Timeframe: h4 = each OHLC bar = 4 market hours.
~2 bars per trading day. Fetches expand until target samples are reached.

Horizon: 2 bars (≈1 trading day, 8 market hours).
Label: Percentile thresholds (balanced 30/30/30).

Run: cd ml && python benchmark_hourly_tabpfn.py
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.features.adaptive_thresholds import AdaptiveThresholds
from src.features.temporal_indicators import (
    SIMPLIFIED_FEATURES,
    TemporalFeatureEngineer,
    compute_simplified_features,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

BENCHMARK_SYMBOLS = ["TSLA", "NVDA", "AAPL", "SPY", "META", "AMD"]
TIMEFRAME = "h4"  # 4-hour bars
TARGET_SAMPLES = 1000  # Expand fetch until we have this many usable samples
HORIZON_BARS = 2  # 2 × 4h = 8 market hours ≈ 1 trading day
TRAIN_VAL_SPLIT = 0.8
MIN_SAMPLES_TRAIN = 100
START_IDX = 200  # sma_200 + lags
MAX_LIMIT_BARS = 5000  # Cap to avoid runaway fetch


def load_ohlcv_until_enough(
    symbol: str,
    target_samples: int = TARGET_SAMPLES,
    horizon_bars: int = HORIZON_BARS,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.Series | None, pd.Series | None, float, float]:
    """
    Fetch h4 OHLCV and prepare data, expanding limit until we have enough samples.

    Returns:
        (df, X, y_labels, y_returns, bear_thresh, bull_thresh) or (None, None, None, None, 0, 0)
    """
    min_bars = target_samples + START_IDX + horizon_bars
    limit = min_bars
    step = 500
    last_df, last_X, last_y_labels, last_y_returns = None, None, None, None
    last_bear, last_bull = 0.0, 0.0

    try:
        from src.data.supabase_db import SupabaseDatabase

        db = SupabaseDatabase()

        while limit <= MAX_LIMIT_BARS:
            df = db.fetch_ohlc_bars(symbol, timeframe=TIMEFRAME, limit=limit)
            if df is None or len(df) < 250:
                return None, None, None, None, 0.0, 0.0

            X, y_labels, y_returns, bear_thresh, bull_thresh = prepare_training_data(
                df, horizon_bars=horizon_bars
            )
            last_df, last_X, last_y_labels, last_y_returns = df, X, y_labels, y_returns
            last_bear, last_bull = bear_thresh, bull_thresh

            if len(X) >= target_samples:
                return df, X, y_labels, y_returns, bear_thresh, bull_thresh

            if len(df) < limit:
                break
            limit += step

        if last_X is not None and len(last_X) >= MIN_SAMPLES_TRAIN:
            return last_df, last_X, last_y_labels, last_y_returns, last_bear, last_bull
    except Exception as e:
        print(f"  [{symbol}] DB error: {e}")
    return None, None, None, None, 0.0, 0.0


def prepare_training_data(
    df: pd.DataFrame,
    horizon_bars: int = HORIZON_BARS,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Prepare training data for h4 timeframe.

    Returns:
        (X, y_labels, y_returns, bear_thresh, bull_thresh)
    """
    df = df.copy()
    df = compute_simplified_features(df, sentiment_series=None)

    forward_returns = df["close"].pct_change(periods=horizon_bars).shift(-horizon_bars)

    bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
        df, horizon_days=1
    )
    valid_returns = forward_returns.dropna()
    if len(valid_returns) >= 30:
        bearish_thresh = float(valid_returns.quantile(0.35))
        bullish_thresh = float(valid_returns.quantile(0.65))

    engineer = TemporalFeatureEngineer()
    X_list = []
    y_labels_list = []
    y_returns_list = []

    end_idx = len(df) - horizon_bars

    for idx in range(START_IDX, end_idx):
        features = engineer.add_features_to_point(df, idx)
        actual_return = forward_returns.iloc[idx]

        if pd.notna(actual_return):
            X_list.append(features)
            y_returns_list.append(actual_return)
            if actual_return > bullish_thresh:
                y_labels_list.append("bullish")
            elif actual_return < bearish_thresh:
                y_labels_list.append("bearish")
            else:
                y_labels_list.append("neutral")

    X = pd.DataFrame(X_list)
    y_labels = pd.Series(y_labels_list)
    y_returns = pd.Series(y_returns_list)

    return X, y_labels, y_returns, bearish_thresh, bullish_thresh


def run_one_symbol(
    symbol: str,
    horizon_bars: int = HORIZON_BARS,
    target_samples: int = TARGET_SAMPLES,
) -> dict | None:
    """Train TabPFN on h4 data, return metrics."""
    df, X, y_labels, y_returns, bear_thresh, bull_thresh = load_ohlcv_until_enough(
        symbol, target_samples=target_samples, horizon_bars=horizon_bars
    )
    if df is None or X is None:
        return None

    if len(X) < MIN_SAMPLES_TRAIN:
        print(f"  {symbol}: skip (insufficient samples: {len(X)} < {MIN_SAMPLES_TRAIN})")
        return None

    numeric_cols = [c for c in SIMPLIFIED_FEATURES if c in X.columns and X[c].dtype in ["float64", "int64"]]
    if len(numeric_cols) < 5:
        print(f"  {symbol}: skip (too few numeric features: {len(numeric_cols)})")
        return None

    X_num = X[numeric_cols].copy()
    X_num = X_num.fillna(0.0)
    if X_num.isnull().any().any():
        print(f"  {symbol}: skip (NaN in features)")
        return None

    split_idx = int(len(X_num) * TRAIN_VAL_SPLIT)
    X_train, X_val = X_num.iloc[:split_idx], X_num.iloc[split_idx:]
    y_train_ret, y_val_ret = y_returns.iloc[:split_idx], y_returns.iloc[split_idx:]
    y_train_lab, y_val_lab = y_labels.iloc[:split_idx], y_labels.iloc[split_idx:]

    tabpfn = None
    try:
        from tabpfn import TabPFNRegressor
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_val_s = scaler.transform(X_val)

        tabpfn = TabPFNRegressor(device="cpu", n_estimators=8)
        tabpfn.fit(X_train_s, y_train_ret.values)

        y_pred_ret = tabpfn.predict(X_val_s)
        y_pred_lab = [
            "bullish" if r > bull_thresh else ("bearish" if r < bear_thresh else "neutral")
            for r in y_pred_ret
        ]

        train_pred = tabpfn.predict(X_train_s)
        train_lab = [
            "bullish" if r > bull_thresh else ("bearish" if r < bear_thresh else "neutral")
            for r in train_pred
        ]
        train_acc = sum(1 for a, b in zip(train_lab, y_train_lab.values) if a == b) / len(train_lab)
        val_acc = sum(1 for a, b in zip(y_pred_lab, y_val_lab.values) if a == b) / len(y_pred_lab)

        import time
        t0 = time.perf_counter()
        _ = tabpfn.predict(X_val_s[:1])
        infer_ms = (time.perf_counter() - t0) * 1000

        return {
            "symbol": symbol,
            "bars": len(df),
            "samples": len(X_num),
            "n_train": len(X_train),
            "n_val": len(X_val),
            "train_accuracy": train_acc,
            "val_accuracy": val_acc,
            "infer_ms": infer_ms,
            "label_dist": y_labels.value_counts().to_dict(),
        }
    except ImportError as e:
        print(f"  {symbol}: TabPFN not installed: {e}")
        return None
    except Exception as e:
        print(f"  {symbol}: TabPFN error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark TabPFN on hourly data")
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(BENCHMARK_SYMBOLS),
        help="Comma-separated symbols",
    )
    parser.add_argument(
        "--horizon-bars",
        type=int,
        default=HORIZON_BARS,
        help="Forecast horizon in bars (default: 2 for h4 ≈ 1 day)",
    )
    parser.add_argument(
        "--target-samples",
        type=int,
        default=TARGET_SAMPLES,
        help="Fetch until this many usable samples (default: 1000)",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    print(f"Benchmarking TabPFN on {TIMEFRAME} data (1 bar = 4 market hours)")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Horizon: {args.horizon_bars} bars (≈1 trading day)")
    print(f"Target samples: {args.target_samples} (expands fetch until enough)\n")

    results = []
    for symbol in symbols:
        out = run_one_symbol(
            symbol,
            horizon_bars=args.horizon_bars,
            target_samples=args.target_samples,
        )
        if out is None:
            continue
        results.append(out)
        print(
            f"  {symbol}: bars={out['bars']}, samples={out['samples']}, "
            f"train_acc={out['train_accuracy']:.1%}, val_acc={out['val_accuracy']:.1%}, "
            f"infer={out['infer_ms']:.0f}ms"
        )

    if not results:
        print(f"No symbols had sufficient {TIMEFRAME} data. Check Supabase availability.")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"BENCHMARK RESULTS ({TIMEFRAME}, TabPFN)")
    print("=" * 80)
    print(f"{'Symbol':<8} {'Bars':>6} {'Samples':>8} {'Train%':>8} {'Val%':>8} {'Infer(ms)':>10}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['symbol']:<8} {r['bars']:>6} {r['samples']:>8} "
            f"{r['train_accuracy']:>7.1%} {r['val_accuracy']:>7.1%} {r['infer_ms']:>10.0f}"
        )
    print("-" * 80)
    n = len(results)
    avg_train = sum(r["train_accuracy"] for r in results) / n
    avg_val = sum(r["val_accuracy"] for r in results) / n
    med_val = sorted(r["val_accuracy"] for r in results)[n // 2]
    print(f"{'MEAN':<8} {'':>6} {'':>8} {avg_train:>7.1%} {avg_val:>7.1%}")
    print(f"{'MED(val)':<8} {'':>6} {'':>8} {'':>8} {med_val:>7.1%}")
    print("=" * 80)


if __name__ == "__main__":
    main()
