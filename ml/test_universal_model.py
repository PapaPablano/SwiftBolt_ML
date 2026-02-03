#!/usr/bin/env python3
"""
Test a universal XGBoost model trained on multiple symbols (walk-forward).

Walk-forward is by CALENDAR DATE so train/test are aligned across symbols
(no lookahead). Features are aligned across symbols (missing filled with
median). Symbol is one-hot encoded.

Usage:
  cd ml && python test_universal_model.py
  python test_universal_model.py --symbols TSLA NVDA AAPL MSFT SPY --threshold 0.008
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Default symbols (same as multi-symbol compare_models)
DEFAULT_SYMBOLS = ["TSLA", "NVDA", "AAPL", "MSFT", "SPY"]
TRAIN_DAYS = 252
REFIT_DAYS = 21
THRESHOLD_PCT = 0.008

# Meta columns (not features)
META_COLS = {"date", "symbol", "y"}


def load_and_prepare_symbol(
    symbol: str,
    db,
    threshold_pct: float,
) -> tuple[pd.DataFrame, pd.Series, pd.Series] | None:
    """Fetch OHLCV, optional sentiment, prepare binary (X, y, dates). Returns None on failure."""
    try:
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=600)
    except Exception as e:
        print(f"  [{symbol}] DB error: {e}")
        return None
    if df is None or len(df) < 250:
        print(f"  [{symbol}] Insufficient data: {len(df) if df is not None else 0}")
        return None

    sentiment = None
    try:
        from src.features.stock_sentiment import get_historical_sentiment_series
        start_date = pd.to_datetime(df["ts"]).min().date()
        end_date = pd.to_datetime(df["ts"]).max().date()
        sentiment = get_historical_sentiment_series(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception:
        pass

    from src.models.xgboost_forecaster import XGBoostForecaster
    forecaster = XGBoostForecaster()
    X, y, dates = forecaster.prepare_training_data_binary(
        df,
        horizon_days=1,
        sentiment_series=sentiment,
        threshold_pct=threshold_pct,
        add_simple_regime=True,
    )
    if len(X) < 80:
        print(f"  [{symbol}] Too few samples after threshold: {len(X)}")
        return None
    return X, y, dates


def align_features_across_symbols(
    pieces: list[tuple[pd.DataFrame, pd.Series, pd.Series, str]],
) -> list[pd.DataFrame]:
    """
    Ensure all symbols have the same feature columns.
    Missing columns filled with median across all pieces (not 0).
    Returns list of DataFrames with columns [feature_cols..., date, symbol, y].
    """
    # Union of all feature columns (exclude meta we'll add later)
    all_cols = set()
    for X, _y, _dates, _sym in pieces:
        all_cols.update(c for c in X.columns if c not in META_COLS and c != "ts")
    if "ts" in all_cols:
        all_cols.discard("ts")
    feature_cols = sorted(all_cols)

    # Median per column from all pieces that have it
    medians = {}
    for col in feature_cols:
        series_list = [p[0][col] for p in pieces if col in p[0].columns]
        if series_list:
            medians[col] = pd.concat(series_list, ignore_index=True).median()
        else:
            medians[col] = 0.0

    aligned = []
    for X, y, dates, symbol in pieces:
        X = X.copy()
        X = X.reindex(columns=feature_cols)
        for col in feature_cols:
            if col in X.columns and X[col].isna().any():
                X[col] = X[col].fillna(medians[col])
        # Fill missing columns (symbol had no data for this feature)
        for col in feature_cols:
            if col not in X.columns or X[col].isna().all():
                X[col] = medians[col]
        dt = pd.to_datetime(dates)
        X["date"] = dt.dt.normalize() if hasattr(dt, "dt") else dt.normalize()
        X["symbol"] = symbol
        X["y"] = np.asarray(y).ravel()
        aligned.append(X)
    return aligned


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward validation for universal XGBoost (multi-symbol)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help=f"Symbols to pool (default: {' '.join(DEFAULT_SYMBOLS)})",
    )
    parser.add_argument("--threshold", type=float, default=THRESHOLD_PCT, help="Binary return threshold")
    parser.add_argument("--train-days", type=int, default=TRAIN_DAYS, help="Training window (calendar days)")
    parser.add_argument("--refit-days", type=int, default=REFIT_DAYS, help="Refit every N calendar days")
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols]
    threshold_pct = args.threshold
    train_days = args.train_days
    refit_days = args.refit_days

    print("Loading and preparing symbols...")
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
    except Exception as e:
        print(f"DB error: {e}")
        sys.exit(1)

    pieces_raw: list[tuple[pd.DataFrame, pd.Series, pd.Series, str]] = []
    for symbol in symbols:
        out = load_and_prepare_symbol(symbol, db, threshold_pct)
        if out is None:
            continue
        X, y, dates = out
        pieces_raw.append((X, y, dates, symbol))
        print(f"  {symbol}: {len(X)} samples")

    if len(pieces_raw) < 2:
        print("Need at least 2 symbols with data. Exiting.")
        sys.exit(1)

    # Align features (median fill for missing), add date + symbol + y
    aligned_dfs = align_features_across_symbols(pieces_raw)
    combined = pd.concat(aligned_dfs, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)

    # One-hot encode symbol (no ordinal assumption)
    combined = pd.get_dummies(combined, columns=["symbol"], prefix="symbol")

    # Unique calendar dates (global timeline for walk-forward)
    unique_dates = sorted(combined["date"].unique())
    n_dates = len(unique_dates)
    print(f"\nPooled: {len(combined)} rows from {len(pieces_raw)} symbols; {n_dates} unique calendar dates")

    if n_dates < train_days + refit_days:
        print("Insufficient unique calendar days for walk-forward.")
        sys.exit(1)

    # Feature columns only (exclude date, y)
    y_col = "y"
    date_col = "date"
    feature_cols = [c for c in combined.columns if c not in (date_col, y_col)]
    X_full = combined[feature_cols]
    y_full = combined[y_col]
    dates_full = combined[date_col]

    from src.models.xgboost_forecaster import XGBoostForecaster

    predictions = []
    actuals = []
    n_windows = 0

    print("\n" + "=" * 60)
    print("Universal XGBoost Walk-Forward (by calendar date)")
    print("=" * 60)

    for i in range(train_days, n_dates, refit_days):
        train_dates = set(unique_dates[:i])
        test_dates = unique_dates[i : i + refit_days]
        if not test_dates:
            break

        train_mask = dates_full.isin(train_dates)
        test_mask = dates_full.isin(test_dates)
        X_train = X_full.loc[train_mask]
        y_train = y_full.loc[train_mask]
        X_test = X_full.loc[test_mask]
        y_test = y_full.loc[test_mask]

        if len(X_train) < 50 or len(X_test) == 0:
            break

        forecaster = XGBoostForecaster()
        forecaster.train(X_train, y_train, min_samples=50)
        y_pred = forecaster.predict_batch(X_test)

        predictions.extend(np.asarray(y_pred).ravel().tolist())
        actuals.extend(np.asarray(y_test).ravel().tolist())
        n_windows += 1
        print(f"  Window {n_windows}: train dates {unique_dates[0]}..{unique_dates[i-1]} ({len(X_train)} rows), test dates {test_dates[0]}..{test_dates[-1]} ({len(X_test)} rows)")

    if not actuals:
        print("No predictions produced.")
        sys.exit(1)

    acc = accuracy_score(actuals, predictions)

    print("=" * 60)
    print("UNIVERSAL MODEL WALK-FORWARD RESULT")
    print("=" * 60)
    print(f"  Accuracy:    {acc:.1%}")
    print(f"  Windows:     {n_windows}")
    print(f"  Predictions: {len(predictions)}")
    print("=" * 60)

    if acc >= 0.56:
        print("\nProduction-ready (>=56% walk-forward).")
    elif acc >= 0.55:
        print("\nMarginal (55–56%). Consider more symbols or features.")
    else:
        print("\nBelow 55%. Single-symbol walk-forward is the baseline; universal may need more data or tuning.")


if __name__ == "__main__":
    main()
