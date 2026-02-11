#!/usr/bin/env python3
"""
Enhanced XGBoost tuning with directional loss function.

This script implements custom directional loss for better direction prediction
and includes the enhanced feature engineering for directional accuracy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Sequence

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import make_scorer, mean_absolute_error, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit


def directional_loss(y_pred, y_true):
    """Penalize incorrect direction more than magnitude error."""
    # Convert to numpy arrays if needed
    y_pred = np.array(y_pred)
    y_true = np.array(y_true)
    
    # Calculate direction changes
    pred_direction = np.sign(np.diff(y_pred))
    true_direction = np.sign(np.diff(y_true))
    
    # Direction penalty: 5x penalty for wrong direction
    direction_match = (pred_direction == true_direction)
    penalty = np.where(direction_match, 1.0, 5.0)
    
    # Apply penalty to squared errors
    errors = y_pred[1:] - y_true[1:]  # Skip first element due to diff
    weighted_errors = penalty * (errors ** 2)
    
    return np.mean(weighted_errors)


def directional_accuracy_scorer(y_true, y_pred):
    """Scorer for directional accuracy (higher is better)."""
    y_pred = np.array(y_pred)
    y_true = np.array(y_true)
    
    if len(y_pred) < 2 or len(y_true) < 2:
        return 0.0
    
    pred_direction = np.sign(np.diff(y_pred))
    true_direction = np.sign(np.diff(y_true))
    
    correct = np.sum(pred_direction == true_direction)
    total = len(pred_direction)
    
    return (correct / total) * 100 if total > 0 else 0.0


def create_directional_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add features specifically for direction prediction."""
    features = pd.DataFrame(index=df.index)
    
    # KDJ crossover signals
    if 'kdj_j' in df.columns and 'kdj_d' in df.columns:
        features['kdj_j_above_d'] = (df['kdj_j'] > df['kdj_d']).astype(int)
        features['kdj_j_cross_d_up'] = (
            (df['kdj_j'] > df['kdj_d']) & 
            (df['kdj_j'].shift(1) <= df['kdj_d'].shift(1))
        ).astype(int)
        features['kdj_j_cross_d_down'] = (
            (df['kdj_j'] < df['kdj_d']) & 
            (df['kdj_j'].shift(1) >= df['kdj_d'].shift(1))
        ).astype(int)
    
    # MACD momentum
    if 'macd' in df.columns:
        features['macd_positive'] = (df['macd'] > 0).astype(int)
        features['macd_acceleration'] = df['macd'].diff()
        features['macd_cross_signal'] = (
            (df['macd'] > df['macd_signal']) & 
            (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        ).astype(int) if 'macd_signal' in df.columns else 0
    
    # Price momentum clusters
    if 'ma_20' in df.columns:
        features['price_above_ma20'] = (df['close'] > df['ma_20']).astype(int)
    if 'ma_5' in df.columns and 'ma_20' in df.columns:
        features['ma_5_above_ma_20'] = (df['ma_5'] > df['ma_20']).astype(int)
        features['ma_crossover'] = (
            (df['ma_5'] > df['ma_20']) & 
            (df['ma_5'].shift(1) <= df['ma_20'].shift(1))
        ).astype(int)
    
    # Volatility regime features
    vol_5 = df['close'].pct_change().rolling(5).std()
    vol_20 = df['close'].pct_change().rolling(20).std()
    features['high_volatility'] = (vol_5 > 1.5 * vol_20).astype(int)
    features['vol_ratio'] = vol_5 / vol_20
    
    # Price change features
    features['price_change_1'] = df['close'].pct_change(1)
    features['price_change_5'] = df['close'].pct_change(5)
    features['price_change_10'] = df['close'].pct_change(10)
    
    # Volume features (if available)
    if 'volume' in df.columns:
        features['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        features['volume_spike'] = (df['volume'] > 2 * df['volume'].rolling(20).mean()).astype(int)
    
    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune XGBoost with directional loss.")
    parser.add_argument(
        "data",
        type=Path,
        help="Path to a CSV or Parquet file containing engineered features.",
    )
    parser.add_argument(
        "--target-col",
        default="target",
        help="Name of the target column (default: target).",
    )
    parser.add_argument(
        "--timestamp-col",
        default="timestamp",
        help="Name of the timestamp column used for chronological sorting (default: timestamp).",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of TimeSeriesSplit folds (default: 5).",
    )
    parser.add_argument(
        "--test-fraction",
        type=float,
        default=0.2,
        help="Fraction of the most recent samples reserved for hold-out evaluation (default: 0.2).",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("xgboost_directional_model.pkl"),
        help="Destination for the fitted model artefact (default: xgboost_directional_model.pkl).",
    )
    parser.add_argument(
        "--use-directional-loss",
        action="store_true",
        help="Use custom directional loss function instead of standard regression.",
    )
    return parser.parse_args()


def load_dataset(path: Path, timestamp_col: str, target_col: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)

    if timestamp_col not in frame or target_col not in frame:
        missing = {timestamp_col, target_col} - set(frame.columns)
        raise ValueError(f"Data file missing required columns: {sorted(missing)}")

    frame = frame.copy()
    frame[timestamp_col] = pd.to_datetime(frame[timestamp_col], errors="coerce")
    frame = frame.dropna(subset=[timestamp_col, target_col])
    frame = frame.sort_values(timestamp_col)
    return frame


def select_features(frame: pd.DataFrame, target_col: str, timestamp_col: str) -> List[str]:
    numeric_cols = frame.select_dtypes(include=["number"]).columns.tolist()
    candidate_features = [col for col in numeric_cols if col not in {target_col, timestamp_col}]
    if not candidate_features:
        raise ValueError("No numeric feature columns available for tuning")
    return candidate_features


def prepare_matrices(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    target_col: str,
) -> tuple[pd.DataFrame, pd.Series]:
    data = frame.dropna(subset=[*feature_cols, target_col])
    X = data.loc[:, feature_cols].astype(float)
    y = data[target_col].astype(float)
    if len(X) <= 10:
        raise ValueError("Dataset too small for tuning; need more than 10 samples")
    return X, y


def compute_holdout_metrics(
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    
    # Directional accuracy
    directional_acc = directional_accuracy_scorer(y_true, y_pred)
    
    with np.errstate(divide="ignore", invalid="ignore"):
        mape_series = np.abs((y_true - y_pred) / y_true)
    mape_series = mape_series.replace([np.inf, -np.inf], np.nan).dropna()
    mape = float(mape_series.mean() * 100.0) if not mape_series.empty else float("nan")
    
    return {
        "mae": mae, 
        "rmse": rmse, 
        "mape": mape,
        "directional_accuracy": directional_acc
    }


def main() -> None:
    args = parse_args()

    frame = load_dataset(args.data, args.timestamp_col, args.target_col)
    
    # Add directional features
    print("Adding directional features...")
    directional_features = create_directional_features(frame)
    frame = pd.concat([frame, directional_features], axis=1)
    
    feature_cols = select_features(frame, args.target_col, args.timestamp_col)
    X, y = prepare_matrices(frame, feature_cols, args.target_col)

    if len(X) <= args.n_splits:
        raise ValueError(
            "Dataset too small for the requested number of splits; "
            "reduce --n-splits or augment the dataset."
        )

    # Choose scoring metric
    if args.use_directional_loss:
        scorer = make_scorer(directional_accuracy_scorer, greater_is_better=True)
        objective = "reg:squarederror"  # XGBoost doesn't support custom objectives directly
        print("Using directional accuracy as scoring metric")
    else:
        scorer = make_scorer(mean_absolute_error, greater_is_better=False)
        objective = "reg:squarederror"
        print("Using MAE as scoring metric")
    
    tscv = TimeSeriesSplit(n_splits=args.n_splits)

    print("PHASE 1: Coarse Grid Search")
    print("=" * 80)

    coarse_grid = {
        "learning_rate": [0.01, 0.05, 0.1, 0.2],
        "max_depth": [3, 5, 7, 9],
        "n_estimators": [100, 200, 300],
        "min_child_weight": [1, 3],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }

    base_model = xgb.XGBRegressor(
        objective=objective,
        random_state=42,
        n_jobs=-1,
    )

    grid_search_coarse = GridSearchCV(
        estimator=base_model,
        param_grid=coarse_grid,
        scoring=scorer,
        cv=tscv,
        verbose=2,
        n_jobs=-1,
        return_train_score=False,
    )

    grid_search_coarse.fit(X, y)
    best_params_coarse = grid_search_coarse.best_params_
    best_score_coarse = grid_search_coarse.best_score_

    print(f"Best coarse CV score: {best_score_coarse:.4f}")
    print(f"Best coarse params: {json.dumps(best_params_coarse, indent=2)}")

    print("\nPHASE 2: Fine-Tuning")
    print("=" * 80)

    # Fine-tuning grid
    fine_grid = {
        "learning_rate": [0.01, 0.05, 0.1, 0.15, 0.2],
        "max_depth": [3, 4, 5, 6, 7, 8, 9],
        "n_estimators": [100, 150, 200, 250, 300],
        "min_child_weight": [1, 2, 3, 4, 5],
        "gamma": [0.0, 0.1, 0.2, 0.3],
        "reg_alpha": [0.0, 0.01, 0.1, 0.5],
        "reg_lambda": [1.0, 1.5, 2.0, 2.5],
    }

    fine_model = xgb.XGBRegressor(
        objective=objective,
        random_state=42,
        n_jobs=-1,
        **{k: v for k, v in best_params_coarse.items() if k not in fine_grid}
    )

    grid_search_fine = GridSearchCV(
        estimator=fine_model,
        param_grid=fine_grid,
        scoring=scorer,
        cv=tscv,
        verbose=2,
        n_jobs=-1,
        return_train_score=False,
    )

    grid_search_fine.fit(X, y)
    best_params_fine = grid_search_fine.best_params_
    best_score_fine = grid_search_fine.best_score_

    print(f"Best fine-tuned CV score: {best_score_fine:.4f}")
    print(f"Best fine-tuned params: {json.dumps(best_params_fine, indent=2)}")

    print("\nPHASE 3: Final Validation")
    print("=" * 80)

    final_params = {**best_params_fine, **{k: v for k, v in best_params_coarse.items() if k not in best_params_fine}}
    final_model = xgb.XGBRegressor(
        objective=objective,
        random_state=42,
        n_jobs=-1,
        **final_params,
    )

    test_size = int(len(X) * args.test_fraction)
    if test_size < max(1, len(X) // 10):
        print("Warning: hold-out set is small; consider increasing --test-fraction.")

    split_index = len(X) - test_size
    split_index = max(args.n_splits + 1, split_index)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    final_model.fit(X_train, y_train)
    y_pred = final_model.predict(X_test)
    holdout_metrics = compute_holdout_metrics(y_test, y_pred)

    print("Hold-out metrics:")
    print(f"MAE:  {holdout_metrics['mae']:.4f}")
    print(f"RMSE: {holdout_metrics['rmse']:.4f}")
    print(f"Directional Accuracy: {holdout_metrics['directional_accuracy']:.2f}%")
    if not np.isnan(holdout_metrics["mape"]):
        print(f"MAPE: {holdout_metrics['mape']:.2f}%")
    else:
        print("MAPE: unavailable (targets contain zeros)")

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, args.model_output)
    print(f"Tuned model saved to: {args.model_output}")

    # Persist final params for downstream scripts
    with open("best_directional_params.json", "w", encoding="utf-8") as handle:
        json.dump({
            "params": final_params, 
            "metrics": holdout_metrics,
            "feature_columns": feature_cols
        }, handle, indent=2)


if __name__ == "__main__":
    main()
