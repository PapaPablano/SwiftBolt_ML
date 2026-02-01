#!/usr/bin/env python3
"""Validate simplified feature set: assert columns, check NaN/inf, print stats."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.features.temporal_indicators import (
    SIMPLIFIED_FEATURES,
    compute_simplified_features,
    prepare_training_data_temporal,
)


def make_synthetic_ohlcv(n_rows: int = 260) -> pd.DataFrame:
    """Build synthetic OHLCV with required columns for feature validation."""
    np.random.seed(42)
    t = np.arange(n_rows, dtype=float)
    close = 100 + np.cumsum(np.random.randn(n_rows) * 0.5)
    high = close + np.abs(np.random.randn(n_rows) * 0.5)
    low = close - np.abs(np.random.randn(n_rows) * 0.5)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    volume = np.random.randint(1_000_000, 10_000_000, size=n_rows).astype(float)
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def main() -> None:
    print("Validating simplified feature set...")
    df = make_synthetic_ohlcv(260)
    df = compute_simplified_features(df)

    missing = [c for c in SIMPLIFIED_FEATURES if c not in df.columns]
    if missing:
        print(f"FAIL: Missing columns: {missing}")
        sys.exit(1)
    print(f"OK: All {len(SIMPLIFIED_FEATURES)} simplified features present.")

    # NaN/inf report
    feats = df[SIMPLIFIED_FEATURES]
    nan_counts = feats.isna().sum()
    inf_counts = np.isinf(feats.select_dtypes(include=[np.number])).sum()
    if nan_counts.any():
        print("\nNaN counts (first 10 with NaNs):")
        print(nan_counts[nan_counts > 0].head(10))
    if hasattr(inf_counts, "any") and inf_counts.any():
        print("\nInf counts:")
        print(inf_counts[inf_counts > 0])
    print("\nHead of simplified features (first 3 rows, first 8 cols):")
    print(feats.iloc[:3, :8].to_string())

    # Prepare training data and assert X columns
    X, y = prepare_training_data_temporal(df, horizon_days=1, use_simplified_features=True)
    x_cols = set(X.columns)
    expected = set(SIMPLIFIED_FEATURES) | {"ts"}
    if not expected.issubset(x_cols):
        print(f"FAIL: X missing columns: {expected - x_cols}")
        sys.exit(1)
    print(f"\nOK: prepare_training_data_temporal returned X with {len(X)} samples.")
    print("Done.")


if __name__ == "__main__":
    main()
