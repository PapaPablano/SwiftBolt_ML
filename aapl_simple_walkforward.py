#!/usr/bin/env python3
"""
Simple AAPL Walk-Forward Analysis

Creates a basic walk-forward validation similar to TSLA example
but customized for AAPL indicators review.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Add ml to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "ml"))

from src.data.supabase_db import db
from src.features.technical_indicators import add_technical_features
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import RobustScaler


def fetch_aapl_data(days=500):
    """Fetch AAPL historical data."""
    print(f"Fetching {days} days of AAPL data...")
    df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=days)
    if df is None or len(df) == 0:
        raise ValueError("No AAPL data found")
    print(f"✅ Fetched {len(df)} bars")
    return df


def add_basic_indicators(df):
    """Add basic technical indicators."""
    print("Adding basic indicators...")
    
    # Add returns
    df['returns_1d'] = df['close'].pct_change()
    df['returns_5d'] = df['close'].pct_change(periods=5)
    df['returns_20d'] = df['close'].pct_change(periods=20)
    
    # Moving averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr_14'] = tr.rolling(window=14).mean()
    
    # Price position
    df['price_vs_sma20'] = (df['close'] - df['sma_20']) / df['sma_20']
    df['price_vs_sma50'] = (df['close'] - df['sma_50']) / df['sma_50']
    
    # Volume
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    print("✅ Added basic indicators")
    return df


def create_labels(df, horizon_days=1, threshold_pct=0.005):
    """Create binary labels."""
    print(f"Creating labels (threshold: {threshold_pct:.1%})...")
    
    # Calculate future returns
    df['future_return'] = df['close'].pct_change(horizon_days).shift(-horizon_days)
    
    # Create binary labels (bullish/bearish only)
    df['actual'] = np.where(
        df['future_return'] > threshold_pct,
        1,  # bullish
        np.where(
            df['future_return'] < -threshold_pct,
            -1,  # bearish
            0   # neutral
        )
    )
    
    # Remove rows with NaN labels
    df = df.dropna(subset=['actual'])
    
    label_counts = pd.Series(df['actual']).value_counts().sort_index()
    label_map = {-1: 'bearish', 0: 'neutral', 1: 'bullish'}
    print(f"✅ Labels: {label_counts.map(label_map).to_dict()}")
    return df


def walk_forward_validate(df, initial_train_days=200, test_days=50, step_days=50):
    """Perform walk-forward validation."""
    print(f"Walk-forward validation: train={initial_train_days}, test={test_days}, step={step_days}")
    
    results = {
        'symbol': 'AAPL',
        'window_accuracies': [],
        'window_predictions': [],
        'mean_accuracy': 0,
        'std_accuracy': 0,
        'overall_accuracy': 0,
        'n_windows': 0
    }
    
    # Select features
    feature_cols = [col for col in df.columns 
                   if col not in ['ts', 'open', 'high', 'low', 'close', 'volume', 
                                'future_return', 'actual']]
    
    total_data = len(df)
    current_start = 0
    window_num = 1
    
    while current_start + initial_train_days + test_days <= total_data:
        print(f"\nWindow {window_num}: days {current_start}-{current_start + initial_train_days + test_days - 1}")
        
        # Split data
        train_end = current_start + initial_train_days
        test_end = train_end + test_days
        
        train_data = df.iloc[current_start:train_end]
        test_data = df.iloc[train_end:test_end]
        
        if len(train_data) < 100 or len(test_data) < 20:
            print(f"  ⚠️  Insufficient data, skipping")
            current_start += step_days
            window_num += 1
            continue
        
        try:
            # Prepare features
            X_train = train_data[feature_cols].fillna(train_data[feature_cols].median())
            y_train = train_data['actual']
            X_test = test_data[feature_cols].fillna(train_data[feature_cols].median())
            y_test = test_data['actual']
            
            # Remove rows with NaN
            train_mask = X_train.notna().all(axis=1)
            test_mask = X_test.notna().all(axis=1)
            
            X_train_clean = X_train[train_mask]
            y_train_clean = y_train[train_mask]
            X_test_clean = X_test[test_mask]
            y_test_clean = y_test[test_mask]
            
            if len(X_train_clean) < 50 or len(X_test_clean) < 10:
                print(f"  ⚠️  Insufficient clean data, skipping")
                current_start += step_days
                window_num += 1
                continue
            
            # Scale features
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train_clean)
            X_test_scaled = scaler.transform(X_test_clean)
            
            # Train Random Forest
            rf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
            rf.fit(X_train_scaled, y_train_clean)
            
            # Predict
            y_pred = rf.predict(X_test_scaled)
            accuracy = np.mean(y_pred == y_test_clean)
            
            results['window_accuracies'].append(accuracy)
            
            # Store predictions
            label_map = {-1: 'bearish', 0: 'neutral', 1: 'bullish'}
            pred_labels = [label_map[p] for p in y_pred]
            actual_labels = [label_map[a] for a in y_test_clean]
            
            window_predictions = pd.DataFrame({
                'date': test_data['ts'].values[test_mask],
                'actual': actual_labels,
                'predicted': pred_labels,
                'window': window_num,
                'close': test_data['close'].values[test_mask]
            })
            results['window_predictions'].append(window_predictions)
            
            print(f"  ✅ Accuracy: {accuracy:.1%} (samples: {len(y_test_clean)})")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        current_start += step_days
        window_num += 1
    
    # Calculate overall statistics
    if results['window_accuracies']:
        results['mean_accuracy'] = np.mean(results['window_accuracies'])
        results['std_accuracy'] = np.std(results['window_accuracies'])
        results['n_windows'] = len(results['window_accuracies'])
        
        # Combine all predictions
        all_predictions = pd.concat(results['window_predictions'], ignore_index=True)
        results['overall_accuracy'] = np.mean(all_predictions['actual'] == all_predictions['predicted'])
        results['predictions_df'] = all_predictions
    
    return results


def create_plot(results, output_path):
    """Create walk-forward plot."""
    print("Creating visualization...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('AAPL Walk-Forward Analysis - Indicators Review', fontsize=16, fontweight='bold')
    
    # 1. Accuracy by Window
    ax1 = axes[0, 0]
    windows = range(1, len(results['window_accuracies']) + 1)
    ax1.plot(windows, results['window_accuracies'], marker='o', linewidth=2, color='#2E86AB')
    ax1.axhline(results['mean_accuracy'], color='red', linestyle='--', 
                label=f"Mean: {results['mean_accuracy']:.1%}")
    ax1.axhline(0.50, color='gray', linestyle=':', label="Random (50%)")
    ax1.set_xlabel('Test Window')
    ax1.set_ylabel('Accuracy')
    ax1.set_title('Accuracy by Test Window')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 1)
    
    # 2. Cumulative Accuracy
    ax2 = axes[0, 1]
    predictions_df = results['predictions_df'].copy()
    predictions_df['correct'] = predictions_df['actual'] == predictions_df['predicted']
    predictions_df['cumulative_acc'] = predictions_df['correct'].expanding().mean()
    ax2.plot(predictions_df['date'], predictions_df['cumulative_acc'], color='#A23B72')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Cumulative Accuracy')
    ax2.set_title('Accuracy Over Time (Expanding Window)')
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # 3. Confusion Matrix
    ax3 = axes[1, 0]
    from sklearn.metrics import confusion_matrix
    
    labels_order = ['bearish', 'neutral', 'bullish']
    cm = confusion_matrix(predictions_df['actual'], predictions_df['predicted'], labels=labels_order)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax3,
                xticklabels=['Bearish', 'Neutral', 'Bullish'],
                yticklabels=['Bearish', 'Neutral', 'Bullish'])
    ax3.set_xlabel('Predicted')
    ax3.set_ylabel('Actual')
    ax3.set_title('Overall Confusion Matrix')
    
    # 4. Accuracy Distribution
    ax4 = axes[1, 1]
    ax4.hist(results['window_accuracies'], bins=min(10, len(results['window_accuracies'])), 
             edgecolor='black', alpha=0.7, color='#2E86AB')
    ax4.axvline(results['mean_accuracy'], color='red', linestyle='--',
                label=f"Mean: {results['mean_accuracy']:.1%}")
    ax4.set_xlabel('Accuracy')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Distribution of Window Accuracies')
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Plot saved: {output_path}")


def create_csv(results, output_path):
    """Create CSV with predictions."""
    print("Creating CSV...")
    
    # Main predictions CSV
    predictions_path = output_path.replace('.csv', '_predictions.csv')
    results['predictions_df'].to_csv(predictions_path, index=False)
    print(f"✅ Predictions saved: {predictions_path}")
    
    # Window statistics
    window_stats = []
    for i, acc in enumerate(results['window_accuracies'], 1):
        window_data = results['predictions_df'][results['predictions_df']['window'] == i]
        window_stats.append({
            'window': i,
            'accuracy': acc,
            'predictions': len(window_data),
            'bullish_preds': (window_data['predicted'] == 'bullish').sum(),
            'bearish_preds': (window_data['predicted'] == 'bearish').sum(),
            'neutral_preds': (window_data['predicted'] == 'neutral').sum()
        })
    
    stats_df = pd.DataFrame(window_stats)
    stats_path = output_path.replace('.csv', '_window_stats.csv')
    stats_df.to_csv(stats_path, index=False)
    print(f"✅ Window stats saved: {stats_path}")
    
    return predictions_path


def main():
    """Main execution."""
    print("🔍 AAPL INDICATORS REVIEW - SIMPLE WALK-FORWARD")
    print("=" * 60)
    
    try:
        # Fetch and prepare data
        df = fetch_aapl_data(days=500)
        df = add_basic_indicators(df)
        df = create_labels(df, horizon_days=1, threshold_pct=0.005)
        
        # Run walk-forward validation
        results = walk_forward_validate(df, initial_train_days=200, test_days=50, step_days=50)
        
        if results['n_windows'] == 0:
            print("❌ No valid windows completed")
            return
        
        # Print results
        print(f"\n📊 WALK-FORWARD RESULTS FOR AAPL:")
        print(f"  Mean accuracy: {results['mean_accuracy']:.1%}")
        print(f"  Std deviation: {results['std_accuracy']:.1%}")
        print(f"  Overall accuracy: {results['overall_accuracy']:.1%}")
        print(f"  Windows tested: {results['n_windows']}")
        print(f"  Total predictions: {len(results['predictions_df'])}")
        
        # Generate outputs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create plot
        plot_path = f"/Users/ericpeterson/SwiftBolt_ML/AAPL_walk_forward_plot_{timestamp}.png"
        create_plot(results, plot_path)
        
        # Create CSV
        csv_path = f"/Users/ericpeterson/SwiftBolt_ML/AAPL_walk_forward_{timestamp}.csv"
        create_csv(results, csv_path)
        
        print(f"\n✅ ANALYSIS COMPLETE")
        print(f"📈 Plot: {plot_path}")
        print(f"📊 CSV: {csv_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
