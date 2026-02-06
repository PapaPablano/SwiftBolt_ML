#!/usr/bin/env python3
"""
Debug Why Model Gets Exactly 33% (Random for 3-Class)

Runs 4 critical tests:
1. Check prediction vs actual distribution
2. Test if "always predict neutral" baseline beats model
3. Test if inverting predictions (bullish<->bearish) improves accuracy
4. Analyze confidence calibration
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# No imports needed - we're just analyzing CSV results

print("="*80)
print("MODEL 33% ACCURACY DEBUGGER")
print("="*80)

# Load validation results
results_files = sorted(Path('validation_results/diversified').glob('validation_results_*.csv'))
if not results_files:
    print("\n❌ No validation results found!")
    sys.exit(1)

latest_file = results_files[-1]
print(f"\nAnalyzing: {latest_file.name}")

df = pd.read_csv(latest_file)

print(f"Total predictions: {len(df)}")
print(f"Overall accuracy: {df['correct'].mean():.1%}")

# Test 1: Prediction vs Actual Distribution
print("\n" + "="*80)
print("TEST 1: PREDICTION vs ACTUAL DISTRIBUTION")
print("="*80)

print("\nPredicted label distribution:")
pred_dist = df['predicted_label'].value_counts(normalize=True)
for label, pct in pred_dist.items():
    print(f"  {label:8s}: {pct:>6.1%}")

print("\nActual label distribution:")
actual_dist = df['actual_label'].value_counts(normalize=True)
for label, pct in actual_dist.items():
    print(f"  {label:8s}: {pct:>6.1%}")

# Check if distributions match
dist_diff = abs(pred_dist - actual_dist).max()
if dist_diff > 0.15:
    print(f"\n⚠️  WARNING: Distribution mismatch > 15% (max diff: {dist_diff:.1%})")
    print("   Model may be learning class priors, not patterns.")
else:
    print(f"\n✓ Distributions match reasonably (max diff: {dist_diff:.1%})")

# Test 2: "Always Predict Neutral" Baseline
print("\n" + "="*80)
print("TEST 2: TRIVIAL BASELINE (Always Predict Neutral)")
print("="*80)

neutral_pct = actual_dist.get('neutral', 0)
print(f"\nIf we always predict 'neutral':")
print(f"  Expected accuracy: {neutral_pct:.1%}")
print(f"  Model accuracy: {df['correct'].mean():.1%}")
print(f"  Difference: {df['correct'].mean() - neutral_pct:+.1%}")

if df['correct'].mean() < neutral_pct:
    print("\n❌ CRITICAL: Model is WORSE than always predicting neutral!")
    print("   This suggests the model is actively harmful.")
elif df['correct'].mean() < neutral_pct + 0.05:
    print("\n⚠️  Model barely beats trivial baseline (+<5%)")
    print("   Model has learned almost nothing useful.")
else:
    print(f"\n✓ Model beats trivial baseline by {df['correct'].mean() - neutral_pct:.1%}")

# Test 3: Inverted Predictions
print("\n" + "="*80)
print("TEST 3: INVERTED PREDICTIONS (Flip Bullish ↔ Bearish)")
print("="*80)

df['predicted_inverted'] = df['predicted_label'].map({
    'bullish': 'bearish',
    'bearish': 'bullish',
    'neutral': 'neutral'
})

df['correct_inverted'] = (df['predicted_inverted'] == df['actual_label']).astype(int)
inverted_accuracy = df['correct_inverted'].mean()

print(f"\nOriginal accuracy: {df['correct'].mean():.1%}")
print(f"Inverted accuracy: {inverted_accuracy:.1%}")
print(f"Difference: {inverted_accuracy - df['correct'].mean():+.1%}")

if inverted_accuracy > 0.45:
    print("\n❌ CRITICAL: Inverted predictions are better!")
    print("   Model has learned the OPPOSITE of what we want.")
    print("   Check for sign errors in labels or features.")
elif inverted_accuracy > df['correct'].mean() + 0.05:
    print("\n⚠️  Inverted is better by >5%")
    print("   Model may have subtle sign inversion bug.")
else:
    print("\n✓ Inverting doesn't help - not a sign inversion issue.")

# Test 4: Confusion Matrix
print("\n" + "="*80)
print("TEST 4: CONFUSION MATRIX")
print("="*80)

confusion = pd.crosstab(
    df['actual_label'],
    df['predicted_label'],
    normalize='index'
)

print("\nRows=Actual, Cols=Predicted (% of each actual class):")
print(confusion.round(3))

print("\nDiagonal values (correct predictions):")
for label in confusion.index:
    if label in confusion.columns:
        acc = confusion.loc[label, label]
        print(f"  {label:8s}: {acc:.1%}")

# Check if one class dominates
for label in confusion.index:
    row = confusion.loc[label]
    max_pred = row.idxmax()
    max_val = row.max()
    
    if max_pred != label and max_val > 0.5:
        print(f"\n⚠️  When actual is {label}, model predicts {max_pred} {max_val:.1%} of time")

# Test 5: Confidence Analysis
print("\n" + "="*80)
print("TEST 5: CONFIDENCE CALIBRATION")
print("="*80)

if 'predicted_confidence' in df.columns:
    print("\nAccuracy by confidence bucket:")
    
    buckets = [
        ('Very High (>=0.9)', 0.9, 1.0),
        ('High (0.7-0.9)', 0.7, 0.9),
        ('Medium (0.5-0.7)', 0.5, 0.7),
        ('Low (0.3-0.5)', 0.3, 0.5),
        ('Very Low (<0.3)', 0.0, 0.3),
    ]
    
    for name, low, high in buckets:
        bucket_df = df[(df['predicted_confidence'] >= low) & (df['predicted_confidence'] < high)]
        if len(bucket_df) > 0:
            acc = bucket_df['correct'].mean()
            n = len(bucket_df)
            print(f"  {name:20s}: {acc:>6.1%} (n={n:>4})")
    
    # Calculate correlation between confidence and correctness
    from scipy.stats import pointbiserialr
    corr, pval = pointbiserialr(df['correct'], df['predicted_confidence'])
    
    print(f"\nCorrelation (confidence vs correctness): {corr:.4f} (p={pval:.4f})")
    
    if abs(corr) < 0.05:
        print("\n❌ CRITICAL: Confidence has NO correlation with accuracy!")
        print("   Model's confidence scores are meaningless.")
    elif corr < 0:
        print("\n⚠️  NEGATIVE correlation: Higher confidence = WORSE accuracy!")
        print("   Model is miscalibrated in the wrong direction.")
    else:
        print(f"\n✓ Positive correlation: {corr:.3f}")

# Test 6: Per-Symbol Performance
print("\n" + "="*80)
print("TEST 6: PER-SYMBOL VARIANCE")
print("="*80)

print("\nAccuracy by symbol:")
symbol_accs = []
for symbol in sorted(df['symbol'].unique()):
    symbol_df = df[df['symbol'] == symbol]
    acc = symbol_df['correct'].mean()
    n = len(symbol_df)
    symbol_accs.append(acc)
    print(f"  {symbol:6s}: {acc:>6.1%} (n={n:>4})")

std_dev = np.std(symbol_accs)
max_range = max(symbol_accs) - min(symbol_accs)

print(f"\nVariance across symbols:")
print(f"  Std dev: {std_dev:.1%}")
print(f"  Range: {min(symbol_accs):.1%} to {max(symbol_accs):.1%} (gap={max_range:.1%})")

if std_dev < 0.03:
    print("\n⚠️  Very low variance across symbols (<3%)")
    print("   Model performs identically everywhere = learning nothing stock-specific.")

# Test 7: Sample Actual Predictions
print("\n" + "="*80)
print("TEST 7: SAMPLE PREDICTIONS")
print("="*80)

print("\nRandom sample of 10 predictions:")
print(f"{'Symbol':<8} {'Date':<12} {'Horizon':<8} {'Actual':<10} {'Predicted':<10} {'Return':<10} {'Match'}")
print("-"*80)

sample = df.sample(min(10, len(df)), random_state=42)
for _, row in sample.iterrows():
    match = '✓' if row['correct'] else '✗'
    print(f"{row['symbol']:<8} {str(row['test_date'])[:10]:<12} {row['horizon']:<8} "
          f"{row['actual_label']:<10} {row['predicted_label']:<10} "
          f"{row['actual_return']:>8.2%}  {match}")

# Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)

issues_found = []

if df['correct'].mean() < neutral_pct:
    issues_found.append("❌ Model is worse than 'always neutral' baseline")

if inverted_accuracy > 0.45:
    issues_found.append("❌ Inverted predictions work better (sign bug)")

if 'predicted_confidence' in df.columns:
    corr, _ = pointbiserialr(df['correct'], df['predicted_confidence'])
    if abs(corr) < 0.05:
        issues_found.append("❌ Confidence scores are uncorrelated with accuracy")

if dist_diff > 0.15:
    issues_found.append("⚠️  Prediction distribution doesn't match actual distribution")

if std_dev < 0.03:
    issues_found.append("⚠️  Performance is identical across all symbols")

if issues_found:
    print("\nCritical issues detected:")
    for issue in issues_found:
        print(f"  {issue}")
else:
    print("\n✓ No obvious issues in predictions detected.")
    print("  Problem is likely in feature quality or look-ahead bias.")

print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)

if inverted_accuracy > 0.45:
    print("\n1. CHECK FOR SIGN INVERSION:")
    print("   - Review label creation logic")
    print("   - Check if returns are inverted somewhere")
    print("   - Verify threshold comparisons (> vs <)")

if df['correct'].mean() < neutral_pct + 0.05:
    print("\n2. MODEL IS NOT LEARNING:")
    print("   - Run look-ahead bias checker: python scripts/check_lookahead_bias.py")
    print("   - Review feature engineering code")
    print("   - Try simpler features (only price-based indicators)")

if 'predicted_confidence' in df.columns and abs(corr) < 0.05:
    print("\n3. CONFIDENCE IS BROKEN:")
    print("   - Check confidence calculation in BaselineForecaster")
    print("   - Verify probability extraction from XGBoost")
    print("   - Consider disabling confidence-based filtering")

print("\n4. CHECK FOR LOOK-AHEAD BIAS:")
print("   Run: python scripts/check_lookahead_bias.py")

print("\n" + "="*80 + "\n")
