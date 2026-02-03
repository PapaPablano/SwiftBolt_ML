"""
Walk-Forward Validation for time-series ML models.

Implements expanding-window and rolling-window walk-forward so the model
is always evaluated on truly unseen future periods (no lookahead).
"""

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)


def _load_ohlcv(symbol: str, limit: int) -> pd.DataFrame | None:
    """Load OHLCV from Supabase for symbol."""
    try:
        from src.data.supabase_db import SupabaseDatabase

        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=limit)
        if df is not None and len(df) >= 250:
            return df
    except Exception as e:
        logger.warning("DB error loading OHLCV for %s: %s", symbol, e)
    return None


def _load_sentiment(
    symbol: str, start_date: Any, end_date: Any
) -> pd.Series | None:
    """Load daily sentiment for symbol over [start_date, end_date]."""
    try:
        from src.features.stock_sentiment import get_historical_sentiment_series

        return get_historical_sentiment_series(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_finviz_realtime=True,
        )
    except Exception as e:
        logger.warning("Sentiment error for %s: %s", symbol, e)
    return None


def _predict_batch_binary(forecaster: Any, X_test: pd.DataFrame, use_tabpfn: bool) -> np.ndarray:
    """Binary (bullish/bearish) predictions. TabPFN: sign of return; Baseline (XGBoost): decode 0/1/2."""
    cols = [c for c in forecaster.feature_columns if c in X_test.columns]
    X = X_test[cols]
    X_scaled = forecaster.scaler.transform(X)
    if use_tabpfn:
        pred_returns = forecaster.model.predict(X_scaled)
        pred_returns = np.atleast_1d(pred_returns)
        return np.where(pred_returns > 0, "bullish", "bearish")
    pred_encoded = forecaster.model.predict(X_scaled)
    pred_encoded = np.atleast_1d(pred_encoded)
    decode = getattr(forecaster, "_label_decode", None)
    if not decode:
        from src.models.baseline_forecaster import LABEL_DECODE
        decode = LABEL_DECODE
    return np.array([decode.get(int(p), "neutral") for p in pred_encoded])


def _predict_batch(forecaster: Any, X_test: pd.DataFrame) -> np.ndarray:
    """
    Get batch predictions (labels) from a trained forecaster.
    Works with BaselineForecaster (labels) and TabPFNForecaster (return -> label).
    """
    cols = [c for c in forecaster.feature_columns if c in X_test.columns]
    X = X_test[cols]
    X_scaled = forecaster.scaler.transform(X)

    # BaselineForecaster (XGBoost): model predicts 0/1/...; decode using forecaster._label_decode
    if hasattr(forecaster.model, "predict_proba"):
        pred_encoded = forecaster.model.predict(X_scaled)
        pred_encoded = np.atleast_1d(pred_encoded)
        decode = getattr(forecaster, "_label_decode", None)
        if not decode:
            from src.models.baseline_forecaster import LABEL_DECODE
            decode = LABEL_DECODE
        return np.array([decode.get(int(p), "neutral") for p in pred_encoded])

    # TabPFNForecaster: model predicts returns; convert to labels
    y_returns = forecaster.model.predict(X_scaled)
    if np.isscalar(y_returns):
        y_returns = np.array([y_returns])
    labels = []
    for r in np.atleast_1d(y_returns):
        if r < forecaster._bearish_thresh:
            labels.append("bearish")
        elif r > forecaster._bullish_thresh:
            labels.append("bullish")
        else:
            labels.append("neutral")
    return np.array(labels)


def _returns_to_labels(
    y_returns: pd.Series | np.ndarray,
    bear_thresh: float,
    bull_thresh: float,
) -> np.ndarray:
    """Convert continuous returns to bearish/neutral/bullish labels."""
    arr = np.atleast_1d(y_returns)
    labels = []
    for r in arr:
        if r < bear_thresh:
            labels.append("bearish")
        elif r > bull_thresh:
            labels.append("bullish")
        else:
            labels.append("neutral")
    return np.array(labels)


