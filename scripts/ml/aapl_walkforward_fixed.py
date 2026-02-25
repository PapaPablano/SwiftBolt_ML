#!/usr/bin/env python3
"""
AAPL Walk-Forward Analysis with Critical Fixes Applied

This script incorporates all the critical fixes:
1. Increased data fetching to 250+ bars
2. TA-Lib error handling
3. Fixed market correlation features
4. Proper data validation
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import logging

# Add ml to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "ml"))

from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_talib_indicator(func, *args, **kwargs):
    """Safely call TA-Lib function with error handling"""
    try:
        result = func(*args, **kwargs)
        if result is None or (isinstance(result, np.ndarray) and len(result) == 0):
            return np.nan
        return result
    except Exception as e:
        logger.warning(f"TA-Lib calculation failed: {e}")
        return np.nan


def fetch_aapl_data(days=500):
    """Fetch AAPL historical data with increased volume."""
    print(f"📊 Fetching {days} days of AAPL data...")
    df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=days)
    if df is None or len(df) == 0:
        raise ValueError("No AAPL data found")
    print(f"✅ Fetched {len(df)} bars")
    
    # Validate data sufficiency
    if len(df) < 250:
        logger.warning(f"⚠️  Only {len(df)} bars available - some indicators may be unstable")
    else:
        print(f"✅ Sufficient data for all indicators")
    
    return df


def fetch_spy_data(days=500):
    """Fetch SPY data for market correlation features."""
    print(f"📊 Fetching {days} days of SPY data...")
    try:
        spy_df = db.fetch_ohlc_bars("SPY", timeframe="d1", limit=days)
        if spy_df is None or len(spy_df) == 0:
            logger.warning("❌ No SPY data found - market correlation features disabled")
            return None
        print(f"✅ Fetched {len(spy_df)} SPY bars")
        return spy_df
    except Exception as e:
        logger.warning(f"❌ SPY fetch failed: {e}")
        return None


def add_market_correlation_features(df, spy_df):
    """Add market correlation features with proper error handling."""
    print("🔗 Adding market correlation features...")
    
    if spy_df is None:
        logger.warning("⚠️  Skipping market correlation - no SPY data")
        return df
    
    try:
        # Merge SPY data
        df_merged = df.merge(spy_df[['ts', 'close']], on='ts', how='left', suffixes=('', '_spy'))
        
        # Calculate returns for both
        df_merged['returns_1d'] = df_merged['close'].pct_change()
        df_merged['returns_spy'] = df_merged['close_spy'].pct_change()
        
        # Calculate correlations with different windows
        df_merged['spy_correlation_20d'] = df_merged['close'].rolling(20).corr(df_merged['close_spy'])
        df_merged['spy_correlation_60d'] = df_merged['close'].rolling(60).corr(df_merged['close_spy'])
        
        # Calculate market beta
        cov_20d = df_merged['returns_1d'].rolling(20).cov(df_merged['returns_spy'])
        var_20d = df_merged['returns_spy'].rolling(20).var()
        df_merged['market_beta_20d'] = cov_20d / var_20d
        
        # Calculate correlation change (momentum)
        df_merged['spy_correlation_change'] = df_merged['spy_correlation_20d'].pct_change()
        
        print("✅ Market correlation features added")
        return df_merged
        
    except Exception as e:
        logger.warning(f"❌ Market correlation error: {e}")
        return df


def add_fixed_indicators(df):
    """Add technical indicators with proper error handling."""
    print("🔧 Adding technical indicators with error handling...")
    
    # Use the existing technical indicators function
    try:
        df_with_indicators = add_technical_features(df.copy())
        print(f"✅ Added {len(df_with_indicators.columns) - len(df.columns)} indicators")
        return df_with_indicators
    except Exception as e:
        logger.warning(f"❌ Technical indicators error: {e}")
        # Fallback to basic indicators
        return add_basic_indicators_fallback(df)


def add_basic_indicators_fallback(df):
    """Fallback basic indicators if main function fails."""
    print("🔄 Using fallback basic indicators...")
    
    # Add returns
    df['returns_1d'] = df['close'].pct_change()
    df['returns_5d'] = df['close'].pct_change(periods=5)
    df['returns_20d'] = df['close'].pct_change(periods=20)
    
    # Moving averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    
    # RSI with error handling
    try:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
    except Exception as e:
        logger.warning(f"RSI calculation failed: {e}")
        df['rsi_14'] = np.nan
    
    # MACD with error handling
    try:
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
    except Exception as e:
        logger.warning(f"MACD calculation failed: {e}")
        df['macd'] = np.nan
        df['macd_signal'] = np.nan
        df['macd_hist'] = np.nan
    
    # ATR with error handling
    try:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr_14'] = true_range.rolling(14).mean()
    except Exception as e:
        logger.warning(f"ATR calculation failed: {e}")
        df['atr_14'] = np.nan
    
    print(f"✅ Added {len(df.columns) - 7} basic indicators")
    return df


def create_labels(df, horizon=1, threshold=0.005):
    """Create directional labels."""
    print(f"🎯 Creating labels (horizon: {horizon} days, threshold: {threshold:.1%})...")
    
    # Calculate future returns
    df['future_return'] = df['close'].shift(-horizon) / df['close'] - 1
    
    # Create labels
    df['label'] = 0  # Neutral
    df.loc[df['future_return'] > threshold, 'label'] = 1  # Bullish
    df.loc[df['future_return'] < -threshold, 'label'] = -1  # Bearish
    
    # Remove rows with NaN labels
    df = df.dropna(subset=['label'])
    
    print(f"✅ Labels created: {df['label'].value_counts().to_dict()}")
    return df


def clean_features(df):
    """Clean and prepare features for ML."""
    print("🧹 Cleaning features...")
    
    # Get numeric columns only
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    feature_cols = [col for col in numeric_cols if col not in ['label', 'future_return']]
    
    # Remove features with too many NaNs
    nan_threshold = len(df) * 0.3  # Allow up to 30% NaN
    clean_features = []
    
    for col in feature_cols:
        if df[col].isna().sum() <= nan_threshold:
            clean_features.append(col)
        else:
            logger.warning(f"⚠️  Removing {col} - too many NaNs")
    
    # Remove rows with too many NaNs
    df_clean = df[clean_features + ['label']].copy()
    nan_count_per_row = df_clean[clean_features].isna().sum(axis=1)
    df_clean = df_clean[nan_count_per_row <= len(clean_features) * 0.2]  # Allow up to 20% NaN per row
    
    # Fill remaining NaNs with median
    for col in clean_features:
        if df_clean[col].isna().any():
            median_val = df_clean[col].median()
            df_clean[col] = df_clean[col].fillna(median_val)
    
    print(f"✅ Features cleaned: {len(clean_features)} features, {len(df_clean)} rows")
    return df_clean, clean_features


def walk_forward_validation(df, features, train_days=200, test_days=50, step_days=50):
    """Perform walk-forward validation."""
    print(f"🔄 Starting walk-forward validation...")
    print(f"   Training: {train_days} days, Testing: {test_days} days, Step: {step_days} days")
    
    results = []
    current_start = 0
    window_num = 1
    
    while current_start + train_days + test_days <= len(df):
        print(f"\n📊 Window {window_num}:")
        
        # Split data
        train_data = df.iloc[current_start:current_start + train_days]
        test_data = df.iloc[current_start + train_days:current_start + train_days + test_days]
        
        # Prepare features
        X_train = train_data[features]
        y_train = train_data['label']
        X_test = test_data[features]
        y_test = test_data['label']
        
        # Scale features
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train_scaled, y_train)
        
        # Predict
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"   Accuracy: {accuracy:.3f}")
        print(f"   Train: {train_data.index[0]} to {train_data.index[-1]}")
        print(f"   Test:  {test_data.index[0]} to {test_data.index[-1]}")
        
        # Store results
        for i, (actual, pred) in enumerate(zip(y_test, y_pred)):
            results.append({
                'date': test_data.index[i],
                'actual': actual,
                'predicted': pred,
                'window': window_num,
                'accuracy': accuracy,
                'close': test_data['close'].iloc[i]
            })
        
        current_start += step_days
        window_num += 1
    
    print(f"\n✅ Walk-forward complete: {window_num - 1} windows")
    return pd.DataFrame(results)


def plot_results(results_df, features_count):
    """Create comprehensive plot of results."""
    print("📈 Creating results plot...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'AAPL Walk-Forward Analysis (Fixed) - {features_count} Features', fontsize=16)
    
    # 1. Accuracy by window
    window_accuracy = results_df.groupby('window')['accuracy'].first()
    axes[0, 0].plot(window_accuracy.index, window_accuracy.values, marker='o', linewidth=2)
    axes[0, 0].axhline(y=0.33, color='r', linestyle='--', alpha=0.7, label='Random Baseline')
    axes[0, 0].set_title('Accuracy by Window')
    axes[0, 0].set_xlabel('Window')
    axes[0, 0].set_ylabel('Accuracy')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # 2. Cumulative accuracy
    results_df['cumulative_accuracy'] = (results_df['actual'] == results_df['predicted']).cumsum() / (results_df.index + 1)
    axes[0, 1].plot(results_df['date'], results_df['cumulative_accuracy'], linewidth=2)
    axes[0, 1].axhline(y=0.33, color='r', linestyle='--', alpha=0.7, label='Random Baseline')
    axes[0, 1].set_title('Cumulative Accuracy Over Time')
    axes[0, 1].set_xlabel('Date')
    axes[0, 1].set_ylabel('Cumulative Accuracy')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # 3. Confusion matrix
    cm = confusion_matrix(results_df['actual'], results_df['predicted'])
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[1, 0])
    axes[1, 0].set_title('Confusion Matrix')
    axes[1, 0].set_xlabel('Predicted')
    axes[1, 0].set_ylabel('Actual')
    
    # 4. Accuracy distribution
    axes[1, 1].hist(results_df.groupby('window')['accuracy'].first(), bins=10, alpha=0.7, edgecolor='black')
    axes[1, 1].axvline(x=0.33, color='r', linestyle='--', alpha=0.7, label='Random Baseline')
    axes[1, 1].set_title('Accuracy Distribution')
    axes[1, 1].set_xlabel('Window Accuracy')
    axes[1, 1].set_ylabel('Frequency')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_filename = f"AAPL_walk_forward_fixed_{timestamp}.png"
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved: {plot_filename}")
    
    return plot_filename


def main():
    """Main execution."""
    print("🔍 AAPL WALK-FORWARD ANALYSIS - FIXED VERSION")
    print("=" * 60)
    print("Incorporating all critical fixes:")
    print("✅ Fix #1: Increased data fetching to 250+ bars")
    print("✅ Fix #2: TA-Lib error handling")
    print("✅ Fix #3: Fixed market correlation features")
    print("✅ Fix #4: Proper data validation")
    
    try:
        # Fix #1: Fetch more data
        df = fetch_aapl_data(days=500)
        spy_df = fetch_spy_data(days=500)
        
        # Fix #3: Add market correlation features
        df = add_market_correlation_features(df, spy_df)
        
        # Fix #2: Add indicators with error handling
        df = add_fixed_indicators(df)
        
        # Create labels
        df = create_labels(df)
        
        # Clean features
        df_clean, features = clean_features(df)
        
        # Walk-forward validation
        results_df = walk_forward_validation(df_clean, features)
        
        # Calculate overall statistics
        overall_accuracy = (results_df['actual'] == results_df['predicted']).mean()
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Overall Accuracy: {overall_accuracy:.3f}")
        print(f"   Random Baseline: 0.333")
        print(f"   Improvement: {(overall_accuracy - 0.333):.3f}")
        print(f"   Total Predictions: {len(results_df)}")
        print(f"   Features Used: {len(features)}")
        
        # Create plots
        plot_filename = plot_results(results_df, len(features))
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"AAPL_walk_forward_fixed_{timestamp}_predictions.csv"
        results_df.to_csv(csv_filename, index=False)
        print(f"✅ Results saved: {csv_filename}")
        
        print(f"\n🎉 ANALYSIS COMPLETE!")
        print(f"📈 Plot: {plot_filename}")
        print(f"📊 Results: {csv_filename}")
        
        # Feature importance
        if len(results_df) > 0:
            # Train final model on all data for feature importance
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(df_clean[features])
            model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            model.fit(X_scaled, df_clean['label'])
            
            print(f"\n🔝 TOP 10 FEATURE IMPORTANCE:")
            feature_importance = pd.DataFrame({
                'feature': features,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            for i, row in feature_importance.head(10).iterrows():
                print(f"   {row['feature']:<25}: {row['importance']:.4f}")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
