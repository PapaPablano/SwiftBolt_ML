#!/usr/bin/env python3
"""
Analyze Validation Results for Overfitting

Checks if model performs consistently across:
- Different sectors (Tech, Healthcare, Materials, etc.)
- Different volatility regimes (Low, Medium, High, Very High)
- Different stock types (Defensive, Growth, Cyclical)

Usage:
    python scripts/analyze_validation_diversity.py validation_results/validation_results_*.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Stock categorization
STOCK_CATEGORIES = {
    'PG': {'sector': 'Consumer Staples', 'volatility': 'Low', 'type': 'Defensive'},
    'KO': {'sector': 'Consumer Staples', 'volatility': 'Low', 'type': 'Defensive'},
    'JNJ': {'sector': 'Healthcare', 'volatility': 'Low', 'type': 'Defensive'},
    'MSFT': {'sector': 'Technology', 'volatility': 'Medium', 'type': 'Mega-cap'},
    'AAPL': {'sector': 'Technology', 'volatility': 'Medium', 'type': 'Mega-cap'},
    'AMGN': {'sector': 'Biotech', 'volatility': 'Medium', 'type': 'Growth'},
    'NVDA': {'sector': 'Technology', 'volatility': 'High', 'type': 'High Growth'},
    'MU': {'sector': 'Semiconductors', 'volatility': 'High', 'type': 'Cyclical'},
    'ALB': {'sector': 'Materials', 'volatility': 'Very High', 'type': 'Cyclical'},
    'SPY': {'sector': 'Index', 'volatility': 'Medium', 'type': 'Broad Market'},
}


def add_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Add sector/volatility/type columns to results."""
    df['sector'] = df['symbol'].map(lambda s: STOCK_CATEGORIES.get(s, {}).get('sector', 'Unknown'))
    df['volatility'] = df['symbol'].map(lambda s: STOCK_CATEGORIES.get(s, {}).get('volatility', 'Unknown'))
    df['stock_type'] = df['symbol'].map(lambda s: STOCK_CATEGORIES.get(s, {}).get('type', 'Unknown'))
    return df


