"""Lightweight XGBoost inference benchmark (baseline vs max_bin).

Usage:
  python src/scripts/xgboost_inference_benchmark.py \
    --rows 5000 --features 40
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass

import numpy as np
from xgboost import XGBClassifier


@dataclass
class BenchmarkResult:
    label: str
    fit_seconds: float
    predict_seconds: float


def build_model() -> XGBClassifier:
    """Build XGBoost model consistent with forecaster defaults."""
    tree_method = os.getenv("XGBOOST_TREE_METHOD")
    predictor = os.getenv("XGBOOST_PREDICTOR")
    try:
        n_jobs = int(os.getenv("XGBOOST_N_JOBS", "-1"))
    except Exception:
        n_jobs = -1

    max_bin = os.getenv("XGBOOST_MAX_BIN")
    try:
        max_bin_value = int(max_bin) if max_bin else None
    except Exception:
        max_bin_value = None

    params = {
        "tree_method": tree_method,
        "predictor": predictor,
        "max_bin": max_bin_value,
    }
    params = {k: v for k, v in params.items() if v}

    return XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        colsample_bylevel=0.8,
        min_child_weight=1,
        gamma=0,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="multi:softmax",
        num_class=3,
        eval_metric="mlogloss",
        verbosity=0,
        n_jobs=n_jobs,
        **params,
    )


def run_benchmark(label: str, X: np.ndarray, y: np.ndarray) -> BenchmarkResult:
    model = build_model()

    start_fit = time.perf_counter()
    model.fit(X, y)
    fit_seconds = time.perf_counter() - start_fit

    start_pred = time.perf_counter()
    _ = model.predict(X)
    predict_seconds = time.perf_counter() - start_pred

    return BenchmarkResult(label, fit_seconds, predict_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="XGBoost inference benchmark")
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--features", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    X = rng.normal(size=(args.rows, args.features)).astype(np.float32)
    y = rng.integers(0, 3, size=args.rows)

    os.environ.setdefault("XGBOOST_TREE_METHOD", "hist")
    os.environ.setdefault("XGBOOST_PREDICTOR", "cpu_predictor")

    baseline_max_bin = os.environ.pop("XGBOOST_MAX_BIN", None)

    baseline = run_benchmark("baseline", X, y)

    if baseline_max_bin is not None:
        os.environ["XGBOOST_MAX_BIN"] = baseline_max_bin
    else:
        os.environ["XGBOOST_MAX_BIN"] = "256"

    tuned = run_benchmark("max_bin=256", X, y)

    print("\nXGBoost benchmark results")
    for result in (baseline, tuned):
        print(
            f"{result.label}: fit={result.fit_seconds:.3f}s "
            f"predict={result.predict_seconds:.3f}s"
        )


if __name__ == "__main__":
    main()
