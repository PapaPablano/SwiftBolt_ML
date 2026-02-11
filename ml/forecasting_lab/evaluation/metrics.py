"""
Metrics for Forecasting Lab: directional accuracy, MAE, MSE.

Self-contained; no production imports.
"""

import numpy as np
from typing import Any


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Fraction of steps where sign(actual change) == sign(predicted change).

    Uses first differences: direction_true = diff(y_true) > 0, direction_pred = diff(y_pred) > 0.
    """
    if len(y_true) < 2 or len(y_pred) < 2:
        return np.nan
    n = min(len(y_true), len(y_pred))
    y_t, y_p = np.asarray(y_true)[:n], np.asarray(y_pred)[:n]
    dir_true = np.diff(y_t) > 0
    dir_pred = np.diff(y_p) > 0
    return float(np.mean(dir_true == dir_pred))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute error."""
    y_t = np.asarray(y_true).ravel()
    y_p = np.asarray(y_pred).ravel()
    n = min(len(y_t), len(y_p))
    return float(np.mean(np.abs(y_t[:n] - y_p[:n])))


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean squared error."""
    y_t = np.asarray(y_true).ravel()
    y_p = np.asarray(y_pred).ravel()
    n = min(len(y_t), len(y_p))
    return float(np.mean((y_t[:n] - y_p[:n]) ** 2))


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metrics: list[str] | None = None,
) -> dict[str, float]:
    """
    Compute requested metrics. Default: directional_accuracy, mae, mse.

    Args:
        y_true: Actual values.
        y_pred: Predicted values.
        metrics: List of names: 'directional_accuracy', 'mae', 'mse'. None = all.

    Returns:
        Dict of metric name -> value.
    """
    metrics = metrics or ["directional_accuracy", "mae", "mse"]
    out: dict[str, float] = {}
    if "directional_accuracy" in metrics:
        out["directional_accuracy"] = directional_accuracy(y_true, y_pred)
    if "mae" in metrics:
        out["mae"] = mae(y_true, y_pred)
    if "mse" in metrics:
        out["mse"] = mse(y_true, y_pred)
    return out
