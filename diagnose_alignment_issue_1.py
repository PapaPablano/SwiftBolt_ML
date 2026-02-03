#!/usr/bin/env python3
"""
REVISED DIAGNOSIS: Target Alignment Issue

Since your lag features are correct (looking backward), the 91.7% train 
accuracy is likely caused by target leakage during feature preparation.

Common issue in Kaggle-style time series:
- Target created correctly
- But rows with NaN features not properly removed
- Or target accidentally includes information from feature calculation period
"""

import pandas as pd
import numpy as np


# ============================================================================
# THE ACTUAL PROBLEM (Most Likely)
# ============================================================================

print("""
╔════════════════════════════════════════════════════════════════════════╗
║              REVISED DIAGNOSIS: Target Alignment Issue                 ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  Your lag features are CORRECT (looking backward).                    ║
║  The problem is likely in target creation or row alignment.           ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
""")


# ============================================================================
# COMMON KAGGLE-STYLE TIME SERIES MISTAKE
# ============================================================================

def show_common_mistake():
    """Show the common target leakage pattern"""
    
    print("\n" + "="*80)
    print("COMMON MISTAKE IN TIME SERIES ML")
    print("="*80)
    
    print("""
WRONG WAY (Causes 90%+ train accuracy):
─────────────────────────────────────────────────────────────────────────

def prepare_training_data_binary(self, df, horizon_days=5, threshold_pct=0.015):
    # Step 1: Create target
    df['future_return'] = df['close'].pct_change(horizon_days).shift(-horizon_days)
    df['target'] = (df['future_return'] > threshold_pct).astype(int)
    
    # Step 2: Create features
    for lag in [1, 5, 10, 20, 30]:
        df[f'close_lag{lag}'] = df['close'].shift(lag)  # Correct
    
    # Step 3: Drop NaN rows (WRONG - does this incorrectly)
    df = df.dropna()  # ❌ This drops rows randomly, breaking alignment!
    
    # Step 4: Return
    feature_cols = [col for col in df.columns if 'lag' in col]
    X = df[feature_cols]
    y = df['target']
    
    return X, y  # ❌ Target and features misaligned!


WHY THIS CAUSES 90%+ ACCURACY:
─────────────────────────────────────────────────────────────────────────

When you have:
- close_lag30 (uses bar from 30 days ago) ✅ Correct
- target (return 5 days ahead) ✅ Correct  
- df.dropna() ❌ Drops different rows for features vs target

After dropna():
- Row 35 in X might have features from bar 50
- Row 35 in y might have target from bar 45
- They're MISALIGNED!

The model learns patterns that don't actually exist.


CORRECT WAY (Prevents leakage):
─────────────────────────────────────────────────────────────────────────

def prepare_training_data_binary(self, df, horizon_days=5, threshold_pct=0.015):
    '''Create features and target with proper alignment'''
    
    # Step 1: Create features FIRST (all use past data)
    for lag in [1, 5, 10, 20, 30]:
        df[f'close_lag{lag}'] = df['close'].shift(lag)
    
    df['returns_1d'] = df['close'].pct_change()
    df['rsi_14'] = talib.RSI(df['close'].values, 14)
    # ... other features ...
    
    # Step 2: Create target LAST
    df['future_return'] = df['close'].pct_change(horizon_days).shift(-horizon_days)
    df['target'] = (df['future_return'] > threshold_pct).astype(int)
    
    # Step 3: Select feature columns
    feature_cols = [col for col in df.columns 
                   if col not in ['target', 'future_return', 'close', 'open', 
                                  'high', 'low', 'volume', 'ts', 'timestamp']]
    
    X = df[feature_cols].copy()
    y = df['target'].copy()
    
    # Step 4: Remove rows where TARGET is NaN (at end due to shift(-horizon))
    # AND where features are NaN (at start due to shift(lag))
    valid_mask = ~y.isna()  # Target must be valid
    
    # Also check features aren't all NaN
    valid_mask = valid_mask & (X.notna().sum(axis=1) > len(feature_cols) * 0.5)
    
    X = X[valid_mask].copy()
    y = y[valid_mask].copy()
    
    # Step 5: Handle remaining NaN in features (forward fill)
    X = X.fillna(method='ffill')  # Use forward fill
    X = X.fillna(0)  # Fill any remaining with 0
    
    # Step 6: Verify alignment
    assert len(X) == len(y), "X and y must have same length!"
    assert X.index.equals(y.index), "X and y must have same index!"
    
    return X, y
""")


# ============================================================================
# ANOTHER COMMON ISSUE: INDICATOR CALCULATION TIMING
# ============================================================================

