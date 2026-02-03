#!/usr/bin/env python3
"""
Visualize walk-forward validation results.

Usage:
  python ml/analyze_walk_forward.py                    # run TSLA walk-forward and plot
  python ml/analyze_walk_forward.py --symbol NVDA      # run NVDA and plot
  python ml/analyze_walk_forward.py --no-tabpfn        # use Baseline (RF) instead of TabPFN
"""

import argparse
import sys
from pathlib import Path

# Add ml to path so we can run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))


def plot_walk_forward_results(result: dict, out_path: str | Path | None = None) -> None:
    """
    Visualize walk-forward validation results: accuracy by window,
    cumulative accuracy over time, overall confusion matrix, accuracy distribution.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 1. Accuracy by window
    ax1 = axes[0, 0]
    accs = result["window_accuracies"]
    windows = range(1, len(accs) + 1)
    ax1.plot(windows, accs, marker="o", linewidth=2)
    ax1.axhline(
        result["mean_accuracy"],
        color="red",
        linestyle="--",
        label=f"Mean: {result['mean_accuracy']:.1%}",
    )
    ax1.axhline(0.333, color="gray", linestyle=":", label="Random (33.3%)")
    ax1.set_xlabel("Window")
    ax1.set_ylabel("Accuracy")
    ax1.set_title("Accuracy by Test Window")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Cumulative accuracy over time
    ax2 = axes[0, 1]
    predictions_df = result["predictions_df"]
    predictions_df = predictions_df.copy()
    predictions_df["correct"] = predictions_df["actual"] == predictions_df["predicted"]
    predictions_df["cumulative_acc"] = predictions_df["correct"].expanding().mean()
    ax2.plot(predictions_df["date"], predictions_df["cumulative_acc"])
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Cumulative Accuracy")
    ax2.set_title("Accuracy Over Time (Expanding)")
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis="x", rotation=45)

    # 3. Confusion matrix (overall)
    ax3 = axes[1, 0]
    from sklearn.metrics import confusion_matrix

    labels_order = ["bearish", "neutral", "bullish"]
    cm = confusion_matrix(
        predictions_df["actual"],
        predictions_df["predicted"],
        labels=labels_order,
    )
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        ax=ax3,
        xticklabels=["Bearish", "Neutral", "Bullish"],
        yticklabels=["Bearish", "Neutral", "Bullish"],
    )
    ax3.set_xlabel("Predicted")
    ax3.set_ylabel("Actual")
    ax3.set_title("Overall Confusion Matrix")

    # 4. Accuracy distribution
    ax4 = axes[1, 1]
    ax4.hist(accs, bins=10, edgecolor="black", alpha=0.7)
    ax4.axvline(
        result["mean_accuracy"],
        color="red",
        linestyle="--",
        label=f"Mean: {result['mean_accuracy']:.1%}",
    )
    ax4.set_xlabel("Accuracy")
    ax4.set_ylabel("Frequency")
    ax4.set_title("Distribution of Window Accuracies")
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    if out_path is None:
        out_path = Path(__file__).resolve().parent / f"walk_forward_{result['symbol']}.png"
    out_path = Path(out_path)
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Plot saved: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run walk-forward validation and plot results"
    )
    parser.add_argument(
        "--symbol",
        default="TSLA",
        help="Symbol to run walk-forward on (default: TSLA)",
    )
    parser.add_argument(
        "--no-tabpfn",
        action="store_true",
        help="Use Baseline (Random Forest) instead of TabPFN",
    )
    parser.add_argument(
        "--initial-train-days",
        type=int,
        default=200,
        help="Initial training window size (default: 200)",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=50,
        help="Test period size per window (default: 50)",
    )
    parser.add_argument(
        "--step-days",
        type=int,
        default=50,
        help="Step between windows (default: 50)",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip generating plot",
    )
    parser.add_argument(
        "--binary-mode",
        action="store_true",
        help="Binary classification (bullish vs bearish only); random baseline 50%%",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.005,
        help="Min |return| for binary mode (default: 0.005)",
    )
    parser.add_argument(
        "--with-regime",
        action="store_true",
        help="Add regime features (SPY, VIX, sector) for market context",
    )
    args = parser.parse_args()

    from src.evaluation.walk_forward import walk_forward_validate

    mode = "binary (bullish/bearish)" if args.binary_mode else "3-class"
    print(f"Running walk-forward validation for {args.symbol} (TabPFN={not args.no_tabpfn}, mode={mode})...")
    result = walk_forward_validate(
        symbol=args.symbol,
        timeframe="d1",
        horizon_days=1,
        initial_train_days=args.initial_train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        use_tabpfn=not args.no_tabpfn,
        binary_mode=args.binary_mode,
        threshold_pct=args.threshold,
        add_regime=args.with_regime,
    )

    baseline = "50.0%" if args.binary_mode else "33.3%"
    print(f"\nWalk-Forward Results for {result['symbol']}:")
    print(f"  Mean accuracy: {result['mean_accuracy']:.1%}")
    print(f"  Std deviation: {result['std_accuracy']:.1%}")
    print(f"  Overall accuracy: {result['overall_accuracy']:.1%}")
    print(f"  Random baseline: {baseline}")
    print(f"  Windows tested: {result['n_windows']}")
    print("\nPer-window accuracies:")
    for i, acc in enumerate(result["window_accuracies"], 1):
        print(f"  Window {i}: {acc:.1%}")

    if not args.no_plot:
        plot_walk_forward_results(result)


if __name__ == "__main__":
    main()
