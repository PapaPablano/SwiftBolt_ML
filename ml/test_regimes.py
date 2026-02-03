#!/usr/bin/env python3
"""Market regime backtesting for 10 stocks."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from src.data.supabase_db import SupabaseDatabase
    from src.data.data_cleaner import DataCleaner
    from src.models.xgboost_forecaster import XGBoostForecaster
    from src.models.arima_garch_forecaster import ARIMAGARCHForecaster
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Market regimes (date ranges)
REGIMES = {
    "crash_2022": {
        "start": "2022-03-01",
        "end": "2022-10-31",
        "type": "Bear Market Crash",
        "spx_return": -18.1,
    },
    "recovery_2023": {
        "start": "2022-11-01",
        "end": "2023-12-31",
        "type": "Post-Crash Recovery",
        "spx_return": 26.3,
    },
    "bull_2024_2025": {
        "start": "2024-01-01",
        "end": "2025-12-31",
        "type": "Mega-Cap Bull Market",
        "spx_return": 42.9,
    },
    "rotation_2021_2022": {
        "start": "2021-11-01",
        "end": "2022-04-30",
        "type": "Rotation from Growth",
        "spx_return": -15.5,
    },
}

STOCKS = {
    "defensive": ["PG", "KO", "JNJ", "MRK"],
    "quality": ["MSFT", "AMGN", "BRK.B"],
    "growth": ["NVDA", "MU", "ALB"],
}

HORIZONS = {"defensive": 5, "quality": 5, "growth": 5}
THRESHOLDS = {"defensive": 0.015, "quality": 0.015, "growth": 0.02}
TRAIN_FRAC = 0.8
MIN_SAMPLES = 50


def load_stock_by_regime(symbol: str, regime: dict, limit: int = 2000) -> pd.DataFrame | None:
    """Load OHLCV for symbol, clean, filter to regime period."""
    try:
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=limit)
        if df is None or len(df) < 100:
            return None
        df = DataCleaner.clean_all(df, verbose=False)
        df["ts"] = pd.to_datetime(df["ts"])
        start = pd.to_datetime(regime["start"])
        end = pd.to_datetime(regime["end"])
        df_regime = df[(df["ts"] >= start) & (df["ts"] <= end)].copy()
        return df_regime if len(df_regime) >= 100 else None
    except Exception:
        return None


def evaluate_xgb(
    df: pd.DataFrame, horizon: int, threshold: float, train_frac: float = TRAIN_FRAC
) -> tuple[float | None, int]:
    """Single time-based split: train XGBoost, return accuracy and sample count."""
    try:
        forecaster = XGBoostForecaster()
        X, y, _ = forecaster.prepare_training_data_binary(
            df, horizon_days=horizon, threshold_pct=threshold, add_simple_regime=True
        )
        if len(X) < MIN_SAMPLES:
            return None, len(X)
        split_idx = int(len(X) * train_frac)
        if split_idx < MIN_SAMPLES or len(X) - split_idx < 10:
            return None, len(X)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        forecaster.train(X_train, y_train, min_samples=30)
        y_pred = forecaster.predict_batch(X_test)
        y_test_arr = np.asarray(y_test).ravel()
        y_pred_arr = np.asarray(y_pred).ravel()
        acc = accuracy_score(y_test_arr, y_pred_arr)
        return float(acc), len(X)
    except Exception:
        return None, 0


def evaluate_arima(
    df: pd.DataFrame, horizon: int, threshold: float, train_frac: float = TRAIN_FRAC
) -> tuple[float | None, int]:
    """Single time-based split: train ARIMA-GARCH, return accuracy and sample count."""
    try:
        forecaster = ARIMAGARCHForecaster()
        X, y, _ = forecaster.prepare_training_data_binary(
            df, horizon_days=horizon, threshold_pct=threshold
        )
        X, y = np.asarray(X), np.asarray(y).ravel()
        if len(X) < MIN_SAMPLES:
            return None, len(X)
        split_idx = int(len(X) * train_frac)
        if split_idx < MIN_SAMPLES or len(X) - split_idx < 10:
            return None, len(X)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        forecaster.train(X_train, y_train, min_samples=30)
        y_pred = forecaster.predict_batch(X_test)
        y_pred_arr = np.asarray(y_pred).ravel()
        acc = accuracy_score(y_test, y_pred_arr)
        return float(acc), len(X)
    except Exception:
        return None, 0


def evaluate_regime(
    symbol: str, regime_name: str, regime: dict, category: str
) -> dict | None:
    """Evaluate one stock in one regime (XGB + ARIMA, single split)."""
    horizon = HORIZONS[category]
    threshold = THRESHOLDS[category]

    df = load_stock_by_regime(symbol, regime, limit=2000)
    if df is None or len(df) < 100:
        return None

    acc_xgb, n_xgb = evaluate_xgb(df, horizon, threshold)
    acc_arima, n_arima = evaluate_arima(df, horizon, threshold)

    return {
        "xgb": acc_xgb,
        "arima": acc_arima,
        "samples_xgb": n_xgb,
        "samples_arima": n_arima,
        "bars": len(df),
    }


def main():
    print("=" * 100)
    print("MARKET REGIME BACKTESTING: 10 Stocks × 4 Regimes (single 80/20 split per model)")
    print("=" * 100)

    results = {}  # regime_name -> { symbol -> { xgb, arima, ... } }

    for regime_name, regime in REGIMES.items():
        print(f"\n{'─' * 100}")
        print(
            f"REGIME: {regime['type']} ({regime['start']} to {regime['end']}) | S&P 500: {regime['spx_return']:+.1f}%"
        )
        print("─" * 100)

        results[regime_name] = {}

        for category, symbols in STOCKS.items():
            print(f"\n  {category.upper()}: ", end="", flush=True)
            for symbol in symbols:
                res = evaluate_regime(symbol, regime_name, regime, category)
                if res is None:
                    print(f"{symbol}: no data  ", end="", flush=True)
                    continue
                results[regime_name][symbol] = res
                xgb_s = f"{res['xgb']:.1%}" if res["xgb"] is not None else "N/A"
                arima_s = f"{res['arima']:.1%}" if res["arima"] is not None else "N/A"
                print(f"{symbol}(XGB:{xgb_s}, ARIMA:{arima_s})  ", end="", flush=True)
            print()

    # Summary: XGBoost accuracy by stock & regime
    print("\n\n" + "=" * 100)
    print("SUMMARY: XGBoost Accuracy (%) by Stock & Regime")
    print("=" * 100)

    rows = []
    for regime_name, regime in REGIMES.items():
        for symbol, res in results.get(regime_name, {}).items():
            acc = res["xgb"]
            rows.append(
                {
                    "Stock": symbol,
                    "Regime": regime["type"],
                    "Accuracy": acc if acc is not None else np.nan,
                    "Samples": res["samples_xgb"],
                }
            )

    if rows:
        summary_df = pd.DataFrame(rows)
        pivot = summary_df.pivot_table(
            index="Stock", columns="Regime", values="Accuracy", aggfunc="first"
        )
        print("\n")
        print(pivot.to_string())
        print("\n\nKey insights (average XGB accuracy by regime):")
        for regime_name, regime in REGIMES.items():
            accs = [
                r["xgb"]
                for r in results.get(regime_name, {}).values()
                if r and r["xgb"] is not None
            ]
            if accs:
                print(f"  {regime['type']}: {np.nanmean(accs):.1%} (n={len(accs)})")
    else:
        print("No results (check Supabase data and symbols).")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
