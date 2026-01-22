#!/usr/bin/env python
"""Diagnostic script to analyze label distributions and recommend optimal thresholds.

Usage:
    python -m src.training.diagnose_threshold --symbol SPY --timeframe d1
    python -m src.training.diagnose_threshold --symbol NVDA --timeframe d1 --plot
"""

import argparse
import logging
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.data.supabase_db import SupabaseDatabase
from src.training.data_preparation import collect_training_data

logger = logging.getLogger(__name__)


def analyze_price_movements(
    df: pd.DataFrame,
    horizon_bars: int = 5,
) -> pd.DataFrame:
    """
    Analyze actual price movements for different horizons.
    
    Args:
        df: OHLCV DataFrame
        horizon_bars: Bars ahead to calculate returns
    
    Returns:
        DataFrame with movement statistics
    """
    future_close = df["close"].shift(-horizon_bars)
    returns = (future_close - df["close"]) / df["close"]
    
    # Remove last N bars where we don't have future data
    returns = returns.iloc[:-horizon_bars].dropna()
    
    stats = {
        "count": len(returns),
        "mean": returns.mean(),
        "std": returns.std(),
        "min": returns.min(),
        "max": returns.max(),
        "median": returns.median(),
        "q25": returns.quantile(0.25),
        "q75": returns.quantile(0.75),
    }
    
    # Distribution percentiles
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        stats[f"p{p}"] = returns.quantile(p / 100)
    
    return pd.Series(stats), returns


def test_threshold(
    returns: pd.Series,
    threshold: float,
) -> Dict[str, int]:
    """
    Test a threshold and return label distribution.
    
    Args:
        returns: Series of future returns
        threshold: Threshold for BULLISH/BEARISH classification
    
    Returns:
        Dict with label counts
    """
    bullish = (returns > threshold).sum()
    bearish = (returns < -threshold).sum()
    neutral = len(returns) - bullish - bearish
    
    total = len(returns)
    
    return {
        "threshold": threshold,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "bullish_pct": bullish / total * 100,
        "bearish_pct": bearish / total * 100,
        "neutral_pct": neutral / total * 100,
        "non_neutral_pct": (bullish + bearish) / total * 100,
        "balance_score": min(bullish, bearish) / max(bullish, bearish, 1),  # 1.0 = perfect balance
    }


def recommend_threshold(
    returns: pd.Series,
    target_neutral_pct: float = 40.0,
    min_samples_per_class: int = 30,
) -> Tuple[float, Dict]:
    """
    Recommend optimal threshold based on data distribution.
    
    Args:
        returns: Series of future returns
        target_neutral_pct: Target percentage for NEUTRAL class (default 40%)
        min_samples_per_class: Minimum samples needed per class
    
    Returns:
        (recommended_threshold, stats_dict)
    """
    # Test range of thresholds
    test_thresholds = np.arange(0.001, 0.030, 0.001)  # 0.1% to 3%
    
    results = []
    for thresh in test_thresholds:
        stats = test_threshold(returns, thresh)
        results.append(stats)
    
    results_df = pd.DataFrame(results)
    
    # Find threshold closest to target neutral percentage
    results_df["neutral_diff"] = abs(results_df["neutral_pct"] - target_neutral_pct)
    
    # Filter for minimum samples per class
    valid_results = results_df[
        (results_df["bullish_count"] >= min_samples_per_class) &
        (results_df["bearish_count"] >= min_samples_per_class)
    ]
    
    if valid_results.empty:
        logger.warning(
            f"No threshold meets minimum samples requirement ({min_samples_per_class}). "
            f"Using best balance instead."
        )
        # Find threshold with best balance score
        best_idx = results_df["balance_score"].idxmax()
        recommended = results_df.loc[best_idx]
    else:
        # Find threshold closest to target neutral percentage
        best_idx = valid_results["neutral_diff"].idxmin()
        recommended = valid_results.loc[best_idx]
    
    return recommended["threshold"], recommended.to_dict()


