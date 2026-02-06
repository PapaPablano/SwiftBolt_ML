#!/usr/bin/env python3
"""Quick check of latest validation results."""

import json
import sys
from pathlib import Path
import pandas as pd
import glob

# Find latest validation files
results_dir = Path('validation_results/diversified')
if not results_dir.exists():
    results_dir = Path('validation_results')

report_files = sorted(results_dir.glob('validation_report_*.json'))
result_files = sorted(results_dir.glob('validation_results_*.csv'))

if not report_files:
    print("❌ No validation report files found!")
    sys.exit(1)

latest_report = report_files[-1]
latest_results = result_files[-1] if result_files else None

print("="*80)
print("VALIDATION RESULTS ANALYSIS")
print("="*80)
print(f"\nReport file: {latest_report.name}")
print(f"Results file: {latest_results.name if latest_results else 'Not found'}")

# Load report
with open(latest_report) as f:
    report = json.load(f)

# Overall metrics
print("\n" + "="*80)
print("OVERALL PERFORMANCE")
print("="*80)
accuracy = report.get('overall_accuracy', 0)
print(f"Total Predictions: {report.get('total_predictions', 0)}")
print(f"Overall Accuracy: {accuracy:.1%}")

if accuracy < 0.45:
    print("\n❌ CRITICAL: Accuracy < 45% - Model is not working")
    status = "FAIL"
elif accuracy < 0.50:
    print("\n⚠️  WARNING: Accuracy < 50% - Below random")
    status = "POOR"
elif accuracy < 0.55:
    print("\n⚠️  MARGINAL: Accuracy 50-55% - Barely better than random")
    status = "MARGINAL"
elif accuracy < 0.60:
    print("\n✅ GOOD: Accuracy 55-60% - Ready for cautious deployment")
    status = "GOOD"
else:
    print("\n🎉 EXCELLENT: Accuracy >60% - Strong model performance")
    status = "EXCELLENT"

# Per-symbol breakdown
print("\n" + "="*80)
print("PER-SYMBOL ACCURACY")
print("="*80)
print(f"{'Symbol':<8} {'Accuracy':<12} {'N':<8} {'Status'}")
print("-"*80)

by_symbol = report.get('by_symbol', {})
for symbol, metrics in sorted(by_symbol.items(), key=lambda x: x[1]['accuracy'], reverse=True):
    acc = metrics['accuracy']
    n = metrics['n_predictions']
    
    if acc >= 0.55:
        symbol_status = "✅ Good"
    elif acc >= 0.50:
        symbol_status = "⚠️  Marginal"
    else:
        symbol_status = "❌ Poor"
    
    print(f"{symbol:<8} {acc:>10.1%} {n:>8} {symbol_status}")

# Per-horizon breakdown
print("\n" + "="*80)
print("PER-HORIZON ACCURACY")
print("="*80)
print(f"{'Horizon':<10} {'Accuracy':<12} {'N':<8}")
print("-"*80)

by_horizon = report.get('by_horizon', {})
for horizon, metrics in sorted(by_horizon.items()):
    acc = metrics['accuracy']
    n = metrics['n_predictions']
    print(f"{horizon:<10} {acc:>10.1%} {n:>8}")

# Confidence calibration
if 'confidence_calibration' in report:
    print("\n" + "="*80)
    print("CONFIDENCE CALIBRATION")
    print("="*80)
    print(f"{'Confidence':<15} {'Accuracy':<12} {'N':<8}")
    print("-"*80)
    
    for bucket, metrics in report['confidence_calibration'].items():
        if metrics['n'] > 0:
            acc = metrics['accuracy']
            n = metrics['n']
            print(f"{bucket:<15} {acc:>10.1%} {n:>8}")

# Check for threshold improvements (if CSV available)
if latest_results and latest_results.exists():
    print("\n" + "="*80)
    print("THRESHOLD ANALYSIS")
    print("="*80)
    
    df = pd.read_csv(latest_results)
    
    if 'bearish_threshold' in df.columns and 'bullish_threshold' in df.columns:
        print("\n✅ Adaptive thresholds are being used!\n")
        
        print("Threshold ranges by symbol:")
        print(f"{'Symbol':<8} {'Bearish Range':<25} {'Bullish Range':<25}")
        print("-"*80)
        
        for symbol in sorted(df['symbol'].unique()):
            symbol_df = df[df['symbol'] == symbol]
            bear_min = symbol_df['bearish_threshold'].min()
            bear_max = symbol_df['bearish_threshold'].max()
            bull_min = symbol_df['bullish_threshold'].min()
            bull_max = symbol_df['bullish_threshold'].max()
            
            print(f"{symbol:<8} [{bear_min:>7.4f} to {bear_max:>7.4f}]   [{bull_min:>7.4f} to {bull_max:>7.4f}]")
        
        # Check if thresholds vary (good sign)
        threshold_variance = df.groupby('symbol')['bullish_threshold'].mean().std()
        if threshold_variance > 0.005:
            print("\n✅ Thresholds vary by symbol (good - adapting to volatility)")
        else:
            print("\n⚠️  Thresholds are similar across symbols (may not be adapting properly)")
    else:
        print("\n❌ WARNING: Threshold columns not found - fix may not have been applied!")

# Deployment recommendation
print("\n" + "="*80)
print("DEPLOYMENT RECOMMENDATION")
print("="*80)

if status == "EXCELLENT" or status == "GOOD":
    print("\n✅ READY TO DEPLOY")
    print("\nNext steps:")
    print("  1. Document these results")
    print("  2. Run shadow deployment (optional)")
    print("  3. Deploy to production with monitoring")
    print("  4. Set up alerts for accuracy < 50%")
elif status == "MARGINAL":
    print("\n⚠️  DEPLOY WITH CAUTION")
    print("\nRecommendations:")
    print("  1. Use conservative position sizing")
    print("  2. Only trade high-confidence predictions (>0.7)")
    print("  3. Monitor closely for first week")
    print("  4. Consider additional feature engineering")
else:
    print("\n❌ DO NOT DEPLOY")
    print("\nRecommended actions:")
    print("  1. Investigate feature quality")
    print("  2. Check for data leakage or bugs")
    print("  3. Consider simpler baseline")
    print("  4. Verify thresholds are being applied correctly")

print("\n" + "="*80)
print(f"\nFull report: {latest_report}")
if latest_results:
    print(f"Full results: {latest_results}")
print("\n" + "="*80 + "\n")
