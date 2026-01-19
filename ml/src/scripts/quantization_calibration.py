"""Lightweight PTQ calibration helper (no new deps).

Usage:
  python src/scripts/quantization_calibration.py --input npy --output npz

The input .npy should contain a 2D numpy array of features used for inference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def calibrate_min_max(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute per-feature min/max ranges for PTQ."""
    if features.ndim != 2:
        raise ValueError("Expected 2D feature array [n_samples, n_features]")
    min_vals = features.min(axis=0)
    max_vals = features.max(axis=0)
    return min_vals, max_vals


def quantize_weights(
    weights: np.ndarray,
    min_vals: np.ndarray,
    max_vals: np.ndarray,
    num_bits: int = 8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simple per-feature symmetric quantization."""
    if weights.ndim != 2:
        raise ValueError("Expected 2D weight array [n_features, n_outputs]")

    if min_vals.shape[0] != weights.shape[0]:
        raise ValueError("min_vals must match weight feature dimension")

    if max_vals.shape[0] != weights.shape[0]:
        raise ValueError("max_vals must match weight feature dimension")

    qmin = -(2 ** (num_bits - 1))
    qmax = 2 ** (num_bits - 1) - 1

    scales = np.maximum(np.abs(min_vals), np.abs(max_vals)) / qmax
    scales = np.where(scales == 0, 1.0, scales)

    zero_points = np.zeros_like(scales)
    scaled = (weights.T / scales).T
    quantized = np.clip(np.round(scaled), qmin, qmax).astype(np.int8)

    return quantized, scales, zero_points


def main() -> None:
    parser = argparse.ArgumentParser(description="PTQ calibration helper")
    parser.add_argument("--input", required=True, help="Path to .npy features")
    parser.add_argument(
        "--output",
        required=True,
        help="Output .npz file for min/max calibration",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    features = np.load(input_path)
    min_vals, max_vals = calibrate_min_max(features)

    np.savez(
        output_path,
        min_vals=min_vals,
        max_vals=max_vals,
    )
    print(f"Saved calibration stats to {output_path}")


if __name__ == "__main__":
    main()
