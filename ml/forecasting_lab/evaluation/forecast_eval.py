"""
Forecast evaluation: per-step errors and directional accuracy by horizon.

Used to extend results JSON with forecast_eval and residual features for the next run.
"""

import numpy as np


def forecast_eval_from_fold(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    horizon: int | None = None,
    y_prev: float | None = None,
) -> dict:
    """
    Compute per-step errors and directional accuracy by step for one fold.

    Multi-step directional accuracy is anchored to the last observed close (y_prev):
    step i is correct if sign(y_true[i] - y_prev) == sign(y_pred[i] - y_prev).
    This avoids horizon-internal-only direction and matches typical use (did we go up/down from last known?).

    Args:
        y_true: Actual values (length >= 1).
        y_pred: Predicted values (same length or longer; truncated to horizon).
        horizon: Optional; if set, truncate to this length.
        y_prev: Last observed close (e.g. last train close). If None, uses y_true[0] as anchor.

    Returns:
        Dict with: per_step_mae, per_step_mse, directional_accuracy_by_step (anchored to y_prev),
        directional_accuracy (mean over steps), and optionally directional_accuracy_within_horizon.
    """
    y_t = np.asarray(y_true).ravel()
    y_p = np.asarray(y_pred).ravel()
    n = min(len(y_t), len(y_p))
    if horizon is not None:
        n = min(n, horizon)
    if n == 0:
        return {
            "per_step_mae": [],
            "per_step_mse": [],
            "directional_accuracy_by_step": [],
            "directional_accuracy": float("nan"),
            "directional_accuracy_within_horizon": float("nan"),
        }
    y_t, y_p = y_t[:n], y_p[:n]
    anchor = float(y_prev) if y_prev is not None else float(y_t[0])

    per_step_mae = [float(np.abs(y_t[i] - y_p[i])) for i in range(n)]
    per_step_mse = [float((y_t[i] - y_p[i]) ** 2) for i in range(n)]

    # Primary: directional per step anchored to last observed close (y_prev)
    dir_by_step = []
    for i in range(n):
        dt = y_t[i] - anchor
        dp = y_p[i] - anchor
        dir_by_step.append(1.0 if (np.sign(dt) == np.sign(dp)) else 0.0)
    dir_acc = float(np.mean(dir_by_step)) if dir_by_step else float("nan")

    # Optional: within-horizon direction (step-to-step)
    dir_within = []
    for i in range(1, n):
        dt = y_t[i] - y_t[i - 1]
        dp = y_p[i] - y_p[i - 1]
        dir_within.append(1.0 if (np.sign(dt) == np.sign(dp)) else 0.0)
    dir_within_acc = float(np.mean(dir_within)) if dir_within else float("nan")

    return {
        "per_step_mae": per_step_mae,
        "per_step_mse": per_step_mse,
        "directional_accuracy_by_step": dir_by_step,
        "directional_accuracy": dir_acc,
        "directional_accuracy_within_horizon": dir_within_acc,
    }


def residual_features_from_fold(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    last_k: int = 5,
) -> dict:
    """
    Build residual features for the next run: last_k residuals (actual - predicted).

    Args:
        y_true: Actual values.
        y_pred: Predicted values.
        last_k: Number of trailing residuals to keep.

    Returns:
        Dict with: last_residuals (list of length <= last_k), residual_mean, residual_std.
    """
    y_t = np.asarray(y_true).ravel()
    y_p = np.asarray(y_pred).ravel()
    n = min(len(y_t), len(y_p))
    if n == 0:
        return {"last_residuals": [], "residual_mean": float("nan"), "residual_std": float("nan")}
    res = (y_t[:n] - y_p[:n]).tolist()
    last_residuals = res[-last_k:] if len(res) >= last_k else res
    return {
        "last_residuals": [float(r) for r in last_residuals],
        "residual_mean": float(np.mean(res)),
        "residual_std": float(np.std(res)) if len(res) > 1 else 0.0,
    }


def aggregate_forecast_eval(fold_evals: list[dict], horizon: int) -> dict:
    """
    Aggregate forecast_eval across folds: mean per-step MAE/MSE, mean directional by step.
    directional_accuracy_by_step is now per-step (anchored to y_prev), so length = n.
    """
    if not fold_evals:
        return {
            "per_step_mae": [],
            "per_step_mse": [],
            "directional_accuracy_by_step": [],
            "directional_accuracy": float("nan"),
            "directional_accuracy_within_horizon": float("nan"),
        }
    max_len = max(len(e.get("per_step_mae", [])) for e in fold_evals)
    max_len = min(max_len, horizon)
    per_step_mae = []
    per_step_mse = []
    dir_by_step = []
    for step in range(max_len):
        mae_vals = [e["per_step_mae"][step] for e in fold_evals if step < len(e.get("per_step_mae", []))]
        mse_vals = [e["per_step_mse"][step] for e in fold_evals if step < len(e.get("per_step_mse", []))]
        dir_vals = [e["directional_accuracy_by_step"][step] for e in fold_evals if step < len(e.get("directional_accuracy_by_step", []))]
        per_step_mae.append(float(np.mean(mae_vals)) if mae_vals else float("nan"))
        per_step_mse.append(float(np.mean(mse_vals)) if mse_vals else float("nan"))
        dir_by_step.append(float(np.mean(dir_vals)) if dir_vals else float("nan"))
    dir_overall = [e.get("directional_accuracy") for e in fold_evals if not np.isnan(e.get("directional_accuracy", float("nan")))]
    dir_within_overall = [e.get("directional_accuracy_within_horizon") for e in fold_evals if "directional_accuracy_within_horizon" in e and not np.isnan(e.get("directional_accuracy_within_horizon", float("nan")))]
    return {
        "per_step_mae": per_step_mae,
        "per_step_mse": per_step_mse,
        "directional_accuracy_by_step": dir_by_step,
        "directional_accuracy": float(np.mean(dir_overall)) if dir_overall else float("nan"),
        "directional_accuracy_within_horizon": float(np.mean(dir_within_overall)) if dir_within_overall else float("nan"),
    }
