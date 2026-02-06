#!/usr/bin/env python3
"""
Test fixed symmetric thresholds vs adaptive thresholds

Hypothesis: Adaptive percentile thresholds are creating bearish bias.
Test: Does using fixed symmetric ±2% thresholds reduce bias?
"""

import pandas as pd
import numpy as np
from pathlib import Path

print("="*80)
print("TESTING FIXED vs ADAPTIVE THRESHOLDS")
print("="*80)

# Load validation results
results_files = sorted(Path('validation_results/diversified').glob('validation_results_*.csv'))
if not results_files:
    print("No results found")
    exit(1)

latest_file = results_files[-1]
df = pd.read_csv(latest_file)

print(f"\nUsing: {latest_file.name}")
print(f"Total predictions: {len(df)}")

# Current (ADAPTIVE) accuracy
print("\n" + "="*80)
print("CURRENT (ADAPTIVE PERCENTILE) THRESHOLDS")
print("="*80)
print(f"Overall accuracy: {df['correct'].mean():.1%}")
print(f"Predicted distribution:")
for label, pct in df['predicted_label'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")
print(f"Actual distribution:")
for label, pct in df['actual_label'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")

# Test FIXED ±2% thresholds
print("\n" + "="*80)
print("TEST 1: FIXED ±2% SYMMETRIC THRESHOLDS")
print("="*80)

df['actual_label_fixed_2pct'] = df['actual_return'].apply(
    lambda r: 'bullish' if r > 0.02 else ('bearish' if r < -0.02 else 'neutral')
)

df['correct_fixed_2pct'] = (df['predicted_label'] == df['actual_label_fixed_2pct']).astype(int)
accuracy_fixed_2pct = df['correct_fixed_2pct'].mean()

print(f"Accuracy with fixed ±2%: {accuracy_fixed_2pct:.1%}")
print(f"Improvement: {accuracy_fixed_2pct - df['correct'].mean():+.1%}")

print(f"\nActual distribution (fixed ±2%):")
for label, pct in df['actual_label_fixed_2pct'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")

# Test FIXED ±1% thresholds
print("\n" + "="*80)
print("TEST 2: FIXED ±1% SYMMETRIC THRESHOLDS")
print("="*80)

df['actual_label_fixed_1pct'] = df['actual_return'].apply(
    lambda r: 'bullish' if r > 0.01 else ('bearish' if r < -0.01 else 'neutral')
)

df['correct_fixed_1pct'] = (df['predicted_label'] == df['actual_label_fixed_1pct']).astype(int)
accuracy_fixed_1pct = df['correct_fixed_1pct'].mean()

print(f"Accuracy with fixed ±1%: {accuracy_fixed_1pct:.1%}")
print(f"Improvement: {accuracy_fixed_1pct - df['correct'].mean():+.1%}")

print(f"\nActual distribution (fixed ±1%):")
for label, pct in df['actual_label_fixed_1pct'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")

# Test WIDER ±3% thresholds
print("\n" + "="*80)
print("TEST 3: FIXED ±3% SYMMETRIC THRESHOLDS")
print("="*80)

df['actual_label_fixed_3pct'] = df['actual_return'].apply(
    lambda r: 'bullish' if r > 0.03 else ('bearish' if r < -0.03 else 'neutral')
)

df['correct_fixed_3pct'] = (df['predicted_label'] == df['actual_label_fixed_3pct']).astype(int)
accuracy_fixed_3pct = df['correct_fixed_3pct'].mean()

print(f"Accuracy with fixed ±3%: {accuracy_fixed_3pct:.1%}")
print(f"Improvement: {accuracy_fixed_3pct - df['correct'].mean():+.1%}")

print(f"\nActual distribution (fixed ±3%):")
for label, pct in df['actual_label_fixed_3pct'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")

# Test BINARY (up vs down, no neutral)
print("\n" + "="*80)
print("TEST 4: BINARY CLASSIFICATION (Up vs Down, No Neutral)")
print("="*80)

# Adapt predictions to binary
df['predicted_binary'] = df['predicted_label'].map({
    'bullish': 'up',
    'bearish': 'down',
    'neutral': 'down'  # Default neutral to down
})

df['actual_binary'] = df['actual_return'].apply(
    lambda r: 'up' if r >= 0 else 'down'
)

df['correct_binary'] = (df['predicted_binary'] == df['actual_binary']).astype(int)
accuracy_binary = df['correct_binary'].mean()

print(f"Accuracy (binary, neutral→down): {accuracy_binary:.1%}")
print(f"Improvement: {accuracy_binary - df['correct'].mean():+.1%}")

print(f"\nActual distribution (binary):")
for label, pct in df['actual_binary'].value_counts(normalize=True).items():
    print(f"  {label}: {pct:.1%}")

# Try neutral→up
df['predicted_binary_up'] = df['predicted_label'].map({
    'bullish': 'up',
    'bearish': 'down',
    'neutral': 'up'  # Default neutral to up
})

df['correct_binary_up'] = (df['predicted_binary_up'] == df['actual_binary']).astype(int)
accuracy_binary_up = df['correct_binary_up'].mean()

print(f"\nBinary (neutral→up): {accuracy_binary_up:.1%}")
print(f"Improvement: {accuracy_binary_up - df['correct'].mean():+.1%}")

# Summary
print("\n" + "="*80)
print("SUMMARY: BEST THRESHOLD CONFIGURATION")
print("="*80)

results = [
    ('Current (Adaptive ±0.3-2.5%)', df['correct'].mean()),
    ('Fixed ±1%', accuracy_fixed_1pct),
    ('Fixed ±2%', accuracy_fixed_2pct),
    ('Fixed ±3%', accuracy_fixed_3pct),
    ('Binary (neutral→down)', accuracy_binary),
    ('Binary (neutral→up)', accuracy_binary_up),
]

results_sorted = sorted(results, key=lambda x: x[1], reverse=True)

print("\nRanked by accuracy:\n")
for i, (name, acc) in enumerate(results_sorted, 1):
    improvement = acc - df['correct'].mean()
    status = '✓' if acc > 0.40 else '⚠️' if acc > 0.35 else '✗'
    print(f"{i}. {name:35s} {acc:>6.1%} {improvement:+6.1%} {status}")

best_name, best_acc = results_sorted[0]

print(f"\n" + "="*80)
print(f"RECOMMENDATION")
print("="*80)

if best_acc > 0.50:
    print(f"\n✓ FOUND GOOD THRESHOLD!")
    print(f"  {best_name}: {best_acc:.1%}")
    print(f"\n  ACTION: Update validation script to use {best_name}")
    print(f"  Then re-run validation to confirm.")
elif best_acc > 0.40:
    print(f"\n⚠️  Marginal improvement")
    print(f"  {best_name}: {best_acc:.1%}")
    print(f"\n  This suggests thresholds aren't the main issue.")
    print(f"  Problem is likely features don't predict returns.")
else:
    print(f"\n✗ No threshold helps")
    print(f"  Best: {best_name}: {best_acc:.1%}")
    print(f"\n  CONCLUSION: Model is fundamentally not learning.")
    print(f"  Features likely have no predictive power.")

print("\n" + "="*80 + "\n")
