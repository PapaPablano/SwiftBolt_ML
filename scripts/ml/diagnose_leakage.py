#!/usr/bin/env python3
"""
Data Leakage Diagnostic Script

Checks if your features contain future information that causes
impossibly high accuracy (>80%).
"""

import sys
from pathlib import Path
# Resolve src to ml/src when run from project root
_ml = Path(__file__).resolve().parent / "ml"
sys.path.insert(0, str(_ml) if _ml.exists() else str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np
from src.data.supabase_db import SupabaseDatabase
from src.data.data_cleaner import DataCleaner
from src.models.xgboost_forecaster import XGBoostForecaster


def check_feature_leakage(symbol: str = 'AAPL', regime_start: str = '2022-03-01', 
                          regime_end: str = '2022-10-31'):
    """
    Check if features contain future information
    """
    
    print("="*80)
    print(f"DATA LEAKAGE DIAGNOSTIC: {symbol}")
    print("="*80)
    
    # Load data
    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=2000)
    df = DataCleaner.clean_all(df, verbose=False)
    
    # Filter to regime
    df['ts'] = pd.to_datetime(df['ts'])
    start = pd.to_datetime(regime_start)
    end = pd.to_datetime(regime_end)
    df = df[(df['ts'] >= start) & (df['ts'] <= end)].copy()
    
    print(f"\n1. BASIC DATA INFO")
    print(f"   Regime: {regime_start} to {regime_end}")
    print(f"   Bars: {len(df)}")
    
    # Prepare features
    model = XGBoostForecaster()
    X, y = model.prepare_training_data_binary(df, horizon_days=5, threshold_pct=0.015)
    
    print(f"   Features: {X.shape[1]}")
    print(f"   Samples: {len(X)}")
    
    # Check 1: Look for features with perfect correlation to target (y is "bullish"/"bearish")
    print(f"\n2. CHECKING FOR PERFECT CORRELATIONS")
    print(f"   (Features with >0.9 correlation suggest leakage)")
    
    y_bin = (y == "bullish").astype(int)
    correlations = X.corrwith(y_bin).abs().sort_values(ascending=False)
    
    suspicious_features = correlations[correlations > 0.7]
    
    if len(suspicious_features) > 0:
        print(f"\n   🚨 FOUND {len(suspicious_features)} SUSPICIOUS FEATURES:")
        for feat, corr in suspicious_features.items():
            print(f"      {feat:40s}: {corr:.3f}")
        print(f"\n   These features are TOO correlated with future returns!")
        print(f"   Likely causes:")
        print(f"   - Feature uses future data (look-ahead bias)")
        print(f"   - Feature calculated incorrectly (using shift)")
        print(f"   - Feature derived from target variable")
    else:
        print(f"   ✅ No perfect correlations found")
        print(f"   Top correlations:")
        for feat, corr in correlations.head(5).items():
            print(f"      {feat:40s}: {corr:.3f}")
    
    # Check 2: Verify time ordering
    print(f"\n3. CHECKING TIME ORDERING")
    
    # Get actual dates for X samples
    # X index should map to df index
    if len(X) == len(df):
        print(f"   ⚠️  WARNING: Feature count equals bar count")
        print(f"      This suggests features might not account for lookback periods")
    
    # Check 3: Look for suspiciously good features
    print(f"\n4. TESTING FEATURE PREDICTIVE POWER")
    
    # Try predicting with just top 5 features
    from sklearn.linear_model import LogisticRegression
    
    top_5_features = correlations.head(5).index
    X_top5 = X[top_5_features].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # Simple 80/20 split
    split = int(len(X_top5) * 0.8)
    X_train = X_top5.iloc[:split]
    X_test = X_top5.iloc[split:]
    y_train = y.iloc[:split]
    y_test = y.iloc[split:]
    
    # Train simple logistic regression
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    
    train_acc = lr.score(X_train, y_train)
    test_acc = lr.score(X_test, y_test)
    
    print(f"\n   Using only top 5 features:")
    print(f"   Train accuracy: {train_acc:.1%}")
    print(f"   Test accuracy: {test_acc:.1%}")
    
    if train_acc > 0.8:
        print(f"\n   🚨 SEVERE DATA LEAKAGE DETECTED!")
        print(f"      Train accuracy {train_acc:.1%} is impossibly high")
        print(f"      Your features contain future information")
    elif test_acc > 0.70:
        print(f"\n   🚨 POSSIBLE DATA LEAKAGE")
        print(f"      Test accuracy {test_acc:.1%} is suspiciously high")
    else:
        print(f"\n   ✅ Accuracy seems reasonable")
    
    # Check 4: Feature inspection
    print(f"\n5. INSPECTING FEATURE VALUES")
    
    # Look at a few suspicious features
    for feat in suspicious_features.head(3).index:
        feat_values = X[feat]
        print(f"\n   Feature: {feat}")
        print(f"   Sample values: {feat_values.iloc[:5].values}")
        print(f"   Stats: min={feat_values.min():.3f}, max={feat_values.max():.3f}, "
              f"mean={feat_values.mean():.3f}")
        
        # Check if feature is just shifted target
        if feat.startswith('returns_') or feat.startswith('target_'):
            print(f"   ⚠️  This feature name suggests it might contain future returns!")
    
    # Final diagnosis
    print(f"\n{'='*80}")
    print(f"DIAGNOSIS")
    print(f"{'='*80}")
    
    if len(suspicious_features) > 0 or train_acc > 0.8:
        print(f"\n🚨 DATA LEAKAGE LIKELY")
        print(f"\nYour impossibly high accuracies (89%, 100%) are caused by:")
        print(f"1. Features containing future information")
        print(f"2. Tiny test sets amplifying overfitting")
        print(f"\nTO FIX:")
        print(f"1. Review feature engineering code")
        print(f"2. Ensure all features use only past data")
        print(f"3. Use walk-forward validation (not 80/20 split)")
        print(f"4. Remove suspicious features: {list(suspicious_features.head(3).index)}")
    else:
        print(f"\n✅ NO OBVIOUS LEAKAGE DETECTED")
        print(f"\nHowever, your high accuracies still suggest problems:")
        print(f"1. Test sets too small (15-20 bars)")
        print(f"2. Overfitting on regime-specific patterns")
        print(f"3. Random variance dominating results")
        print(f"\nTO FIX:")
        print(f"1. Use walk-forward validation")
        print(f"2. Increase minimum regime size")
        print(f"3. Report confidence intervals, not point estimates")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='AAPL', help='Stock to check')
    parser.add_argument('--regime', default='crash_2022', 
                       help='Regime: crash_2022, recovery_2023, bull_2024')
    
    args = parser.parse_args()
    
    regimes = {
        'crash_2022': ('2022-03-01', '2022-10-31'),
        'recovery_2023': ('2022-11-01', '2023-12-31'),
        'bull_2024': ('2024-01-01', '2024-12-31'),
    }
    
    regime_dates = regimes.get(args.regime, regimes['crash_2022'])
    
    check_feature_leakage(args.symbol, regime_dates[0], regime_dates[1])