def analyze_diversity(df: pd.DataFrame):
    """Analyze results for overfitting patterns."""
    print("\n" + "="*80)
    print("DIVERSIFIED VALIDATION ANALYSIS")
    print("="*80)
    
    # Overall stats
    print(f"\nOverall Performance:")
    print(f"  Total Predictions: {len(df)}")
    print(f"  Overall Accuracy: {df['correct'].mean():.1%}")
    print(f"  Symbols Tested: {df['symbol'].nunique()}")
    
    # Per-symbol accuracy (sorted by performance)
    print(f"\n" + "-"*80)
    print("Per-Symbol Accuracy:")
    print("-"*80)
    print(f"{'Symbol':<8} {'Sector':<20} {'Volatility':<12} {'Accuracy':<10} {'N':<6}")
    print("-"*80)
    
    for symbol in sorted(df['symbol'].unique()):
        symbol_df = df[df['symbol'] == symbol]
        category = STOCK_CATEGORIES.get(symbol, {})
        sector = category.get('sector', 'Unknown')
        volatility = category.get('volatility', 'Unknown')
        accuracy = symbol_df['correct'].mean()
        n = len(symbol_df)
        print(f"{symbol:<8} {sector:<20} {volatility:<12} {accuracy:>8.1%} {n:>6}")
    
    # Sector analysis
    print(f"\n" + "-"*80)
    print("Per-Sector Accuracy (Overfitting Check):")
    print("-"*80)
    
    sector_stats = df.groupby('sector').agg({
        'correct': ['mean', 'count'],
        'symbol': 'nunique',
    }).round(3)
    
    for sector in sorted(df['sector'].unique()):
        sector_df = df[df['sector'] == sector]
        accuracy = sector_df['correct'].mean()
        n = len(sector_df)
        n_symbols = sector_df['symbol'].nunique()
        print(f"  {sector:<20}: {accuracy:>6.1%} (n={n:>4}, symbols={n_symbols})")
    
    # Check if one sector dominates
    sector_accuracies = df.groupby('sector')['correct'].mean()
    if len(sector_accuracies) > 1:
        sector_range = sector_accuracies.max() - sector_accuracies.min()
        if sector_range > 0.20:
            print(f"\n  ⚠️  WARNING: >20% gap between best/worst sector suggests sector overfitting!")
            print(f"     Best: {sector_accuracies.idxmax()} ({sector_accuracies.max():.1%})")
            print(f"     Worst: {sector_accuracies.idxmin()} ({sector_accuracies.min():.1%})")
        else:
            print(f"\n  ✓ Sector performance is consistent (range={sector_range:.1%})")
    
    # Volatility analysis
    print(f"\n" + "-"*80)
    print("Per-Volatility Accuracy (Regime Check):")
    print("-"*80)
    
    vol_order = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}
    for vol in sorted(df['volatility'].unique(), key=lambda x: vol_order.get(x, 99)):
        vol_df = df[df['volatility'] == vol]
        accuracy = vol_df['correct'].mean()
        n = len(vol_df)
        n_symbols = vol_df['symbol'].nunique()
        print(f"  {vol:<12}: {accuracy:>6.1%} (n={n:>4}, symbols={n_symbols})")
    
    # Check if model only works in one volatility regime
    vol_accuracies = df.groupby('volatility')['correct'].mean()
    if len(vol_accuracies) > 1:
        vol_range = vol_accuracies.max() - vol_accuracies.min()
        if vol_range > 0.20:
            print(f"\n  ⚠️  WARNING: >20% gap between volatility regimes!")
            print(f"     Best: {vol_accuracies.idxmax()} ({vol_accuracies.max():.1%})")
            print(f"     Worst: {vol_accuracies.idxmin()} ({vol_accuracies.min():.1%})")
            print(f"     Model may only work in {vol_accuracies.idxmax().lower()} volatility environments")
        else:
            print(f"\n  ✓ Works across volatility regimes (range={vol_range:.1%})")
    
    # Stock type analysis
    print(f"\n" + "-"*80)
    print("Per-Type Accuracy:")
    print("-"*80)
    
    for stock_type in sorted(df['stock_type'].unique()):
        type_df = df[df['stock_type'] == stock_type]
        accuracy = type_df['correct'].mean()
        n = len(type_df)
        n_symbols = type_df['symbol'].nunique()
        print(f"  {stock_type:<15}: {accuracy:>6.1%} (n={n:>4}, symbols={n_symbols})")
    
    # Overfitting detection summary
    print(f"\n" + "="*80)
    print("OVERFITTING DETECTION SUMMARY")
    print("="*80)
    
    symbol_accuracies = df.groupby('symbol')['correct'].mean()
    symbol_std = symbol_accuracies.std()
    symbol_range = symbol_accuracies.max() - symbol_accuracies.min()
    
    print(f"\nAccuracy Statistics Across Symbols:")
    print(f"  Mean: {symbol_accuracies.mean():.1%}")
    print(f"  Std Dev: {symbol_std:.1%}")
    print(f"  Range: {symbol_accuracies.min():.1%} - {symbol_accuracies.max():.1%} (gap={symbol_range:.1%})")
    
    print(f"\nOverfitting Risk Assessment:")
    if symbol_std > 0.15:
        print(f"  ❌ HIGH RISK: Std dev > 15% suggests model overfits to specific stocks")
        print(f"     Action: Investigate top performers, check for data leakage")
    elif symbol_std > 0.10:
        print(f"  ⚠️  MODERATE RISK: Std dev > 10% shows some stock-specific patterns")
        print(f"     Action: Monitor performance gaps, consider ensemble reweighting")
    else:
        print(f"  ✓ LOW RISK: Consistent performance across diverse stocks (std={symbol_std:.1%})")
        print(f"     Action: Model generalizes well, safe to deploy")
    
    if symbol_range > 0.25:
        print(f"\n  ❌ WARNING: >25% gap between best/worst stock!")
        print(f"     Best: {symbol_accuracies.idxmax()} ({symbol_accuracies.max():.1%})")
        print(f"     Worst: {symbol_accuracies.idxmin()} ({symbol_accuracies.min():.1%})")
        print(f"     Risk: Model may be cherry-picking easy stocks")
    
    print(f"\n" + "="*80)
    
    # Recommendations
    print(f"\nDEPLOYMENT RECOMMENDATION:")
    print("="*80)
    
    overall_acc = df['correct'].mean()
    
    if overall_acc < 0.50:
        print(f"  ❌ DO NOT DEPLOY (accuracy {overall_acc:.1%} < 50%)")
        print(f"     Model is worse than random - check for bugs")
    elif overall_acc < 0.55:
        print(f"  ⚠️  DEPLOY WITH CAUTION (accuracy {overall_acc:.1%})")
        print(f"     Marginally better than random - use conservative position sizing")
    elif symbol_std > 0.15 or symbol_range > 0.25:
        print(f"  ⚠️  DEPLOY WITH CAUTION (accuracy {overall_acc:.1%} but high variance)")
        print(f"     Model works but may overfit to specific stocks/sectors")
        print(f"     Action: Use only on stocks similar to best performers")
    else:
        print(f"  ✓ READY TO DEPLOY (accuracy {overall_acc:.1%}, low variance)")
        print(f"     Model generalizes well across diverse stocks")
        print(f"     Proceed with canary deployment or production rollout")
    
    print(f"\n" + "="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze validation results for overfitting'
    )
    parser.add_argument(
        'results_file',
        help='Path to validation_results_*.csv file'
    )
    
    args = parser.parse_args()
    
    results_file = Path(args.results_file)
    if not results_file.exists():
        print(f"Error: File not found: {results_file}")
        sys.exit(1)
    
    # Load results
    df = pd.read_csv(results_file)
    
    # Add categories
    df = add_categories(df)
    
    # Analyze
    analyze_diversity(df)


if __name__ == '__main__':
    main()