def walk_forward_validate(
    symbol: str,
    timeframe: str = "d1",
    horizon_days: int = 1,
    initial_train_days: int = 200,
    test_days: int = 50,
    step_days: int = 50,
    use_tabpfn: bool = True,
    binary_mode: bool = False,
    threshold_pct: float = 0.005,
    add_regime: bool = False,
) -> Dict[str, Any]:
    """
    Walk-forward validation with expanding window.

    Each window: train on all past data, test on next period (blind).
    If binary_mode=True, only bullish/bearish (filter |return| < threshold_pct).
    Random baseline: 33.3% (3-class) or 50% (binary).

    Returns:
        Dict with mean_accuracy, std_accuracy, window_accuracies, windows,
        predictions_df, n_windows, symbol, overall_accuracy.
    """
    from src.models.baseline_forecaster import BaselineForecaster
    from src.models.tabpfn_forecaster import TabPFNForecaster

    lookback = initial_train_days + 600
    df = _load_ohlcv(symbol, limit=lookback)
    if df is None:
        raise ValueError(f"Insufficient OHLCV data for {symbol} (need >= 250 bars)")

    start_ts = pd.to_datetime(df["ts"]).min()
    end_ts = pd.to_datetime(df["ts"]).max()
    sentiment = _load_sentiment(symbol, start_ts, end_ts)

    if use_tabpfn:
        forecaster_cls = TabPFNForecaster
    else:
        forecaster_cls = BaselineForecaster

    prep = forecaster_cls()
    if binary_mode:
        X, y, dates = prep.prepare_training_data_binary(
            df,
            horizon_days=horizon_days,
            sentiment_series=sentiment,
            threshold_pct=threshold_pct,
            add_simple_regime=add_regime,
        )
        dates = dates.reset_index(drop=True)
        if len(dates) != len(X):
            dates = dates.iloc[: len(X)]
    else:
        X, y = prep.prepare_training_data(
            df, horizon_days=horizon_days, sentiment_series=sentiment
        )
        horizon_int = max(1, int(np.ceil(horizon_days)))
        start_idx = 200
        end_idx = len(df) - horizon_int
        dates = pd.to_datetime(df["ts"]).iloc[start_idx:end_idx]
        dates = dates.reset_index(drop=True)
        if len(dates) != len(X):
            dates = dates.iloc[: len(X)]

    if len(X) < initial_train_days + test_days:
        raise ValueError(
            f"Not enough samples for walk-forward: {len(X)} "
            f"(need >= {initial_train_days + test_days})"
        )

    windows: List[Dict[str, Any]] = []
    all_predictions: List[str] = []
    all_actuals: List[Any] = []
    all_dates: List[pd.Timestamp] = []

    split_idx = initial_train_days

    while split_idx + test_days <= len(X):
        X_train = X.iloc[:split_idx]
        y_train = y.iloc[:split_idx]
        X_test = X.iloc[split_idx : split_idx + test_days]
        y_test = y.iloc[split_idx : split_idx + test_days]
        test_dates = dates.iloc[split_idx : split_idx + test_days]

        model = forecaster_cls()
        model.train(X_train, y_train, min_samples=50)

        if binary_mode:
            y_pred = _predict_batch_binary(model, X_test, use_tabpfn)
            if use_tabpfn and np.issubdtype(y_test.dtype, np.floating):
                y_test_labels = np.where(
                    np.asarray(y_test) > 0, "bullish", "bearish"
                )
            else:
                y_test_labels = y_test
            acc = accuracy_score(y_test_labels, y_pred)
            actuals_for_df = y_test_labels
        else:
            y_pred = _predict_batch(model, X_test)
            if use_tabpfn and np.issubdtype(y_test.dtype, np.floating):
                y_test_labels = _returns_to_labels(
                    y_test, model._bearish_thresh, model._bullish_thresh
                )
                acc = accuracy_score(y_test_labels, y_pred)
                actuals_for_df = y_test_labels
            else:
                acc = accuracy_score(y_test, y_pred)
                actuals_for_df = y_test

        windows.append({
            "train_start": dates.iloc[0],
            "train_end": dates.iloc[split_idx - 1],
            "test_start": test_dates.iloc[0],
            "test_end": test_dates.iloc[-1],
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": acc,
        })
        all_predictions.extend(y_pred.tolist())
        all_actuals.extend(
            actuals_for_df.tolist()
            if hasattr(actuals_for_df, "tolist")
            else list(actuals_for_df)
        )
        all_dates.extend(test_dates.tolist())

        logger.info(
            "Window %s: Train [%s..%s], Test [%s..%s], Acc=%.1f%%",
            len(windows),
            dates.iloc[0].date(),
            dates.iloc[split_idx - 1].date(),
            test_dates.iloc[0].date(),
            test_dates.iloc[-1].date(),
            acc * 100,
        )

        split_idx += step_days

    accuracies = [w["accuracy"] for w in windows]
    mean_acc = float(np.mean(accuracies))
    std_acc = float(np.std(accuracies)) if len(accuracies) > 1 else 0.0
    overall_acc = accuracy_score(all_actuals, all_predictions)

    predictions_df = pd.DataFrame({
        "date": all_dates,
        "actual": all_actuals,
        "predicted": all_predictions,
    })

    logger.info(
        "WALK-FORWARD %s: windows=%s, mean_acc=%.1f%% ± %.1f%%, overall=%.1f%%",
        symbol,
        len(windows),
        mean_acc * 100,
        std_acc * 100,
        overall_acc * 100,
    )

    return {
        "symbol": symbol,
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "overall_accuracy": overall_acc,
        "window_accuracies": accuracies,
        "windows": windows,
        "predictions_df": predictions_df,
        "n_windows": len(windows),
    }