def plot_distribution(
    returns: pd.Series,
    current_threshold: float,
    recommended_threshold: float,
    symbol: str,
    timeframe: str,
):
    """
    Plot return distribution with threshold overlays.
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Histogram of returns
    ax1 = axes[0]
    ax1.hist(returns * 100, bins=50, alpha=0.7, edgecolor='black')
    ax1.axvline(current_threshold * 100, color='red', linestyle='--', 
                linewidth=2, label=f'Current ({current_threshold*100:.1f}%)')
    ax1.axvline(-current_threshold * 100, color='red', linestyle='--', linewidth=2)
    ax1.axvline(recommended_threshold * 100, color='green', linestyle='-', 
                linewidth=2, label=f'Recommended ({recommended_threshold*100:.1f}%)')
    ax1.axvline(-recommended_threshold * 100, color='green', linestyle='-', linewidth=2)
    ax1.set_xlabel('Return (%)')
    ax1.set_ylabel('Frequency')
    ax1.set_title(f'{symbol} {timeframe.upper()} - Return Distribution (5 bars ahead)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Label distribution comparison
    ax2 = axes[1]
    
    current_stats = test_threshold(returns, current_threshold)
    recommended_stats = test_threshold(returns, recommended_threshold)
    
    x = np.arange(3)
    width = 0.35
    
    current_pcts = [
        current_stats['bearish_pct'],
        current_stats['neutral_pct'],
        current_stats['bullish_pct'],
    ]
    recommended_pcts = [
        recommended_stats['bearish_pct'],
        recommended_stats['neutral_pct'],
        recommended_stats['bullish_pct'],
    ]
    
    ax2.bar(x - width/2, current_pcts, width, label='Current', alpha=0.7)
    ax2.bar(x + width/2, recommended_pcts, width, label='Recommended', alpha=0.7)
    
    ax2.set_xlabel('Label')
    ax2.set_ylabel('Percentage (%)')
    ax2.set_title('Label Distribution Comparison')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['BEARISH', 'NEUTRAL', 'BULLISH'])
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add percentage labels on bars
    for i, (curr, rec) in enumerate(zip(current_pcts, recommended_pcts)):
        ax2.text(i - width/2, curr + 1, f'{curr:.1f}%', ha='center', va='bottom', fontsize=9)
        ax2.text(i + width/2, rec + 1, f'{rec:.1f}%', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(f'threshold_analysis_{symbol}_{timeframe}.png', dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: threshold_analysis_{symbol}_{timeframe}.png")
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Analyze label distributions and recommend optimal thresholds'
    )
    parser.add_argument('--symbol', type=str, required=True, help='Stock symbol (e.g., SPY)')
    parser.add_argument('--timeframe', type=str, required=True, help='Timeframe (e.g., d1, h1)')
    parser.add_argument('--horizon', type=int, default=5, help='Bars ahead to predict (default: 5)')
    parser.add_argument('--bars', type=int, default=500, help='Number of bars to analyze (default: 500)')
    parser.add_argument('--current-threshold', type=float, default=0.015, help='Current threshold (default: 0.015)')
    parser.add_argument('--plot', action='store_true', help='Generate plots')
    parser.add_argument('--target-neutral', type=float, default=40.0, help='Target neutral percentage (default: 40)')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print(f"Threshold Diagnostic for {args.symbol} {args.timeframe.upper()}")
    print("=" * 80)
    
    # Collect data
    print(f"\nCollecting {args.bars} bars of data...")
    db = SupabaseDatabase()
    data_map = collect_training_data(
        db=db,
        symbols=[args.symbol],
        timeframes={args.timeframe: args.bars},
        lookback_days=365,
    )
    
    if args.timeframe not in data_map or args.symbol not in data_map[args.timeframe]:
        print(f"\n❌ No data found for {args.symbol}/{args.timeframe}")
        return 1
    
    df = data_map[args.timeframe][args.symbol]
    print(f"✅ Loaded {len(df)} bars")
    
    # Analyze movements
    print(f"\nAnalyzing {args.horizon}-bar ahead returns...")
    stats, returns = analyze_price_movements(df, horizon_bars=args.horizon)
    
    print("\n" + "=" * 80)
    print("PRICE MOVEMENT STATISTICS")
    print("=" * 80)
    print(f"Sample count:    {stats['count']:.0f}")
    print(f"Mean return:     {stats['mean']*100:+.3f}%")
    print(f"Std deviation:   {stats['std']*100:.3f}%")
    print(f"Min return:      {stats['min']*100:+.3f}%")
    print(f"Max return:      {stats['max']*100:+.3f}%")
    print(f"Median return:   {stats['median']*100:+.3f}%")
    print(f"\nPercentiles:")
    print(f"  1st:  {stats['p1']*100:+.3f}%")
    print(f"  5th:  {stats['p5']*100:+.3f}%")
    print(f"  25th: {stats['p25']*100:+.3f}%")
    print(f"  50th: {stats['p50']*100:+.3f}%")
    print(f"  75th: {stats['p75']*100:+.3f}%")
    print(f"  95th: {stats['p95']*100:+.3f}%")
    print(f"  99th: {stats['p99']*100:+.3f}%")
    
    # Test current threshold
    print("\n" + "=" * 80)
    print(f"CURRENT THRESHOLD: {args.current_threshold*100:.2f}%")
    print("=" * 80)
    current_stats = test_threshold(returns, args.current_threshold)
    print(f"BEARISH:  {current_stats['bearish_count']:4d} samples ({current_stats['bearish_pct']:.1f}%)")
    print(f"NEUTRAL:  {current_stats['neutral_count']:4d} samples ({current_stats['neutral_pct']:.1f}%)")
    print(f"BULLISH:  {current_stats['bullish_count']:4d} samples ({current_stats['bullish_pct']:.1f}%)")
    print(f"\nNon-neutral: {current_stats['non_neutral_pct']:.1f}%")
    print(f"Balance score: {current_stats['balance_score']:.3f} (1.0 = perfect)")
    
    # Recommend optimal threshold
    print("\n" + "=" * 80)
    print("RECOMMENDED THRESHOLD")
    print("=" * 80)
    recommended_threshold, rec_stats = recommend_threshold(
        returns, 
        target_neutral_pct=args.target_neutral,
        min_samples_per_class=30,
    )
    print(f"Optimal threshold: {recommended_threshold*100:.2f}%")
    print(f"\nLabel distribution:")
    print(f"BEARISH:  {rec_stats['bearish_count']:.0f} samples ({rec_stats['bearish_pct']:.1f}%)")
    print(f"NEUTRAL:  {rec_stats['neutral_count']:.0f} samples ({rec_stats['neutral_pct']:.1f}%)")
    print(f"BULLISH:  {rec_stats['bullish_count']:.0f} samples ({rec_stats['bullish_pct']:.1f}%)")
    print(f"\nNon-neutral: {rec_stats['non_neutral_pct']:.1f}%")
    print(f"Balance score: {rec_stats['balance_score']:.3f}")
    
    # Configuration recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDED CONFIGURATION")
    print("=" * 80)
    print(f"Update ensemble_training_job.py:")
    print(f"""\n'{args.timeframe}': {{"bars": {args.bars}, "horizon": {args.horizon}, "threshold": {recommended_threshold:.4f}}},""")
    
    # Quick comparison table
    print("\n" + "=" * 80)
    print("COMPARISON TABLE")
    print("=" * 80)
    comparison_thresholds = [0.005, 0.008, 0.010, 0.012, 0.015, 0.020, recommended_threshold]
    comparison_thresholds = sorted(set(comparison_thresholds))
    
    print(f"{'Threshold':>10} | {'Bearish':>8} | {'Neutral':>8} | {'Bullish':>8} | {'Non-Neutral':>12} | {'Balance':>8}")
    print("-" * 80)
    
    for thresh in comparison_thresholds:
        stats = test_threshold(returns, thresh)
        marker = " ← Recommended" if abs(thresh - recommended_threshold) < 0.0001 else ""
        marker = " ← Current" if abs(thresh - args.current_threshold) < 0.0001 else marker
        print(
            f"{thresh*100:9.2f}% | "
            f"{stats['bearish_pct']:7.1f}% | "
            f"{stats['neutral_pct']:7.1f}% | "
            f"{stats['bullish_pct']:7.1f}% | "
            f"{stats['non_neutral_pct']:11.1f}% | "
            f"{stats['balance_score']:7.3f}{marker}"
        )
    
    # Generate plots if requested
    if args.plot:
        print("\nGenerating plots...")
        plot_distribution(
            returns,
            args.current_threshold,
            recommended_threshold,
            args.symbol,
            args.timeframe,
        )
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
