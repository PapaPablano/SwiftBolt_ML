#!/usr/bin/env python3
"""
Compare validation predictions vs actuals for a specific symbol and horizon.

Use this after blind validation to reconcile diagnostic (in-sample) vs
validation (out-of-sample) and spot systematic issues (e.g. 5D always wrong).

Usage:
    cd /Users/ericpeterson/SwiftBolt_ML/ml
    python scripts/compare_validation_by_symbol_horizon.py
    python scripts/compare_validation_by_symbol_horizon.py --symbol NVDA --horizon 5D
    python scripts/compare_validation_by_symbol_horizon.py --csv validation_results/diversified/validation_results_20260204_013028.csv
"""

import argparse
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser(description="Compare validation by symbol/horizon")
    ap.add_argument("--csv", default=None, help="Path to validation_results_*.csv (default: latest)")
    ap.add_argument("--symbol", default="AAPL", help="Symbol to filter")
    ap.add_argument("--horizon", default="5D", help="Horizon to filter (1D, 5D, 10D, 20D)")
    args = ap.parse_args()

    if args.csv and Path(args.csv).exists():
        csv_path = Path(args.csv)
    else:
        for d in ["validation_results/diversified", "validation_results"]:
            dir_path = Path(d)
            if dir_path.exists():
                files = sorted(dir_path.glob("validation_results_*.csv"))
                if files:
                    csv_path = files[-1]
                    break
        else:
            print("No validation_results_*.csv found.")
            return 1
        if not args.csv:
            csv_path = Path(csv_path)

    df = pd.read_csv(csv_path)
    if "correct" not in df.columns:
        print("CSV missing 'correct' column.")
        return 1

    sub = df[(df["symbol"] == args.symbol) & (df["horizon"] == args.horizon)].copy()
    if sub.empty:
        print(f"No rows for {args.symbol} {args.horizon} in {csv_path.name}")
        return 0

    sub["test_date"] = pd.to_datetime(sub["test_date"]).dt.strftime("%Y-%m-%d")
    if "actual_return" in sub.columns:
        sub["actual_return_pct"] = (sub["actual_return"].astype(float) * 100).round(2)

    print("=" * 80)
    print(f"VALIDATION COMPARISON: {args.symbol} {args.horizon}")
    print("=" * 80)
    print(f"CSV: {csv_path}")
    print(f"N:  {len(sub)}  |  Correct: {sub['correct'].sum()}  |  Accuracy: {sub['correct'].mean():.1%}")
    print()
    cols = ["test_date", "actual_label", "predicted_label", "correct"]
    if "actual_return_pct" in sub.columns:
        cols.insert(3, "actual_return_pct")
    print(sub[cols].to_string(index=False))
    print()

    # Pattern check
    pred_counts = sub["predicted_label"].value_counts()
    actual_counts = sub["actual_label"].value_counts()
    print("Predicted distribution:", pred_counts.to_dict())
    print("Actual distribution:  ", actual_counts.to_dict())
    if sub["correct"].sum() == 0 and len(sub) >= 5:
        print("\n⚠️  0% correct on this slice – check for systematic inversion or horizon bug.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
