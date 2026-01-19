"""PTQ accuracy check (baseline vs 8-bit input quantization).

Usage:
  python src/scripts/ptq_accuracy_check.py \
    --rows 5000 --features 40
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from xgboost import XGBClassifier


def build_model() -> XGBClassifier:
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
        n_jobs=-1,
    )


def quantize_inputs(
    X: np.ndarray,
    min_vals: np.ndarray,
    max_vals: np.ndarray,
    num_bits: int = 8,
) -> np.ndarray:
    qmin = -(2 ** (num_bits - 1))
    qmax = 2 ** (num_bits - 1) - 1

    scales = np.maximum(np.abs(min_vals), np.abs(max_vals)) / qmax
    scales = np.where(scales == 0, 1.0, scales)

    scaled = X / scales
    quantized = np.clip(np.round(scaled), qmin, qmax)
    dequantized = quantized * scales

    return dequantized.astype(np.float32)


def load_calibration(
    calibration_path: Path,
    X: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if calibration_path.is_file():
        data = np.load(calibration_path)
        return data["min_vals"], data["max_vals"]

    return X.min(axis=0), X.max(axis=0)


def load_policy(policy_path: Path) -> dict[str, float]:
    if not policy_path.is_file():
        return {}

    with policy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return {
        "max_change": float(data.get("max_change", 0.01)),
        "max_prob_delta": float(data.get("max_prob_delta", 0.005)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PTQ accuracy check")
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--features", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--calibration", type=str, default="")
    parser.add_argument(
        "--policy",
        type=str,
        default="ml/config/ptq_policy.json",
        help="Path to PTQ policy JSON",
    )
    parser.add_argument("--max-change", type=float, default=None)
    parser.add_argument("--max-prob-delta", type=float, default=None)
    args = parser.parse_args()

    policy = load_policy(Path(args.policy))
    max_change = args.max_change
    if max_change is None:
        max_change = policy.get("max_change", 0.01)

    max_prob_delta = args.max_prob_delta
    if max_prob_delta is None:
        max_prob_delta = policy.get("max_prob_delta", 0.005)

    rng = np.random.default_rng(args.seed)
    X = rng.normal(size=(args.rows, args.features)).astype(np.float32)
    y = rng.integers(0, 3, size=args.rows)

    calibration_path = Path(args.calibration) if args.calibration else Path()
    min_vals, max_vals = load_calibration(calibration_path, X)

    X_quant = quantize_inputs(X, min_vals, max_vals)

    model = build_model()
    model.fit(X, y)

    base_probs = model.predict_proba(X)
    base_preds = np.argmax(base_probs, axis=1)

    quant_probs = model.predict_proba(X_quant)
    quant_preds = np.argmax(quant_probs, axis=1)

    pred_changes = np.mean(base_preds != quant_preds)
    prob_delta = np.mean(np.abs(base_probs - quant_probs))

    print("PTQ accuracy check (input quantization)")
    print(f"prediction_change_rate={pred_changes:.4f}")
    print(f"mean_abs_prob_delta={prob_delta:.6f}")

    if pred_changes > max_change or prob_delta > max_prob_delta:
        print("PTQ_CHECK_FAILED: disable quantization")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
