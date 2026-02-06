#!/usr/bin/env python3
"""
Diagnose Model Performance Issues

Investigates why model accuracy is at random levels (33%).
Checks:
1. Label distribution (is dataset balanced?)
2. Feature quality (are features predictive?)
3. Training data size
4. Prediction distribution (is model just predicting one class?)
5. Look-ahead bias detection
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db
from src.models.baseline_forecaster import BaselineForecaster
from src.features.adaptive_thresholds import AdaptiveThresholds

print("="*80)
print("MODEL FAILURE DIAGNOSTIC")
print("="*80)

# Test on one symbol
SYMBOL = 'AAPL'
HORIZON_DAYS = 5

print(f"\nTesting on: {SYMBOL}")
print(f"Horizon: {HORIZON_DAYS}D\n")

# Load data
print("-"*80)
print("1. LOADING DATA")
print("-"*80)
df = db.fetch_ohlc_bars(SYMBOL, timeframe='d1', limit=1000)
df['ts'] = pd.to_datetime(df['ts'])
df = df.sort_values('ts').reset_index(drop=True)
print(f"Loaded {len(df)} bars from {df['ts'].min().date()} to {df['ts'].max().date()}")

# Prepare training data
print("\n" + "-"*80)
print("2. LABEL DISTRIBUTION")
print("-"*80)

model = BaselineForecaster()
X, y = model.prepare_training_data(df, horizon_days=HORIZON_DAYS)

print(f"\nTotal samples: {len(y)}")
print(f"\nLabel counts:")
label_counts = y.value_counts()
for label, count in label_counts.items():
    pct = count / len(y) * 100
    print(f"  {label:8s}: {count:4d} ({pct:5.1f}%)")

if len(label_counts) == 1:
    print("\n❌ CRITICAL: Only one label! Model cannot learn.")
    print("   Problem: Thresholds are too wide or too narrow.")
    sys.exit(1)

# Check for severe imbalance
min_pct = (label_counts.min() / len(y)) * 100
max_pct = (label_counts.max() / len(y)) * 100

if min_pct < 5:
    print(f"\n⚠️  WARNING: Severe class imbalance! Smallest class is {min_pct:.1f}%")
    print("   Model may struggle to learn minority classes.")
elif min_pct < 15:
    print(f"\n⚠️  Class imbalance: Smallest class is {min_pct:.1f}%")
else:
    print(f"\n✅ Balanced labels: {min_pct:.1f}% to {max_pct:.1f}%")

# Check thresholds
print("\n" + "-"*80)
print("3. THRESHOLD VALUES")
print("-"*80)

bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
    df, horizon_days=HORIZON_DAYS
)

print(f"Bearish threshold: {bearish_thresh:.4f} ({bearish_thresh*100:.2f}%)")
print(f"Bullish threshold: {bullish_thresh:.4f} ({bullish_thresh*100:.2f}%)")
print(f"Neutral range: {bearish_thresh:.4f} to {bullish_thresh:.4f}")

# Calculate actual returns distribution
returns = df['close'].pct_change(HORIZON_DAYS).shift(-HORIZON_DAYS)
returns_valid = returns.dropna()

print(f"\nActual returns distribution:")
print(f"  Mean: {returns_valid.mean():.4f}")
print(f"  Std: {returns_valid.std():.4f}")
print(f"  Min: {returns_valid.min():.4f}")
print(f"  25%: {returns_valid.quantile(0.25):.4f}")
print(f"  50%: {returns_valid.quantile(0.50):.4f}")
print(f"  75%: {returns_valid.quantile(0.75):.4f}")
print(f"  Max: {returns_valid.max():.4f}")

if abs(bullish_thresh) > returns_valid.std() * 3:
    print("\n⚠️  WARNING: Thresholds are very wide (>3 std devs)")
    print("   Most returns will be 'neutral', making problem trivial.")

# Train model
print("\n" + "-"*80)
print("4. TRAINING MODEL")
print("-"*80)

try:
    model.train(X, y, min_samples=50)
    print(f"\u2705 Model trained successfully")
    print(f"   Training samples: {len(X)}")
    print(f"   Features: {len(X.columns)}")
except Exception as e:
    print(f"\u274c Training failed: {e}")
    sys.exit(1)

# Check feature importance
if hasattr(model.model, 'feature_importances_'):
    print("\nTop 10 features by importance:")
    imp = model.model.feature_importances_
    cols = list(X.columns)
    # Align lengths (XGBoost can drop constant features)
    n = min(len(imp), len(cols))
    importances = pd.Series(imp[:n], index=cols[:n]).sort_values(ascending=False)
    
    for i, (feat, imp) in enumerate(importances.head(10).items(), 1):
        print(f"  {i:2d}. {feat:30s}: {imp:.4f}")
    
    # Check if any feature dominates
    top_feature_pct = importances.iloc[0] / importances.sum() * 100
    if top_feature_pct > 50:
        print(f"\n⚠️  WARNING: Top feature accounts for {top_feature_pct:.1f}% of importance")
        print("   Model may be overfitting to one feature.")

# Test predictions on training data
print("\n" + "-"*80)
print("5. PREDICTION DISTRIBUTION")
print("-"*80)

try:
    # Predict on the training data to see if model learned
    result = model.predict(df, horizon_days=HORIZON_DAYS)
    pred_label = result['label']
    pred_probs = result.get('probabilities', {})
    
    print(f"\nPrediction on latest bar:")
    print(f"  Label: {pred_label}")
    print(f"  Probabilities: {pred_probs}")
    
    # Check if probabilities are balanced or skewed
    if pred_probs:
        max_prob = max(pred_probs.values())
        if max_prob < 0.4:
            print(f"\n⚠️  Model is very uncertain (max prob={max_prob:.1%})")
        elif max_prob > 0.9:
            print(f"\n⚠️  Model is overconfident (max prob={max_prob:.1%})")
        else:
            print(f"\n✅ Model confidence looks reasonable (max prob={max_prob:.1%})")
    
except Exception as e:
    print(f"\u274c Prediction failed: {e}")
    import traceback
    traceback.print_exc()

# Check predictions on multiple samples
print("\n" + "-"*80)
print("6. SAMPLE PREDICTIONS (Last 10 bars)")
print("-"*80)

print(f"\n{'Date':<12} {'Actual Return':<15} {'Predicted':<12} {'Actual Label':<12} {'Match'}")
print("-"*80)

# Predict on last 10 bars
for i in range(max(0, len(df)-HORIZON_DAYS-10), len(df)-HORIZON_DAYS):
    if i < 50:  # Need minimum lookback
        continue
    
    # Get data up to this point
    train_subset = df.iloc[:i+1].copy()
    
    try:
        # Get actual return
        actual_return = (df.iloc[i+HORIZON_DAYS]['close'] - df.iloc[i]['close']) / df.iloc[i]['close']
        
        # Get predicted label
        result = model.predict(train_subset, horizon_days=HORIZON_DAYS)
        pred_label = result['label']
        
        # Get actual label
        if actual_return > bullish_thresh:
            actual_label = 'bullish'
        elif actual_return < bearish_thresh:
            actual_label = 'bearish'
        else:
            actual_label = 'neutral'
        
        match = '✅' if pred_label == actual_label else '❌'
        
        date_str = df.iloc[i]['ts'].strftime('%Y-%m-%d')
        print(f"{date_str:<12} {actual_return:>13.2%}  {pred_label:<12} {actual_label:<12} {match}")
        
    except Exception as e:
        continue

# Look-ahead bias check
print("\n" + "-"*80)
print("7. LOOK-AHEAD BIAS CHECK")
print("-"*80)

print("\nChecking if features contain future information...")

# Check if any features have suspiciously high correlation with target
from scipy.stats import pointbiserialr

# Convert labels to numeric
label_map = {'bearish': 0, 'neutral': 1, 'bullish': 2}
y_numeric = y.map(label_map)

print("\nTop 5 features by correlation with target:")
correlations = {}
for col in X.columns:
    try:
        if X[col].std() > 0:  # Skip constant columns
            corr, pval = pointbiserialr(y_numeric, X[col])
            correlations[col] = abs(corr)
    except:
        pass

top_corrs = sorted(correlations.items(), key=lambda x: x[1], reverse=True)[:5]
for feat, corr in top_corrs:
    print(f"  {feat:30s}: {corr:.4f}")
    if corr > 0.3:
        print(f"    ⚠️  High correlation - may indicate look-ahead bias!")

# Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)

print("\nPotential issues detected:")
issues = []

if len(label_counts) < 3:
    issues.append("❌ Missing label classes")
if min_pct < 15:
    issues.append(f"⚠️  Severe class imbalance ({min_pct:.1f}%)")
if abs(bullish_thresh) > returns_valid.std() * 3:
    issues.append("⚠️  Thresholds too wide (most samples are neutral)")
if len(X) < 200:
    issues.append(f"⚠️  Small training set ({len(X)} samples)")

if issues:
    for issue in issues:
        print(f"  {issue}")
else:
    print("  ✅ No obvious issues detected")

print("\n" + "="*80)
print("RECOMMENDED ACTIONS")
print("="*80)

if min_pct < 5:
    print("\n1. FIX LABEL IMBALANCE:")
    print("   - Thresholds are creating too many of one class")
    print("   - Try: Change from percentile to fixed thresholds (e.g., ±2%)")
    print("   - Or: Adjust percentiles (e.g., 30th/70th instead of 35th/65th)")

if abs(bullish_thresh) > returns_valid.std() * 2:
    print("\n2. ADJUST THRESHOLDS:")
    print(f"   - Current: ±{abs(bullish_thresh):.2%}")
    print(f"   - Return std: {returns_valid.std():.2%}")
    print("   - Try: Use smaller multiplier in compute_thresholds_horizon()")

print("\n3. TEST SIMPLER BASELINE:")
print("   - Create a 'predict always neutral' baseline")
print("   - If it gets 33%, your model isn't learning anything")

print("\n4. CHECK FEATURE ENGINEERING:")
print("   - Review temporal_indicators.py")
print("   - Verify no look-ahead bias")
print("   - Check if features are predictive")

print("\n5. TRY BINARY CLASSIFICATION:")
print("   - Instead of 3 classes (bull/neutral/bear)")
print("   - Try 2 classes: up (>=0) vs down (<0)")
print("   - Easier problem, should get >50% if model works")

print("\n" + "="*80 + "\n")
