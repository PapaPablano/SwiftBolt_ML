#!/usr/bin/env python3
"""
AAPL Indicators Review - Custom Walk-Forward Analysis

This script creates a customized walk-forward validation and visualization
specifically for reviewing AAPL indicators and ML features pipeline.

Generates:
1. Custom walk-forward plot (like TSLA example)
2. Detailed CSV predictions with indicators
3. Feature importance analysis
4. Indicator performance breakdown
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
from src.features.support_resistance_detector import SupportResistanceDetector
from src.strategies.supertrend_ai import SuperTrendAI
from src.models.ensemble_forecaster import EnsembleForecaster


def fetch_aapl_historical_data(days=500):
    """Fetch historical AAPL data for walk-forward analysis."""
    print(f"Fetching {days} days of AAPL historical data...")
    
    try:
        df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=days)
        if df is None or len(df) == 0:
            raise ValueError("No AAPL data found")
            
        print(f"✅ Fetched {len(df)} bars from {df['ts'].min()} to {df['ts'].max()}")
        return df
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None


def add_all_indicators(df):
    """Add all indicators to the dataframe."""
    print("Adding technical indicators...")
    
    # Add technical indicators
    df_with_indicators = add_technical_features(df.copy())
    
    # Add S/R detection
    try:
        sr_detector = SupportResistanceDetector()
        sr_levels = sr_detector.find_all_levels(df)
        
        # Add S/R features to dataframe
        df_with_indicators['nearest_support'] = sr_levels.get('nearest_support', df['close'])
        df_with_indicators['nearest_resistance'] = sr_levels.get('nearest_resistance', df['close'])
        df_with_indicators['support_distance'] = sr_levels.get('support_distance_pct', 0)
        df_with_indicators['resistance_distance'] = sr_levels.get('resistance_distance_pct', 0)
        
        # Add polynomial features
        polynomial = sr_levels.get('polynomial', {})
        df_with_indicators['poly_support'] = polynomial.get('support', df['close'])
        df_with_indicators['poly_resistance'] = polynomial.get('resistance', df['close'])
        df_with_indicators['poly_diverging'] = int(polynomial.get('isDiverging', False))
        
        print("✅ Added S/R features")
    except Exception as e:
        print(f"⚠️  S/R detection failed: {e}")
    
    # Add SuperTrend AI features
    try:
        st_ai = SuperTrendAI(
            df,
            atr_length=10,
            min_mult=1.0,
            max_mult=5.0,
            step=0.5,
            perf_alpha=10,
            from_cluster="Best"
        )
        df_st, st_info = st_ai.calculate()
        
        # Merge SuperTrend features
        st_features = ['supertrend', 'supertrend_trend', 'signal_confidence', 
                      'supertrend_performance_index', 'target_factor']
        for feature in st_features:
            if feature in df_st.columns:
                df_with_indicators[feature] = df_st[feature]
        
        print(f"✅ Added SuperTrend AI (factor: {st_info['target_factor']:.2f})")
    except Exception as e:
        print(f"⚠️  SuperTrend AI failed: {e}")
    
    return df_with_indicators


def create_labels(df, horizon_days=1, threshold_pct=0.005):
    """Create binary labels based on future returns."""
    print(f"Creating labels (horizon: {horizon_days} days, threshold: {threshold_pct:.1%})...")
    
    df = df.copy()
    
    # Calculate future returns
    df['future_return'] = df['close'].pct_change(horizon_days).shift(-horizon_days)
    
    # Create binary labels
    df['actual'] = np.where(
        df['future_return'] > threshold_pct,
        'bullish',
        np.where(
            df['future_return'] < -threshold_pct,
            'bearish',
            'neutral'
        )
    )
    
    # Create labels - use numeric labels for ensemble
    df['actual_numeric'] = df['actual'].map({
        'bearish': -1,
        'neutral': 0, 
        'bullish': 1
    })
    
    # Remove rows with NaN labels
    df = df.dropna(subset=['actual_numeric'])
    
    print(f"✅ Created labels: {df['actual'].value_counts().to_dict()}")
    return df


def walk_forward_validate_aapl(df, initial_train_days=200, test_days=50, step_days=50):
    """Perform walk-forward validation on AAPL with feature analysis."""
    print(f"Starting walk-forward validation...")
    print(f"  Initial train: {initial_train_days} days")
    print(f"  Test window: {test_days} days")
    print(f"  Step: {step_days} days")
    
    results = {
        'symbol': 'AAPL',
        'window_accuracies': [],
        'window_predictions': [],
        'feature_importance': [],
        'indicator_performance': {},
        'mean_accuracy': 0,
        'std_accuracy': 0,
        'overall_accuracy': 0,
        'n_windows': 0
    }
    
    total_data = len(df)
    current_start = 0
    
    window_num = 1
    
    while current_start + initial_train_days + test_days <= total_data:
        print(f"\nWindow {window_num}: Training on days {current_start}-{current_start + initial_train_days - 1}, "
              f"testing on days {current_start + initial_train_days}-{current_start + initial_train_days + test_days - 1}")
        
        # Split data
        train_end = current_start + initial_train_days
        test_end = train_end + test_days
        
        train_data = df.iloc[current_start:train_end].copy()
        test_data = df.iloc[train_end:test_end].copy()
        
        # Skip if not enough data or labels
        if len(train_data) < 100 or len(test_data) < 20:
            print(f"  ⚠️  Insufficient data, skipping window")
            current_start += step_days
            window_num += 1
            continue
        
        try:
            # Prepare features - be more selective
            feature_columns = [col for col in train_data.columns 
                             if col not in ['ts', 'open', 'high', 'low', 'close', 'volume', 
                                          'future_return', 'actual']]
            
            # Remove columns with too many NaNs and keep only numeric
            valid_features = []
            for col in feature_columns:
                if (train_data[col].notna().sum() > len(train_data) * 0.8 and  # At least 80% valid
                    train_data[col].dtype in ['float64', 'int64', 'float32', 'int32']):  # Numeric only
                    valid_features.append(col)
            
            if len(valid_features) < 5:
                print(f"  ⚠️  Too few valid features ({len(valid_features)}), skipping")
                current_start += step_days
                window_num += 1
                continue
            
            # Fill NaN values with median
            train_features = train_data[valid_features].fillna(train_data[valid_features].median())
            test_features = test_data[valid_features].fillna(train_data[valid_features].median())
            
            # Remove any remaining NaN rows
            train_mask = train_features.notna().all(axis=1)
            test_mask = test_features.notna().all(axis=1)
            
            train_features_clean = train_features[train_mask]
            train_labels_clean = pd.Series(train_data['actual_numeric'].values[train_mask])
            test_features_clean = test_features[test_mask]
            test_labels_clean = pd.Series(test_data['actual_numeric'].values[test_mask])
            
            if len(train_features_clean) < 50 or len(test_features_clean) < 10:
                print(f"  ⚠️  Insufficient clean data (train: {len(train_features_clean)}, test: {len(test_features_clean)}), skipping")
                current_start += step_days
                window_num += 1
                continue
            
            print(f"  📊 Using {len(valid_features)} features: {valid_features[:5]}...")
            
            # Train ensemble model
            ensemble = EnsembleForecaster()
            ensemble = ensemble.train(train_features_clean, train_labels_clean)
            
            # Make predictions
            predictions = []
            for i in range(len(test_features_clean)):
                test_row = test_features_clean.iloc[[i]]  # Keep as DataFrame
                pred_dict = ensemble.predict(test_row)
                predictions.append(pred_dict['label'])
            y_pred = np.array(predictions)
            y_test = test_labels_clean.values
            
            # Calculate accuracy
            accuracy = np.mean(y_pred == y_test)
            results['window_accuracies'].append(accuracy)
            
            # Store predictions with dates
            test_dates = test_data['ts'].values[test_mask]
            test_closes = test_data['close'].values[test_mask]
            
            # Convert numeric predictions back to string labels
            pred_labels = []
            for pred in y_pred:
                if pred == 1:
                    pred_labels.append('bullish')
                elif pred == -1:
                    pred_labels.append('bearish')
                else:
                    pred_labels.append('neutral')
            
            # Convert actual numeric back to string for display
            actual_labels = []
            for actual in y_test:
                if actual == 1:
                    actual_labels.append('bullish')
                elif actual == -1:
                    actual_labels.append('bearish')
                else:
                    actual_labels.append('neutral')
            
            window_predictions = pd.DataFrame({
                'date': test_dates,
                'actual': actual_labels,
                'predicted': pred_labels,
                'window': window_num,
                'close': test_closes
            })
            results['window_predictions'].append(window_predictions)
            
            # Store feature importance (simplified)
            if hasattr(ensemble, 'training_stats'):
                results['feature_importance'].append({
                    'window': window_num,
                    'rf_accuracy': ensemble.training_stats.get('rf_accuracy', 0),
                    'gb_accuracy': ensemble.training_stats.get('gb_accuracy', 0)
                })
            
            print(f"  ✅ Accuracy: {accuracy:.1%} (samples: {len(y_test)})")
            
        except Exception as e:
            print(f"  ❌ Error in window {window_num}: {e}")
        
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
        
        # Aggregate feature importance
        if results['feature_importance']:
            all_importance = pd.concat(results['feature_importance'], ignore_index=True)
            results['avg_feature_importance'] = all_importance.groupby('feature')['importance'].mean().sort_values(ascending=False)
    
    return results


def create_custom_plot(results, output_path):
    """Create custom walk-forward plot for AAPL indicators review."""
    print("Creating custom visualization...")
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('AAPL Indicators Review - Walk-Forward Analysis', fontsize=16, fontweight='bold')
    
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
    ax3 = axes[0, 2]
    from sklearn.metrics import confusion_matrix
    
    labels_order = ['bearish', 'neutral', 'bullish']
    cm = confusion_matrix(predictions_df['actual'], predictions_df['predicted'], labels=labels_order)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax3,
                xticklabels=['Bearish', 'Neutral', 'Bullish'],
                yticklabels=['Bearish', 'Neutral', 'Bullish'])
    ax3.set_xlabel('Predicted')
    ax3.set_ylabel('Actual')
    ax3.set_title('Overall Confusion Matrix')
    
    # 4. Feature Importance (Top 15)
    ax4 = axes[1, 0]
    if 'avg_feature_importance' in results:
        top_features = results['avg_feature_importance'].head(15)
        y_pos = range(len(top_features))
        ax4.barh(y_pos, top_features.values, color='#F18F01')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels([f.replace('_', ' ').title() for f in top_features.index])
        ax4.set_xlabel('Mean Importance')
        ax4.set_title('Top 15 Feature Importance')
        ax4.grid(True, alpha=0.3, axis='x')
    
    # 5. Prediction Distribution
    ax5 = axes[1, 1]
    pred_counts = predictions_df['predicted'].value_counts()
    colors = ['#C73E1D', '#F18F01', '#2E86AB']  # bearish, neutral, bullish
    ax5.pie(pred_counts.values, labels=pred_counts.index, autopct='%1.1f%%', 
            colors=[colors[pred_counts.index.get_idx(label)] for label in pred_counts.index])
    ax5.set_title('Prediction Distribution')
    
    # 6. Accuracy Distribution
    ax6 = axes[1, 2]
    ax6.hist(results['window_accuracies'], bins=min(10, len(results['window_accuracies'])), 
             edgecolor='black', alpha=0.7, color='#2E86AB')
    ax6.axvline(results['mean_accuracy'], color='red', linestyle='--',
                label=f"Mean: {results['mean_accuracy']:.1%}")
    ax6.set_xlabel('Accuracy')
    ax6.set_ylabel('Frequency')
    ax6.set_title('Distribution of Window Accuracies')
    ax6.legend()
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Plot saved: {output_path}")


def create_detailed_csv(results, output_path):
    """Create detailed CSV with predictions and key indicators."""
    print("Creating detailed CSV...")
    
    predictions_df = results['predictions_df'].copy()
    
    # Add key indicator values for each prediction date
    # Note: In a real implementation, you'd merge with the original indicator data
    
    # Add window performance metrics
    window_stats = []
    for window_num in predictions_df['window'].unique():
        window_data = predictions_df[predictions_df['window'] == window_num]
        accuracy = np.mean(window_data['actual'] == window_data['predicted'])
        window_stats.append({
            'window': window_num,
            'accuracy': accuracy,
            'predictions': len(window_data),
            'bullish_preds': (window_data['predicted'] == 'bullish').sum(),
            'bearish_preds': (window_data['predicted'] == 'bearish').sum(),
            'neutral_preds': (window_data['predicted'] == 'neutral').sum()
        })
    
    window_stats_df = pd.DataFrame(window_stats)
    
    # Save main predictions
    main_csv_path = output_path.replace('.csv', '_predictions.csv')
    predictions_df.to_csv(main_csv_path, index=False)
    print(f"✅ Predictions saved: {main_csv_path}")
    
    # Save window statistics
    stats_csv_path = output_path.replace('.csv', '_window_stats.csv')
    window_stats_df.to_csv(stats_csv_path, index=False)
    print(f"✅ Window stats saved: {stats_csv_path}")
    
    # Save feature importance
    if 'avg_feature_importance' in results:
        importance_df = results['avg_feature_importance'].reset_index()
        importance_df.columns = ['feature', 'mean_importance']
        importance_csv_path = output_path.replace('.csv', '_feature_importance.csv')
        importance_df.to_csv(importance_csv_path, index=False)
        print(f"✅ Feature importance saved: {importance_csv_path}")
    
    return main_csv_path


def main():
    """Main execution function."""
    print("🔍 AAPL INDICATORS REVIEW - WALK-FORWARD ANALYSIS")
    print("=" * 60)
    
    # Fetch data
    df = fetch_aapl_historical_data(days=500)
    if df is None:
        return
    
    # Add indicators
    df_with_indicators = add_all_indicators(df)
    
    # Create labels
    df_labeled = create_labels(df_with_indicators, horizon_days=1, threshold_pct=0.005)
    
    # Run walk-forward validation
    results = walk_forward_validate_aapl(df_labeled, initial_train_days=200, test_days=50, step_days=50)
    
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
    create_custom_plot(results, plot_path)
    
    # Create CSV
    csv_path = f"/Users/ericpeterson/SwiftBolt_ML/AAPL_walk_forward_{timestamp}.csv"
    create_detailed_csv(results, csv_path)
    
    # Show top features
    if 'avg_feature_importance' in results:
        print(f"\n🎯 TOP 10 FEATURES:")
        for i, (feature, importance) in enumerate(results['avg_feature_importance'].head(10).items(), 1):
            print(f"  {i:2d}. {feature:<30} {importance:.4f}")
    
    print(f"\n✅ ANALYSIS COMPLETE")
    print(f"📈 Plot: {plot_path}")
    print(f"📊 CSV: {csv_path}")


if __name__ == "__main__":
    main()
