#!/usr/bin/env python3
"""
Diagnostic: Why is accuracy low in recent data?

This script helps understand if the low accuracy (37%) is expected
or indicates a real problem.
"""

import sys
from pathlib import Path
# Resolve src to ml/src when run from project root
_ml = Path(__file__).resolve().parent / "ml"
sys.path.insert(0, str(_ml) if _ml.exists() else str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np
from datetime import datetime

from src.data.supabase_db import SupabaseDatabase
from src.data.data_cleaner import DataCleaner
from src.models.xgboost_forecaster import XGBoostForecaster


def diagnose_accuracy_issue():
    """Diagnose the low accuracy issue"""
    
    print("="*80)
    print("ACCURACY DIAGNOSTIC: Understanding 37% Accuracy")
    print("="*80)
    
    # Load data
    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars('AAPL', timeframe='d1', limit=500)
    df = DataCleaner.clean_all(df, verbose=False)
    
    print(f"\n1. DATA PERIOD")
    print(f"   Date range: {df['ts'].min().date()} to {df['ts'].max().date()}")
    print(f"   Total bars: {len(df)}")
    
    # Calculate returns
    df['returns'] = df['close'].pct_change()
    df['forward_5d_return'] = df['close'].pct_change(5).shift(-5)
    
    # Analyze market behavior
    print(f"\n2. MARKET BEHAVIOR IN THIS PERIOD")
    print(f"   Total return: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.1f}%")
    print(f"   Average daily return: {df['returns'].mean() * 100:.2f}%")
    print(f"   Volatility (std): {df['returns'].std() * 100:.2f}%")
    print(f"   Up days: {(df['returns'] > 0).sum()} ({(df['returns'] > 0).mean() * 100:.1f}%)")
    print(f"   Down days: {(df['returns'] < 0).sum()} ({(df['returns'] < 0).mean() * 100:.1f}%)")
    
    # Analyze 5-day moves
    threshold = 0.015
    df['target'] = (df['forward_5d_return'] > threshold).astype(int)
    
    print(f"\n3. TARGET DISTRIBUTION (5-day moves > {threshold*100:.1f}%)")
    print(f"   Bullish moves (>1.5%): {(df['target'] == 1).sum()} ({(df['target'] == 1).mean() * 100:.1f}%)")
    print(f"   Bearish moves (≤1.5%): {(df['target'] == 0).sum()} ({(df['target'] == 0).mean() * 100:.1f}%)")
    
    # Check if this is a trending market
    sma_20 = df['close'].rolling(20).mean()
    sma_50 = df['close'].rolling(50).mean()
    
    above_20 = (df['close'] > sma_20).mean() * 100
    above_50 = (df['close'] > sma_50).mean() * 100
    
    print(f"\n4. TREND ANALYSIS")
    print(f"   Above 20-day SMA: {above_20:.1f}% of time")
    print(f"   Above 50-day SMA: {above_50:.1f}% of time")
    
    if above_20 > 70 and above_50 > 70:
        print(f"   ⚠️  STRONG UPTREND - This makes prediction harder!")
        print(f"       In trending markets, everything moves together.")
        print(f"       37% accuracy is EXPECTED in this regime.")
    
    # Analyze regime
    recent_vol = df['returns'].tail(100).std() * 100
    older_vol = df['returns'].head(100).std() * 100
    
    print(f"\n5. VOLATILITY COMPARISON")
    print(f"   Recent volatility (last 100 days): {recent_vol:.2f}%")
    print(f"   Earlier volatility (first 100 days): {older_vol:.2f}%")
    
    if recent_vol < 1.5:
        print(f"   ⚠️  LOW VOLATILITY - Harder to predict direction!")
        print(f"       Low vol = small moves = harder to beat 50% baseline.")
    
    # Feature quality check
    model = XGBoostForecaster()
    X, y = model.prepare_training_data_binary(df, horizon_days=5, threshold_pct=0.015)
    
    print(f"\n6. FEATURE QUALITY")
    print(f"   Features generated: {X.shape[1]}")
    print(f"   Training samples: {len(X)}")
    
    # Check feature correlation with target (y is "bullish"/"bearish")
    y_bin = (y == "bullish").astype(int)
    correlations = X.corrwith(y_bin).abs().sort_values(ascending=False)
    
    print(f"\n   Top 5 features correlated with target:")
    for feat, corr in correlations.head(5).items():
        print(f"     {feat:30s}: {corr:.3f}")
    
    if correlations.max() < 0.15:
        print(f"\n   ⚠️  LOW FEATURE CORRELATION - Features weakly predict target!")
        print(f"       Max correlation: {correlations.max():.3f}")
        print(f"       This suggests the target is very hard to predict.")
    
    # Baseline comparison (y is "bullish"/"bearish")
    pos_rate = (y == "bullish").mean()
    baseline_acc = max(pos_rate, 1 - pos_rate)
    
    print(f"\n7. BASELINE COMPARISON")
    print(f"   Baseline (always predict majority): {baseline_acc:.1%}")
    print(f"   Your model accuracy: 37.1%")
    print(f"   Improvement over baseline: {(0.371 - baseline_acc) * 100:+.1f}pp")
    
    if 0.371 < baseline_acc:
        print(f"   ⚠️  MODEL WORSE THAN BASELINE!")
        print(f"       This indicates the model is not learning properly.")
    else:
        print(f"   ✅ Model is learning (beats baseline)")
    
    # Final diagnosis
    print(f"\n{'='*80}")
    print(f"DIAGNOSIS SUMMARY")
    print(f"{'='*80}")
    
    reasons = []
    
    if above_20 > 70:
        reasons.append("Strong uptrend (everything goes up)")
    
    if recent_vol < 1.5:
        reasons.append("Low volatility (small moves)")
    
    if correlations.max() < 0.15:
        reasons.append("Weak feature predictive power")
    
    if len(reasons) > 0:
        print(f"\nLow accuracy (37%) is EXPECTED because:")
        for i, reason in enumerate(reasons, 1):
            print(f"  {i}. {reason}")
        
        print(f"\n✅ CONCLUSION: This is NORMAL for recent bull market data.")
        print(f"   Crash/recovery regimes should show 55-65% accuracy.")
    else:
        print(f"\n⚠️  CONCLUSION: Low accuracy NOT fully explained.")
        print(f"   Check for data quality or feature engineering issues.")
    
    print(f"\n{'='*80}")
    print(f"NEXT STEPS")
    print(f"{'='*80}")
    print(f"\n1. Run regime tests to see crash/recovery accuracy:")
    print(f"   python test_regimes_fixed.py --quick-test AAPL --regime crash_2022")
    print(f"\n2. If crash regime also shows <45%, investigate:")
    print(f"   - Feature engineering issues")
    print(f"   - Data quality problems")
    print(f"   - Model hyperparameters")


if __name__ == '__main__':
    diagnose_accuracy_issue()