def show_indicator_timing_issue():
    """Show how indicators can cause leakage"""
    
    print("\n" + "="*80)
    print("INDICATOR TIMING ISSUE")
    print("="*80)
    
    print("""
Some TA-Lib indicators use future data by default!

POTENTIAL ISSUE: Bollinger Bands
─────────────────────────────────────────────────────────────────────────

# If you do this:
upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
df['bb_lower'] = lower

# Then use bb_lower as a feature...
# The bb_lower at row i uses close from rows i-19 to i (correct)
# BUT if you then calculate features FROM bb_lower incorrectly...

# WRONG:
df['bb_signal'] = (df['close'] < df['bb_lower']).astype(int)
df['bb_signal_future'] = df['bb_signal'].shift(-5)  # ❌ Uses future signal!

# CORRECT:
df['bb_signal'] = (df['close'] < df['bb_lower']).astype(int)
df['bb_signal_past'] = df['bb_signal'].shift(5)  # ✅ Uses past signal


POTENTIAL ISSUE: SuperTrend
─────────────────────────────────────────────────────────────────────────

Your diagnostic showed 'supertrend_trend_lag30' with 0.601 correlation.

Let me guess your code:
```python
# Step 1: Calculate SuperTrend (correct)
df['supertrend'] = calculate_supertrend(df)
df['supertrend_trend'] = df['supertrend_direction']  # 1 or -1

# Step 2: Create lag feature (correct)  
df['supertrend_trend_lag30'] = df['supertrend_trend'].shift(30)  # ✅ Good

# Step 3: But then maybe you do this somewhere?
df['supertrend_change'] = df['supertrend_trend'] != df['supertrend_trend'].shift(1)
df['supertrend_future_change'] = df['supertrend_change'].shift(-5)  # ❌ Bad!
```

The issue isn't the lag30 feature - it's some OTHER feature derived from 
SuperTrend that accidentally uses future data.
""")


# ============================================================================
# DIAGNOSTIC: CHECK YOUR ACTUAL CODE
# ============================================================================

def diagnostic_questions():
    """Questions to identify the exact issue"""
    
    print("\n" + "="*80)
    print("DIAGNOSTIC QUESTIONS")
    print("="*80)
    
    print("""
Answer these questions to find the exact issue:

1. TARGET CREATION
   Q: In prepare_training_data_binary, what order do you create things?
   
   Show me the order:
   A) Create features first, then target last? ✅ Good
   B) Create target first, then features? ⚠️  Risky
   C) Create features and target together? ❌ Bad

2. NaN HANDLING
   Q: How do you handle NaN values?
   
   A) df.dropna() on entire dataframe? ❌ Causes misalignment
   B) Drop rows where target is NaN? ✅ Good
   C) Forward fill features, then drop NaN targets? ✅✅ Best
   D) fillna(0) on everything? ⚠️  Risky but might work

3. FEATURE FILTERING
   Q: How do you select which columns become features?
   
   A) Select all columns except target/price? ✅ Good
   B) Select columns with 'lag' or 'feature' in name? ✅ Good  
   C) Use df.iloc[:,:-1] to get all but last column? ❌ Risky

4. INDEX ALIGNMENT
   Q: After creating X and y, do you verify:
   
   - len(X) == len(y)? 
   - X.index.equals(y.index)?
   - First/last dates match?

5. INDICATOR CALCULATION
   Q: Do you calculate any features FROM the target variable?
   
   Example:
   - df['target_sma'] = df['target'].rolling(5).mean()  # ❌ Leakage!
   - df['return_future'] = df['close'].shift(-5)  # ❌ Leakage!
""")


# ============================================================================
# QUICK FIX: ADD VERIFICATION
# ============================================================================

def add_verification_code():
    """Add verification to catch alignment issues"""
    
    print("\n" + "="*80)
    print("ADD THIS VERIFICATION TO YOUR CODE")
    print("="*80)
    
    print("""
Add this at the END of prepare_training_data_binary:

```python
def prepare_training_data_binary(self, df, horizon_days=5, threshold_pct=0.015):
    # ... your existing code ...
    
    # CREATE X and y
    X = df[feature_cols].copy()
    y = df['target'].copy()
    
    # ... remove NaN rows ...
    
    # ============================================================
    # VERIFICATION CODE - ADD THIS
    # ============================================================
    
    print(f"\\nVERIFICATION:")
    print(f"  Original df: {len(df)} rows")
    print(f"  Final X: {len(X)} rows")
    print(f"  Final y: {len(y)} rows")
    print(f"  Lengths match: {len(X) == len(y)}")
    print(f"  Indices match: {X.index.equals(y.index)}")
    
    # Check for impossibly high correlation (leakage detector)
    if len(X) > 0 and len(y) > 0:
        correlations = X.corrwith(y).abs().sort_values(ascending=False)
        max_corr = correlations.iloc[0]
        max_feat = correlations.index[0]
        
        print(f"  Max feature correlation: {max_corr:.3f} ({max_feat})")
        
        if max_corr > 0.65:
            print(f"  ⚠️  WARNING: {max_feat} has {max_corr:.1%} correlation with target!")
            print(f"     This suggests possible data leakage.")
    
    # Check target distribution
    print(f"  Target distribution: {y.value_counts().to_dict()}")
    print(f"  Target balance: {y.mean():.1%} positive")
    
    # Check for any NaN in final data
    nan_features = X.columns[X.isna().any()].tolist()
    if nan_features:
        print(f"  ⚠️  Features with NaN: {nan_features[:5]}")
    
    nan_targets = y.isna().sum()
    if nan_targets > 0:
        print(f"  ❌ ERROR: Target has {nan_targets} NaN values!")
    
    return X, y
```

This will help you spot the exact issue.
""")