def walk_forward_rolling(
    symbol: str,
    timeframe: str = "d1",
    horizon_days: int = 1,
    window_size: int = 200,
    test_days: int = 50,
    step_days: int = 50,
    use_tabpfn: bool = True,
) -> Dict[str, Any]:
    """
    Walk-forward validation with rolling (fixed-size) training window.

    Window 1: Train [0:200],     Test [200:250]
    Window 2: Train [50:250],    Test [250:300]
    Window 3: Train [100:300],  Test [300:350]
    ...

    Faster than expanding window but uses less history per model.
    """
    from src.models.baseline_forecaster import BaselineForecaster
    from src.models.tabpfn_forecaster import TabPFNForecaster

    lookback = window_size + 600
    df = _load_ohlcv(symbol, limit=lookback)
    if df is None:
        raise ValueError(f"Insufficient OHLCV data for {symbol}")

    start_ts = pd.to_datetime(df["ts"]).min()
    end_ts = pd.to_datetime(df["ts"]).max()
    sentiment = _load_sentiment(symbol, start_ts, end_ts)

    forecaster_cls = TabPFNForecaster if use_tabpfn else BaselineForecaster
    prep = forecaster_cls()
    X, y = prep.prepare_training_data(
        df, horizon_days=horizon_days, sentiment_series=sentiment
    )

    horizon_int = max(1, int(np.ceil(horizon_days)))
    start_idx = 200
    end_idx = len(df) - horizon_int
    dates = pd.to_datetime(df["ts"]).iloc[start_idx:end_idx].reset_index(drop=True)
    if len(dates) > len(X):
        dates = dates.iloc[: len(X)]

    windows = []
    all_predictions = []
    all_actuals = []
    all_dates = []

    split_start = 0
    while split_start + window_size + test_days <= len(X):
        train_end = split_start + window_size
        test_end = train_end + test_days

        X_train = X.iloc[split_start:train_end]
        y_train = y.iloc[split_start:train_end]
        X_test = X.iloc[train_end:test_end]
        y_test = y.iloc[train_end:test_end]
        test_dates = dates.iloc[train_end:test_end]

        model = forecaster_cls()
        model.train(X_train, y_train, min_samples=50)

        y_pred = _predict_batch(model, X_test)
        if use_tabpfn and np.issubdtype(y_test.dtype, np.floating):
            y_test_labels = _returns_to_labels(
                y_test, model._bearish_thresh, model._bullish_thresh
            )
            acc = accuracy_score(y_test_labels, y_pred)
            actuals_for_df = y_test_labels
        else:
            acc = accuracy_score(y_test, y_pred)
            actuals_for_df = y_test

        windows.append({
            "train_start": dates.iloc[split_start],
            "train_end": dates.iloc[train_end - 1],
            "test_start": test_dates.iloc[0],
            "test_end": test_dates.iloc[-1],
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": acc,
        })
        all_predictions.extend(y_pred.tolist())
        all_actuals.extend(
            actuals_for_df.tolist()
            if hasattr(actuals_for_df, "tolist")
            else list(actuals_for_df)
        )
        all_dates.extend(test_dates.tolist())

        logger.info(
            "Rolling window %s: Train [%s..%s], Test [%s..%s], Acc=%.1f%%",
            len(windows),
            dates.iloc[split_start].date(),
            dates.iloc[train_end - 1].date(),
            test_dates.iloc[0].date(),
            test_dates.iloc[-1].date(),
            acc * 100,
        )

        split_start += step_days

    accuracies = [w["accuracy"] for w in windows]
    mean_acc = float(np.mean(accuracies))
    std_acc = float(np.std(accuracies)) if len(accuracies) > 1 else 0.0
    overall_acc = accuracy_score(all_actuals, all_predictions)

    predictions_df = pd.DataFrame({
        "date": all_dates,
        "actual": all_actuals,
        "predicted": all_predictions,
    })

    return {
        "symbol": symbol,
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "overall_accuracy": overall_acc,
        "window_accuracies": accuracies,
        "windows": windows,
        "predictions_df": predictions_df,
        "n_windows": len(windows),
    }
