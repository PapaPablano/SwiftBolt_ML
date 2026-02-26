#!/usr/bin/env python3
"""
Quick patch to add verification to XGBoostForecaster

This will show us if there's misalignment or leakage
"""

print("""
╔════════════════════════════════════════════════════════════════════════╗
║                    VERIFICATION PATCH                                  ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  Add this code to your XGBoostForecaster.prepare_training_data_binary ║
║                                                                        ║
║  Location: src/models/xgboost_forecaster.py                          ║
║  Method: prepare_training_data_binary                                 ║
║  Position: RIGHT BEFORE 'return X, y'                                 ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝

ADD THIS CODE:
═══════════════════════════════════════════════════════════════════════

    # ===== VERIFICATION CODE - ADD BEFORE RETURN =====
    print(f"\\n{'='*80}")
    print("FEATURE/TARGET VERIFICATION")
    print(f"{'='*80}")
    print(f"Original df rows: {len(df)}")
    print(f"Final X rows: {len(X)}")
    print(f"Final y rows: {len(y)}")
    print(f"Lengths match: {len(X) == len(y)}")
    print(f"Indices match: {X.index.equals(y.index)}")
    
    # Check for leakage via correlation
    if len(X) > 0 and len(y) > 0:
        correlations = X.corrwith(y).abs().sort_values(ascending=False)
        print(f"\\nTop 10 features by correlation with target:")
        for feat, corr in correlations.head(10).items():
            print(f"  {feat:40s}: {corr:.3f}")
        
        max_corr = correlations.iloc[0]
        if max_corr > 0.65:
            print(f"\\n⚠️  WARNING: Max correlation {max_corr:.3f} suggests possible leakage!")
        elif max_corr > 0.55:
            print(f"\\n⚠️  CAUTION: Max correlation {max_corr:.3f} is borderline high")
        else:
            print(f"\\n✅ Max correlation {max_corr:.3f} looks reasonable")
    
    # Check target distribution
    print(f"\\nTarget distribution:")
    print(f"  Positive (1): {(y == 1).sum()} ({(y == 1).mean()*100:.1f}%)")
    print(f"  Negative (0): {(y == 0).sum()} ({(y == 0).mean()*100:.1f}%)")
    
    # Check for NaN
    nan_in_X = X.isna().sum().sum()
    nan_in_y = y.isna().sum()
    print(f"\\nNaN check:")
    print(f"  NaN in X: {nan_in_X}")
    print(f"  NaN in y: {nan_in_y}")
    
    if nan_in_X > 0 or nan_in_y > 0:
        print(f"  ❌ ERROR: Found NaN values!")
    else:
        print(f"  ✅ No NaN values")
    
    print(f"{'='*80}")
    # ===== END VERIFICATION CODE =====
    
    return X, y


EXAMPLE OUTPUT YOU SHOULD SEE:
═══════════════════════════════════════════════════════════════════════

When you run the test again, you'll see something like:

================================================================================
FEATURE/TARGET VERIFICATION
================================================================================
Original df rows: 169
Final X rows: 91
Final y rows: 91
Lengths match: True
Indices match: True

Top 10 features by correlation with target:
  bb_lower                                : 0.613
  supertrend_trend_lag30                  : 0.601
  historical_volatility_60d               : 0.568
  sma_50                                  : 0.553
  bb_upper                                : 0.483
  ema_26                                  : 0.465
  sma_20                                  : 0.447
  ...

⚠️  WARNING: Max correlation 0.613 suggests possible leakage!

Target distribution:
  Positive (1): 50 (54.9%)
  Negative (0): 41 (45.1%)

NaN check:
  NaN in X: 0
  NaN in y: 0
  ✅ No NaN values
================================================================================


INTERPRETATION:
═══════════════════════════════════════════════════════════════════════

1. If "Lengths match: False" → Misalignment issue (use fix #1 below)
2. If "Indices match: False" → Misalignment issue (use fix #1 below)
3. If "Max correlation > 0.65" → Feature leakage (use fix #2 below)
4. If "NaN in X or y > 0" → Data cleaning issue (use fix #3 below)


FIX #1: Alignment Issue
═══════════════════════════════════════════════════════════════════════

If lengths or indices don't match, replace your dropna logic with:

    # WRONG:
    # X = X.dropna()
    # y = y.dropna()
    
    # CORRECT:
    valid_idx = ~y.isna()  # Keep only rows with valid target
    X = X[valid_idx]
    y = y[valid_idx]
    
    # Forward fill NaN in features
    X = X.fillna(method='ffill')
    X = X.fillna(0)
    
    # Verify
    assert len(X) == len(y), f"Length mismatch: X={len(X)}, y={len(y)}"
    assert X.index.equals(y.index), "Index mismatch!"


FIX #2: High Correlation (>0.60)
═══════════════════════════════════════════════════════════════════════

The features bb_lower (0.613) and supertrend_trend_lag30 (0.601) are 
TOO correlated with the target.

Option A - Remove these features:
    
    # After creating X, y:
    high_corr_features = ['bb_lower', 'supertrend_trend_lag30', 
                          'historical_volatility_60d']
    X = X.drop(columns=high_corr_features, errors='ignore')

Option B - Investigate why they're so correlated:
    
    # Check if bb_lower is calculated correctly
    # bb_lower should use only past 20 days, not future data
    
    # Check if supertrend_trend_lag30 uses correct shift direction
    # It should be: df['supertrend_trend'].shift(30)  # 30 days AGO
    # Not: df['supertrend_trend'].shift(-30)  # 30 days AHEAD


FIX #3: Use Walk-Forward Validation
═══════════════════════════════════════════════════════════════════════

Your 19-bar test set is TOO SMALL. Use walk-forward instead of 80/20:

Replace evaluate_stock_in_regime in test_regimes_fixed.py with:

def evaluate_stock_in_regime_FIXED(...):
    # ... load data, prepare features ...
    
    # Instead of:
    # split = int(len(X) * 0.8)
    # X_train, X_test = X[:split], X[split:]
    
    # Use walk-forward:
    min_train = 50
    test_window = 5
    n_windows = (len(X) - min_train) // test_window
    
    all_predictions = []
    all_actuals = []
    
    for i in range(n_windows):
        train_end = min_train + (i * test_window)
        test_start = train_end
        test_end = min(test_start + test_window, len(X))
        
        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]
        X_test = X.iloc[test_start:test_end]
        y_test = y.iloc[test_start:test_end]
        
        model.train(X_train, y_train)
        preds = (model.predict_proba(X_test)[:, 1] > 0.5).astype(int)
        
        all_predictions.extend(preds)
        all_actuals.extend(y_test.values)
    
    accuracy = (np.array(all_predictions) == np.array(all_actuals)).mean()
    
    return {
        'accuracy': accuracy,
        'test_samples': len(all_predictions),  # 40+ instead of 19
        'n_windows': n_windows
    }


NEXT STEPS:
═══════════════════════════════════════════════════════════════════════

1. Add the verification code to prepare_training_data_binary
2. Run: python test_regimes_fixed.py --quick-test AAPL --regime crash_2022
3. Check the verification output
4. Apply the appropriate fix based on what you see
5. Re-run and accuracy should drop to 52-58% (realistic!)

""")