# ============================================================================
# SPECIFIC FIX FOR 91.7% TRAIN ACCURACY
# ============================================================================

def fix_917_train_accuracy():
    """Specific fix for your 91.7% issue"""
    
    print("\n" + "="*80)
    print("FIX FOR 91.7% TRAIN ACCURACY")
    print("="*80)
    
    print("""
Given that:
1. Your lag features are correct (looking backward)
2. Train accuracy is 91.7%
3. Test accuracy is 68.4%

The issue is almost certainly one of these:

MOST LIKELY: Row Alignment After dropna()
─────────────────────────────────────────────────────────────────────────

Your current code probably does:
```python
# Create features
for lag in [1, 5, 10, 20, 30]:
    df[f'lag{lag}'] = df['close'].shift(lag)

# Create target
df['target'] = (df['close'].pct_change(5).shift(-5) > 0.015).astype(int)

# Select columns
X = df[feature_cols]
y = df['target']

# Remove NaN - THIS IS THE PROBLEM
X = X.dropna()  # Drops different rows than y!
y = y.dropna()  # Now X and y are misaligned!

return X, y  # ❌ Different lengths, different indices
```

FIX:
```python
# Create features
for lag in [1, 5, 10, 20, 30]:
    df[f'lag{lag}'] = df['close'].shift(lag)

# Create target
df['target'] = (df['close'].pct_change(5).shift(-5) > 0.015).astype(int)

# Select columns
X = df[feature_cols].copy()
y = df['target'].copy()

# Remove rows where EITHER X or y has issues
# Method 1: Remove rows with NaN target (most important)
valid_idx = ~y.isna()
X = X[valid_idx]
y = y[valid_idx]

# Method 2: Forward fill NaN in features
X = X.fillna(method='ffill').fillna(0)

# Verify
assert len(X) == len(y)
assert X.index.equals(y.index)

return X, y  # ✅ Same length, same indices
```


SECOND LIKELY: Feature Created From Target
─────────────────────────────────────────────────────────────────────────

Check if you accidentally do this:
```python
df['target'] = (df['close'].pct_change(5).shift(-5) > 0.015).astype(int)

# Then later...
df['target_smooth'] = df['target'].rolling(10).mean()  # ❌ Uses future targets!

# Or even worse:
df['feature_based_on_target'] = df['target'].shift(-5)  # ❌ Direct leakage!
```

Search your code for any line that uses df['target'] on the RIGHT side of =


TEST YOUR FIX:
─────────────────────────────────────────────────────────────────────────

After fixing, train accuracy should drop to 55-65%:

```python
from sklearn.linear_model import LogisticRegression

X, y = model.prepare_training_data_binary(df, 5, 0.015)

split = int(len(X) * 0.8)
lr = LogisticRegression().fit(X[:split], y[:split])

train_acc = lr.score(X[:split], y[:split])
test_acc = lr.score(X[split:], y[split:])

print(f"Train: {train_acc:.1%}")  # Should be 55-65%
print(f"Test: {test_acc:.1%}")   # Should be 50-60%
print(f"Gap: {train_acc - test_acc:.1%}")  # Should be <10%

if train_acc > 0.70:
    print("❌ Still leaking!")
else:
    print("✅ Fixed!")
```
""")


# ============================================================================
# MAIN
# ============================================================================

def main():
    show_common_mistake()
    show_indicator_timing_issue()
    diagnostic_questions()
    add_verification_code()
    fix_917_train_accuracy()
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    
    print("""
1. Add the verification code to prepare_training_data_binary
2. Run your training pipeline
3. Share the verification output with me
4. I'll tell you exactly which line is causing the leakage

OR

Just share your prepare_training_data_binary method code and I'll fix it directly.

The 91.7% train accuracy is definitely fixable - we just need to find
where X and y are getting misaligned or where a feature uses future data.
""")


if __name__ == '__main__':
    main()
