#!/usr/bin/env python3
"""Single-split hybrid TabPFN + XGBoost test on AAPL."""

import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.supabase_db import SupabaseDatabase
from src.data.data_cleaner import DataCleaner
from src.models.xgboost_forecaster import XGBoostForecaster

try:
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion
    TABPFN_AVAILABLE = True
except ImportError:
    TABPFN_AVAILABLE = False
    ModelVersion = None


def _create_tabpfn_classifier():
    """Use V2 (non-gated) when HF_TOKEN is unset so Docker works without HuggingFace login."""
    if os.environ.get("HF_TOKEN"):
        return TabPFNClassifier(device="cpu", n_estimators=8)
    return TabPFNClassifier.create_default_for_version(ModelVersion.V2)


def load_aapl_supabase(timeframe: str = "d1", limit: int = 600) -> pd.DataFrame:
    """Load AAPL OHLCV. Default d1 (daily) for reliable walk-forward; 4h often has insufficient bars."""
    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars("AAPL", timeframe=timeframe, limit=limit)
    df = DataCleaner.clean_all(df, verbose=False)
    return df


def build_xy(df: pd.DataFrame, horizon_days: int = 5, threshold_pct: float = 0.015):
    """Use existing XGBoostForecaster feature pipeline (horizon in bars/days)."""
    forecaster = XGBoostForecaster()
    X, y, _ = forecaster.prepare_training_data_binary(
        df,
        horizon_days=horizon_days,
        threshold_pct=threshold_pct,
    )
    return X, y


def time_based_split(X: pd.DataFrame, y: pd.Series, val_frac: float = 0.2):
    n = len(X)
    split_idx = int(n * (1 - val_frac))
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
    return X_train, X_val, y_train, y_val


def evaluate_preds(y_true, y_prob, name: str):
    y_pred = (y_prob >= 0.5).astype(int)
    y_true_bin = np.where(np.asarray(y_true).ravel() == "bullish", 1, 0)
    acc = (y_pred == y_true_bin).mean()
    print(f"\n{name} accuracy: {acc:.3f}")
    return acc


def main():
    if not TABPFN_AVAILABLE:
        print("TabPFN not installed. Run: pip install tabpfn")
        sys.exit(1)

    # Daily bars: enough history for walk-forward; 4h often insufficient (e.g. TSLA ~683 bars)
    timeframe = "d1"
    limit = 600
    print(f"Loading AAPL from Supabase ({timeframe}, limit={limit})...")
    df = load_aapl_supabase(timeframe=timeframe, limit=limit)
    print(f"Loaded {len(df)} bars: {df['ts'].min()} → {df['ts'].max()}")

    horizon_days = 5
    threshold = 0.015

    print("\nPreparing features (X, y)...")
    X, y = build_xy(df, horizon_days=horizon_days, threshold_pct=threshold)
    print(f"X shape: {X.shape}, y shape: {y.shape}")

    X_train, X_val, y_train, y_val = time_based_split(X, y, val_frac=0.2)
    print(f"Train size: {len(X_train)}, Val size: {len(X_val)}")

    # 1) XGBoost baseline
    print("\nFitting XGBoost...")
    xgb = XGBoostForecaster()
    xgb.train(X_train, y_train, min_samples=30)
    xgb_proba = xgb.predict_proba(X_val)
    acc_xgb = evaluate_preds(y_val.values, xgb_proba, "XGBoost")

    # 2) TabPFN (same X, y; y as 0/1 for classifier)
    print("\nFitting TabPFN...")
    y_train_num = np.where(np.asarray(y_train).ravel() == "bullish", 1, 0)
    tabpfn = _create_tabpfn_classifier()
    # TabPFN has ~1000 sample limit for fit; we use last 1000 if larger
    X_tab = X_train.to_numpy(dtype=np.float32)
    if len(X_tab) > 1000:
        X_tab = X_tab[-1000:]
        y_train_num = y_train_num[-1000:]
    tabpfn.fit(X_tab, y_train_num)
    X_val_num = X_val.reindex(columns=X_train.columns).fillna(0).to_numpy(dtype=np.float32)
    tab_proba = tabpfn.predict_proba(X_val_num)[:, 1]
    acc_tab = evaluate_preds(y_val.values, tab_proba, "TabPFN")

    # 3) Hybrid ensemble: simple average
    alpha = 0.5  # weight for XGBoost; TabPFN gets (1-alpha)
    hybrid_proba = alpha * xgb_proba + (1 - alpha) * tab_proba
    acc_hybrid = evaluate_preds(y_val.values, hybrid_proba, f"Hybrid (alpha={alpha:.2f})")

    print("\n==========================")
    print("FINAL RESULTS (AAPL, single-split, Supabase, daily, 5-day horizon)")
    print("==========================")
    print(f"XGBoost accuracy : {acc_xgb:.3f}")
    print(f"TabPFN accuracy  : {acc_tab:.3f}")
    print(f"Hybrid accuracy  : {acc_hybrid:.3f}")


if __name__ == "__main__":
    main()
