#!/usr/bin/env python3
"""
Compare Google Research TimesFM (time series foundation model) to our walk-forward
XGBoost/ARIMA on TSLA directional accuracy.

Requires the timesfm repo to be cloned and installed:

  cd /path/to/SwiftBolt_ML
  gh repo clone google-research/timesfm   # or: git clone https://github.com/google-research/timesfm.git
  cd timesfm && pip install -e ".[torch]" && cd ..
  cd ml && python compare_timesfm.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_PATH = Path(__file__).resolve().parent.parent / "timesfm"
SYMBOL = "TSLA"
CONTEXT_LEN = 512
HORIZON = 5
N_TEST_WINDOWS = 5  # number of walk-forward windows to evaluate


def main():
    print("=" * 60)
    print("TimesFM vs WALK-FORWARD COMPARISON (TSLA)")
    print("=" * 60)

    # --- Ensure timesfm is available ---
    if not REPO_PATH.is_dir():
        print(f"\nTimesFM repo not found at {REPO_PATH}")
        print("Clone it with:")
        print("  gh repo clone google-research/timesfm")
        print("  # or: git clone https://github.com/google-research/timesfm.git")
        sys.exit(1)

    sys.path.insert(0, str(REPO_PATH / "src"))
    try:
        import timesfm
        if not hasattr(timesfm, "TimesFM_2p5_200M_torch"):
            raise ImportError("TimesFM_2p5_200M_torch not available; install with: pip install -e \".[torch]\" from timesfm dir")
    except ImportError as e:
        print(f"\nTimesFM import failed: {e}")
        print("From repo root, run:  cd timesfm && pip install -e \".[torch]\"")
        sys.exit(1)

    # --- Load TSLA close (yfinance) ---
    print(f"\nLoading {SYMBOL} data (yfinance 5y)...")
    try:
        import yfinance as yf
        ticker = yf.Ticker(SYMBOL)
        hist = ticker.history(period="5y", interval="1d")
        if hist.empty or len(hist) < CONTEXT_LEN + HORIZON * (N_TEST_WINDOWS + 1):
            print("Insufficient data")
            sys.exit(1)
        close = hist["Close"].values.astype(np.float64)
    except Exception as e:
        print(f"Data load failed: {e}")
        sys.exit(1)

    # --- Load model and compile ---
    print("Loading TimesFM 2.5 200M (PyTorch)...")
    try:
        import torch
        torch.set_float32_matmul_precision("high")
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
        model.compile(
            timesfm.ForecastConfig(
                max_context=min(1024, CONTEXT_LEN),
                max_horizon=HORIZON,
                normalize_inputs=True,
                use_continuous_quantile_head=False,
            )
        )
    except Exception as e:
        print(f"Model load failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Walk-forward style evaluation: directional accuracy ---
    print(f"\nEvaluating {N_TEST_WINDOWS} test windows (context={CONTEXT_LEN}, horizon={HORIZON})...")
    correct = 0
    total = 0
    for w in range(N_TEST_WINDOWS):
        # Test window: from end backwards
        end_idx = len(close) - HORIZON * (w + 1)
        if end_idx < CONTEXT_LEN + HORIZON:
            break
        start_idx = end_idx - CONTEXT_LEN
        context = close[start_idx:end_idx]
        actual_next = close[end_idx : end_idx + HORIZON]
        try:
            point_forecast, _ = model.forecast(horizon=HORIZON, inputs=[context])
            pred = point_forecast[0]  # (horizon,)
        except Exception as e:
            print(f"  Window {w+1} forecast failed: {e}")
            continue
        last_price = context[-1]
        for h in range(HORIZON):
            pred_dir = 1 if pred[h] > last_price else (0 if pred[h] == last_price else -1)
            actual_dir = 1 if actual_next[h] > last_price else (0 if actual_next[h] == last_price else -1)
            if actual_dir != 0 and pred_dir == actual_dir:
                correct += 1
            if actual_dir != 0:
                total += 1
        # For next window, "last_price" for direction could be step-wise; here we use context[-1] for all 5 steps for simplicity
        if total >= 20:
            break

    timesfm_acc = correct / total if total > 0 else 0.0

    # --- Our walk-forward metrics (reference) ---
    our_xgboost_acc = 0.515
    our_arima_acc = 0.472

    # --- Print comparison ---
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    print("\n--- TimesFM 2.5 (Google Research, directional from point forecast) ---")
    print(f"  Directional accuracy: {timesfm_acc:.1%}  (n={total} steps)")
    print("\n--- Our walk-forward (Supabase TSLA 5d) ---")
    print(f"  XGBoost accuracy:     {our_xgboost_acc:.1%}")
    print(f"  ARIMA-GARCH accuracy: {our_arima_acc:.1%}")
    print("\n--- Note ---")
    print("  TimesFM: point forecast → sign(forecast - last) vs actual direction.")
    print("  Ours: binary classifier (bullish/bearish) in walk-forward windows.")
    print("  Run: python walk_forward_weekly.py TSLA --horizon 5 --threshold 0.02")
    print("=" * 60)


if __name__ == "__main__":
    main()
