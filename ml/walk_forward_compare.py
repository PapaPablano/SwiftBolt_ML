#!/usr/bin/env python3
"""
Walk-forward validation for ARIMA-GARCH vs XGBoost.

Based on research:
- Alpha Scientist walk-forward methodology
- QuantInsti WFO in Python (2025)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

sys.path.insert(0, str(Path(__file__).resolve().parent))


def walk_forward_validation(
    model_class,
    df: pd.DataFrame,
    sentiment: pd.Series | None,
    threshold_pct: float = 0.008,
    train_window: int = 252,
    refit_frequency: int = 21,
):
    """
    Walk-forward validation with periodic retraining.

    Args:
        model_class: Forecaster class (ARIMAGARCHForecaster or XGBoostForecaster)
        df: OHLCV DataFrame
        sentiment: Sentiment series (or None)
        threshold_pct: Binary classification threshold
        train_window: Training window size (days)
        refit_frequency: Retrain every N days

    Returns:
        Dict with accuracy, n_windows, n_predictions, refit_points
    """
    forecaster = model_class()

    X, y, dates = forecaster.prepare_training_data_binary(
        df,
        horizon_days=1,
        sentiment_series=sentiment,
        threshold_pct=threshold_pct,
        add_simple_regime=True,
    )

    # Cap train_window/refit_frequency to actual len(X) when small-move filtering left fewer rows than expected
    min_samples_for_one_window = 150  # need at least one train window + some test
    if len(X) < min_samples_for_one_window:
        raise ValueError("Insufficient data for walk-forward")
    if len(X) < train_window + 50:
        train_window = min(train_window, max(100, len(X) - 50))
        refit_frequency = min(refit_frequency, max(21, train_window // 5))

    # Ensure we have indexable y/dates
    if hasattr(y, "iloc"):
        y_use = y
    else:
        y_use = pd.Series(y)
    if hasattr(dates, "iloc"):
        dates_use = dates
    else:
        dates_use = pd.Series(dates)

    predictions = []
    actuals = []
    prediction_dates = []
    refit_points = []

    for i in range(train_window, len(X), refit_frequency):
        train_start = max(0, i - train_window)
        X_train = X.iloc[train_start:i] if hasattr(X, "iloc") else X[train_start:i]
        y_train = y_use.iloc[train_start:i] if hasattr(y_use, "iloc") else y_use[train_start:i]
        test_end = min(len(X), i + refit_frequency)
        X_test = X.iloc[i:test_end] if hasattr(X, "iloc") else X[i:test_end]
        y_test = y_use.iloc[i:test_end] if hasattr(y_use, "iloc") else y_use[i:test_end]

        if len(X_test) == 0:
            break

        forecaster.train(X_train, y_train, min_samples=50)
        y_pred = forecaster.predict_batch(X_test)

        predictions.extend(np.asarray(y_pred).ravel().tolist())
        actuals.extend(np.asarray(y_test).ravel().tolist())
        chunk_dates = dates_use.iloc[i:test_end] if hasattr(dates_use, "iloc") else dates_use[i:test_end]
        prediction_dates.extend(chunk_dates.tolist() if hasattr(chunk_dates, "tolist") else list(chunk_dates))
        refit_points.append(dates_use.iloc[i] if hasattr(dates_use, "iloc") else dates_use[i])
        print(f"  Window {len(refit_points)}: trained on {len(X_train)}, tested on {len(X_test)}")

    acc = accuracy_score(actuals, predictions)
    return {
        "accuracy": acc,
        "n_windows": len(refit_points),
        "n_predictions": len(predictions),
        "refit_points": refit_points,
        "prediction_dates": prediction_dates,
        "predictions": predictions,
        "actuals": actuals,
    }


def main() -> None:
    symbol = "TSLA"
    threshold = 0.008

    print(f"Loading {symbol}...")
    try:
        from src.data.supabase_db import SupabaseDatabase
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=600)
    except Exception as e:
        print(f"DB error: {e}")
        sys.exit(1)

    if df is None or len(df) < 300:
        print("Insufficient OHLCV data.")
        sys.exit(1)

    start_date = pd.to_datetime(df["ts"]).min().date()
    end_date = pd.to_datetime(df["ts"]).max().date()
    sentiment = None
    try:
        from src.features.stock_sentiment import get_historical_sentiment_series
        sentiment = get_historical_sentiment_series(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception as e:
        print(f"Sentiment load failed: {e} (continuing without)")

    results: dict = {}

    print("\n" + "=" * 60)
    print("ARIMA-GARCH Walk-Forward Validation")
    print("=" * 60)
    try:
        from src.models.arima_garch_forecaster import ARIMAGARCHForecaster
        results["ARIMA-GARCH"] = walk_forward_validation(
            ARIMAGARCHForecaster,
            df,
            sentiment,
            threshold_pct=threshold,
        )
    except Exception as e:
        print(f"ARIMA-GARCH failed: {e}")
        results["ARIMA-GARCH"] = {"accuracy": 0.0, "n_windows": 0, "n_predictions": 0, "refit_points": []}

    print("\n" + "=" * 60)
    print("XGBoost Walk-Forward Validation")
    print("=" * 60)
    try:
        from src.models.xgboost_forecaster import XGBoostForecaster
        results["XGBoost"] = walk_forward_validation(
            XGBoostForecaster,
            df,
            sentiment,
            threshold_pct=threshold,
        )
    except Exception as e:
        print(f"XGBoost failed: {e}")
        results["XGBoost"] = {"accuracy": 0.0, "n_windows": 0, "n_predictions": 0, "refit_points": []}

    print("\n" + "=" * 60)
    print("WALK-FORWARD RESULTS")
    print("=" * 60)
    for model, res in sorted(results.items(), key=lambda x: x[1]["accuracy"], reverse=True):
        print(f"{model:20s}: {res['accuracy']:.1%} ({res['n_windows']} windows, {res['n_predictions']} predictions)")
    print("=" * 60)

    best = max(results.items(), key=lambda x: x[1]["accuracy"])
    print(f"\nBest model: {best[0]} ({best[1]['accuracy']:.1%})")
    if best[1]["accuracy"] >= 0.55:
        print("PRODUCTION READY (>55%)")
    else:
        print("Below 55% threshold")


if __name__ == "__main__":
    main()
