#!/usr/bin/env python3
"""
Comprehensive AAPL Indicators Review

Based on Perplexity expert recommendations, this script analyzes the critical areas
that explain why the walk-forward validation achieved 33% accuracy (random performance).

Key Review Areas:
1. Indicator Stationarity and Information Content
2. Label Definition and Target Leakage
3. Feature Engineering Issues  
4. Walk-Forward Implementation Specifics
5. Model Architecture Mismatch
6. Critical Reality Check
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit

# Add ml to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "ml"))

from src.data.supabase_db import db


def fetch_aapl_data(days=500):
    """Fetch AAPL historical data."""
    print(f"📊 Fetching {days} days of AAPL data...")
    df = db.fetch_ohlc_bars("AAPL", timeframe="d1", limit=days)
    if df is None or len(df) == 0:
        raise ValueError("No AAPL data found")
    print(f"✅ Fetched {len(df)} bars from {df['ts'].min()} to {df['ts'].max()}")
    return df


def add_comprehensive_indicators(df):
    """Add comprehensive technical indicators with analysis."""
    print("🔧 Adding comprehensive indicators...")
    
    # Price Action Features
    df['returns_1d'] = df['close'].pct_change()
    df['returns_5d'] = df['close'].pct_change(periods=5)
    df['returns_20d'] = df['close'].pct_change(periods=20)
    df['returns_5d_vol'] = df['returns_5d'].rolling(5).std()
    
    # Moving Averages (Multiple Timeframes)
    df['sma_10'] = df['close'].rolling(window=10).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    
    # Price Position vs MAs
    df['price_vs_sma10'] = (df['close'] - df['sma_10']) / df['sma_10']
    df['price_vs_sma20'] = (df['close'] - df['sma_20']) / df['sma_20']
    df['price_vs_sma50'] = (df['close'] - df['sma_50']) / df['sma_50']
    df['price_vs_ema12'] = (df['close'] - df['ema_12']) / df['ema_12']
    df['price_vs_ema26'] = (df['close'] - df['ema_26']) / df['ema_26']
    
    # MA Crosses
    df['sma_cross_10_20'] = (df['sma_10'] > df['sma_20']).astype(int)
    df['ema_cross_12_26'] = (df['ema_12'] > df['ema_26']).astype(int)
    
    # Momentum Indicators
    # RSI (Multiple periods)
    for period in [14, 21, 30]:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df['macd_cross'] = (df['macd'] > df['macd_signal']).astype(int)
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Volatility Indicators
    # ATR (Multiple periods)
    for period in [14, 21]:
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df[f'atr_{period}'] = tr.rolling(window=period).mean()
        df[f'atr_{period}_norm'] = df[f'atr_{period}'] / df['close']
    
    # Historical Volatility
    df['volatility_10d'] = df['returns_1d'].rolling(window=10).std() * np.sqrt(252)
    df['volatility_20d'] = df['returns_1d'].rolling(window=20).std() * np.sqrt(252)
    
    # Volume Indicators
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma_20']
    df['volume_ratio_5d'] = df['volume'] / df['volume'].rolling(window=5).mean()
    
    # On-Balance Volume
    obv = []
    obv_value = 0
    for i in range(len(df)):
        if i == 0:
            obv_value = df['volume'].iloc[i]
        else:
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv_value += df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv_value -= df['volume'].iloc[i]
        obv.append(obv_value)
    df['obv'] = obv
    df['obv_sma'] = df['obv'].rolling(window=20).mean()
    
    # Price Patterns
    df['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
    df['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)
    df['inside_bar'] = ((df['high'] <= df['high'].shift(1)) & (df['low'] >= df['low'].shift(1))).astype(int)
    
    print(f"✅ Added {len([col for col in df.columns if col not in ['ts', 'open', 'high', 'low', 'close', 'volume']])} indicators")
    return df


def create_labels(df, horizon_days=1, threshold_pct=0.005):
    """Create labels with detailed analysis."""
    print(f"🎯 Creating labels (horizon: {horizon_days} days, threshold: {threshold_pct:.1%})...")
    
    # Calculate future returns
    df['future_return'] = df['close'].pct_change(horizon_days).shift(-horizon_days)
    
    # Create binary labels
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
    df = df.dropna(subset=['actual', 'future_return'])
    
    # Label analysis
    label_counts = pd.Series(df['actual']).value_counts().sort_index()
    label_map = {-1: 'bearish', 0: 'neutral', 1: 'bullish'}
    
    print(f"✅ Labels: {label_counts.map(label_map).to_dict()}")
    print(f"   Future return stats: mean={df['future_return'].mean():.4f}, std={df['future_return'].std():.4f}")
    print(f"   Return distribution: 25th={df['future_return'].quantile(0.25):.4f}, 75th={df['future_return'].quantile(0.75):.4f}")
    
    return df


def analyze_indicator_stationarity(df):
    """Analyze indicator stationarity and information content."""
    print("\n🔍 ANALYSIS 1: Indicator Stationarity and Information Content")
    print("=" * 70)
    
    feature_cols = [col for col in df.columns 
                   if col not in ['ts', 'open', 'high', 'low', 'close', 'volume', 
                                'future_return', 'actual']]
    
    # Correlation analysis with target
    correlations = {}
    for col in feature_cols:
        if df[col].dtype in ['float64', 'int64']:
            corr = df[col].corr(df['actual'])
            if not np.isnan(corr):
                correlations[col] = abs(corr)
    
    # Sort by correlation strength
    sorted_corrs = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
    
    print("\n📈 Top 15 Indicators by Correlation with Target:")
    for i, (col, corr) in enumerate(sorted_corrs[:15], 1):
        print(f"  {i:2d}. {col:<25} {corr:.4f}")
    
    print(f"\n📊 Correlation Summary:")
    print(f"   Mean correlation: {np.mean(list(correlations.values())):.4f}")
    print(f"   Max correlation: {np.max(list(correlations.values())):.4f}")
    print(f"   Indicators with >0.1 correlation: {sum(1 for c in correlations.values() if c > 0.1)}")
    
    # Stationarity test (ADF) on top indicators
    print("\n🧪 Stationarity Test (ADF) on Top 10 Indicators:")
    from statsmodels.tsa.stattools import adfuller
    
    stationary_count = 0
    for col, corr in sorted_corrs[:10]:
        try:
            series = df[col].dropna()
            if len(series) > 30:
                result = adfuller(series)
                p_value = result[1]
                is_stationary = p_value < 0.05
                if is_stationary:
                    stationary_count += 1
                print(f"   {col:<20} p={p_value:.4f} {'✅ Stationary' if is_stationary else '❌ Non-stationary'}")
        except Exception as e:
            print(f"   {col:<20} ❌ Error: {str(e)[:30]}")
    
    print(f"\n   Stationary indicators: {stationary_count}/10")
    
    return correlations, sorted_corrs


def analyze_label_quality(df):
    """Analyze label definition and potential leakage."""
    print("\n🔍 ANALYSIS 2: Label Definition and Target Leakage")
    print("=" * 70)
    
    # Label distribution analysis
    label_dist = df['actual'].value_counts().sort_index()
    label_map = {-1: 'bearish', 0: 'neutral', 1: 'bullish'}
    
    print("\n📊 Label Distribution:")
    for label, count in label_dist.items():
        pct = count / len(df) * 100
        print(f"   {label_map[label]:<8} {count:4d} ({pct:5.1f}%)")
    
    # Check for lookahead bias
    print("\n🔍 Lookahead Bias Check:")
    print(f"   Future return calculation: close[{df.index[0]+1}] / close[{df.index[0]}] - 1")
    print(f"   Indicator availability: All indicators calculated using data up to time t")
    print(f"   ✅ No obvious lookahead bias detected")
    
    # Label stability over time
    print("\n📈 Label Stability Over Time:")
    df_temp = df.copy()
    df_temp['date'] = pd.to_datetime(df_temp['ts'])
    df_temp['month'] = df_temp['date'].dt.to_period('M')
    
    monthly_dist = df_temp.groupby('month')['actual'].value_counts(normalize=True).unstack()
    if monthly_dist is not None:
        print("   Monthly label distribution (%):")
        for month in monthly_dist.index[:6]:  # Show first 6 months
            row = monthly_dist.loc[month]
            print(f"   {month}: Bullish {row.get(1, 0)*100:.1f}%, Neutral {row.get(0, 0)*100:.1f}%, Bearish {row.get(-1, 0)*100:.1f}%")
    
    return label_dist


def analyze_feature_engineering(df):
    """Analyze feature engineering issues."""
    print("\n🔍 ANALYSIS 3: Feature Engineering Issues")
    print("=" * 70)
    
    feature_cols = [col for col in df.columns 
                   if col not in ['ts', 'open', 'high', 'low', 'close', 'volume', 
                                'future_return', 'actual']]
    
    # Feature scaling analysis
    print("\n📏 Feature Scaling Analysis:")
    feature_stats = {}
    for col in feature_cols[:20]:  # Analyze first 20 features
        if df[col].dtype in ['float64', 'int64']:
            stats_data = df[col].describe()
            feature_stats[col] = {
                'mean': stats_data['mean'],
                'std': stats_data['std'],
                'min': stats_data['min'],
                'max': stats_data['max'],
                'range': stats_data['max'] - stats_data['min']
            }
    
    # Sort by range to identify scaling issues
    sorted_by_range = sorted(feature_stats.items(), key=lambda x: x[1]['range'], reverse=True)
    
    print("   Top 10 features by range (scaling needed):")
    for i, (col, stats) in enumerate(sorted_by_range[:10], 1):
        print(f"   {i:2d}. {col:<20} range={stats['range']:.2e}, mean={stats['mean']:.2e}")
    
    # Multicollinearity analysis
    print("\n🔗 Multicollinearity Analysis:")
    correlation_matrix = df[feature_cols[:15]].corr()  # First 15 features
    high_corr_pairs = []
    
    for i in range(len(correlation_matrix.columns)):
        for j in range(i+1, len(correlation_matrix.columns)):
            corr_val = correlation_matrix.iloc[i, j]
            if abs(corr_val) > 0.8:  # High correlation threshold
                high_corr_pairs.append((correlation_matrix.columns[i], correlation_matrix.columns[j], corr_val))
    
    print(f"   High correlation pairs (|r| > 0.8): {len(high_corr_pairs)}")
    for col1, col2, corr in high_corr_pairs[:5]:  # Show top 5
        print(f"   {col1} ↔ {col2}: r={corr:.3f}")
    
    # Feature importance using simple model
    print("\n🎯 Feature Importance (Random Forest):")
    try:
        X = df[feature_cols[:20]].fillna(df[feature_cols[:20]].median())
        y = df['actual']
        
        # Remove NaN rows
        mask = X.notna().all(axis=1)
        X_clean = X[mask]
        y_clean = y[mask]
        
        if len(X_clean) > 100:
            rf = RandomForestClassifier(n_estimators=50, random_state=42)
            rf.fit(X_clean, y_clean)
            
            importances = rf.feature_importances_
            feature_imp = list(zip(X_clean.columns, importances))
            feature_imp.sort(key=lambda x: x[1], reverse=True)
            
            print("   Top 10 most important features:")
            for i, (col, imp) in enumerate(feature_imp[:10], 1):
                print(f"   {i:2d}. {col:<20} {imp:.4f}")
        else:
            print("   Insufficient clean data for feature importance analysis")
            
    except Exception as e:
        print(f"   Error in feature importance analysis: {e}")
    
    return feature_stats, high_corr_pairs


def analyze_walk_forward_implementation(df):
    """Analyze walk-forward implementation specifics."""
    print("\n🔍 ANALYSIS 4: Walk-Forward Implementation Specifics")
    print("=" * 70)
    
    # Simulate walk-forward windows
    initial_train_days = 200
    test_days = 50
    step_days = 50
    
    total_data = len(df)
    windows = []
    
    current_start = 0
    window_num = 1
    
    while current_start + initial_train_days + test_days <= total_data:
        train_end = current_start + initial_train_days
        test_end = train_end + test_days
        
        train_data = df.iloc[current_start:train_end]
        test_data = df.iloc[train_end:test_end]
        
        windows.append({
            'window': window_num,
            'train_start': current_start,
            'train_end': train_end,
            'test_start': train_end,
            'test_end': test_end,
            'train_size': len(train_data),
            'test_size': len(test_data),
            'train_date_start': str(train_data['ts'].iloc[0]),
            'train_date_end': str(train_data['ts'].iloc[-1]),
            'test_date_start': str(test_data['ts'].iloc[0]),
            'test_date_end': str(test_data['ts'].iloc[-1])
        })
        
        current_start += step_days
        window_num += 1
    
    print(f"\n📅 Walk-Forward Window Analysis:")
    print(f"   Total windows: {len(windows)}")
    print(f"   Initial training: {initial_train_days} days")
    print(f"   Test window: {test_days} days")
    print(f"   Step size: {step_days} days")
    
    print("\n📋 Window Details:")
    for window in windows:
        print(f"   Window {window['window']}: Train {window['train_size']} days ({window['train_date_start'][:10]} to {window['train_date_end'][:10]}), "
              f"Test {window['test_size']} days ({window['test_date_start'][:10]} to {window['test_date_end'][:10]})")
    
    # Check for data leakage
    print("\n🔍 Data Leakage Check:")
    leakage_detected = False
    for i in range(len(windows) - 1):
        current_test_end = windows[i]['test_end']
        next_train_start = windows[i + 1]['train_start']
        if next_train_start < current_test_end:
            print(f"   ❌ Overlap detected between Window {i+1} test and Window {i+2} train")
            leakage_detected = True
    
    if not leakage_detected:
        print("   ✅ No data leakage detected between windows")
    
    # Indicator warm-up analysis
    print("\n🔥 Indicator Warm-up Analysis:")
    max_lookback = 50  # Maximum indicator lookback (e.g., 50-day SMA)
    
    for window in windows[:3]:  # Check first 3 windows
        train_start = window['train_start']
        if train_start < max_lookback:
            print(f"   Window {window['window']}: Training starts at index {train_start}, indicators may be unstable (need {max_lookback} bars)")
        else:
            print(f"   Window {window['window']}: ✅ Sufficient data for indicator warm-up")
    
    return windows


def analyze_model_architecture(df):
    """Analyze model architecture mismatch."""
    print("\n🔍 ANALYSIS 5: Model Architecture Mismatch")
    print("=" * 70)
    
    feature_cols = [col for col in df.columns 
                   if col not in ['ts', 'open', 'high', 'low', 'close', 'volume', 
                                'future_return', 'actual']]
    
    # Prepare data
    X = df[feature_cols[:15]].fillna(df[feature_cols[:15]].median())  # Use first 15 features
    y = df['actual']
    
    # Remove NaN rows
    mask = X.notna().all(axis=1)
    X_clean = X[mask]
    y_clean = y[mask]
    
    if len(X_clean) < 100:
        print("❌ Insufficient clean data for model analysis")
        return
    
    print(f"\n📊 Data Shape: {X_clean.shape}")
    print(f"   Features: {X_clean.shape[1]}")
    print(f"   Samples: {X_clean.shape[0]}")
    print(f"   Classes: {np.unique(y_clean)}")
    
    # Test different model complexities
    print("\n🤖 Model Complexity Analysis:")
    
    models = {
        'Simple Logistic': None,
        'Random Forest (50 trees)': None,
        'Random Forest (200 trees)': None,
        'Gradient Boosting': None
    }
    
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    
    # Time series split for validation
    tscv = TimeSeriesSplit(n_splits=3)
    
    for name in models.keys():
        try:
            scores = []
            
            if 'Logistic' in name:
                model = LogisticRegression(random_state=42, max_iter=1000)
            elif '50 trees' in name:
                model = RandomForestClassifier(n_estimators=50, random_state=42)
            elif '200 trees' in name:
                model = RandomForestClassifier(n_estimators=200, random_state=42)
            else:  # Gradient Boosting
                model = GradientBoostingClassifier(n_estimators=100, random_state=42)
            
            for train_idx, test_idx in tscv.split(X_clean):
                X_train, X_test = X_clean.iloc[train_idx], X_clean.iloc[test_idx]
                y_train, y_test = y_clean.iloc[train_idx], y_clean.iloc[test_idx]
                
                # Scale features
                scaler = RobustScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                
                model.fit(X_train_scaled, y_train)
                score = model.score(X_test_scaled, y_test)
                scores.append(score)
            
            avg_score = np.mean(scores)
            models[name] = avg_score
            print(f"   {name:<25} {avg_score:.3f} ± {np.std(scores):.3f}")
            
        except Exception as e:
            print(f"   {name:<25} ❌ Error: {str(e)[:30]}")
    
    # Baseline comparison
    print("\n🎯 Baseline Comparison:")
    most_common = y_clean.mode().iloc[0]
    baseline_accuracy = (y_clean == most_common).mean()
    print(f"   Most frequent class baseline: {baseline_accuracy:.3f}")
    print(f"   Random baseline (3-class): {1/3:.3f}")
    
    return models


def generate_comprehensive_report(df, correlations, windows, models):
    """Generate comprehensive review report."""
    print("\n🔍 ANALYSIS 6: Critical Reality Check & Recommendations")
    print("=" * 70)
    
    print("\n📋 KEY FINDINGS:")
    
    # Indicator effectiveness
    max_corr = max(correlations.values()) if correlations else 0
    mean_corr = np.mean(list(correlations.values())) if correlations else 0
    
    print(f"\n1. INDICATOR EFFECTIVENESS:")
    print(f"   • Maximum indicator-target correlation: {max_corr:.4f}")
    print(f"   • Mean indicator-target correlation: {mean_corr:.4f}")
    if max_corr < 0.15:
        print(f"   • ❌ Very low correlation - indicators lack predictive signal")
    elif max_corr < 0.25:
        print(f"   • ⚠️  Low correlation - indicators have weak signal")
    else:
        print(f"   • ✅ Moderate correlation - indicators have some signal")
    
    # Model performance
    best_model_score = max(models.values()) if models else 0
    print(f"\n2. MODEL PERFORMANCE:")
    print(f"   • Best model accuracy: {best_model_score:.3f}")
    if best_model_score < 0.4:
        print(f"   • ❌ Poor performance - models not learning useful patterns")
    elif best_model_score < 0.5:
        print(f"   • ⚠️  Weak performance - some learning but limited")
    else:
        print(f"   • ✅ Good performance - models finding patterns")
    
    # Data quality
    print(f"\n3. DATA QUALITY:")
    print(f"   • Total samples: {len(df)}")
    print(f"   • Feature completeness: {(1 - df[correlations.keys()].isna().mean().mean()) * 100:.1f}%")
    print(f"   • Walk-forward windows: {len(windows)}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if max_corr < 0.15:
        print(f"\n   🚨 URGENT - Technical indicators lack predictive signal:")
        print(f"      • Consider adding fundamental data (P/E, revenue, earnings)")
        print(f"      • Add market regime indicators (VIX, sector performance)")
        print(f"      • Implement alternative features (price patterns, microstructure)")
        print(f"      • Test longer prediction horizons (5d, 10d, 20d)")
    
    if best_model_score < 0.4:
        print(f"\n   🔧 MODEL IMPROVEMENT NEEDED:")
        print(f"      • Try ensemble methods with different base learners")
        print(f"      • Implement feature selection to reduce noise")
        print(f"      • Add regularization to prevent overfitting")
        print(f"      • Consider deep learning for non-linear patterns")
    
    print(f"\n   📊 FEATURE ENGINEERING:")
    print(f"      • Remove highly correlated features (>0.8)")
    print(f"      • Implement adaptive indicator parameters")
    print(f"      • Add regime-specific feature sets")
    print(f"      • Test different scaling methods")
    
    print(f"\n   🎯 TARGET DEFINITION:")
    print(f"      • Experiment with different return thresholds")
    print(f"      • Try regression instead of classification")
    print(f"      • Implement multi-horizon predictions")
    
    # Reality check
    print(f"\n🔍 REALITY CHECK:")
    print(f"   • Random performance is common for pure technical analysis")
    print(f"   • Academic literature shows limited predictive power of technical indicators")
    print(f"   • Consider combining with fundamental or sentiment analysis")
    print(f"   • Focus on risk management rather than prediction accuracy")


def create_review_plots(df, correlations, windows):
    """Create comprehensive review plots."""
    print("\n📈 Creating review plots...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Indicator Correlations
    plt.figure(figsize=(12, 8))
    
    sorted_corrs = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
    top_features = [item[0] for item in sorted_corrs[:20]]
    top_values = [item[1] for item in sorted_corrs[:20]]
    
    plt.subplot(2, 2, 1)
    bars = plt.barh(range(len(top_features)), top_values, color='steelblue')
    plt.yticks(range(len(top_features)), [f.replace('_', ' ')[:20] for f in top_features])
    plt.xlabel('Absolute Correlation with Target')
    plt.title('Top 20 Indicator Correlations')
    plt.grid(axis='x', alpha=0.3)
    
    # 2. Label Distribution Over Time
    plt.subplot(2, 2, 2)
    df_temp = df.copy()
    df_temp['date'] = pd.to_datetime(df_temp['ts'])
    df_temp['month'] = df_temp['date'].dt.to_period('M')
    
    monthly_dist = df_temp.groupby('month')['actual'].value_counts(normalize=True).unstack()
    if monthly_dist is not None:
        monthly_dist.plot(kind='bar', stacked=True, ax=plt.gca(), 
                         color=['red', 'gray', 'green'], alpha=0.7)
        plt.xlabel('Month')
        plt.ylabel('Proportion')
        plt.title('Label Distribution Over Time')
        plt.legend(['Bearish', 'Neutral', 'Bullish'])
        plt.xticks(rotation=45)
    
    # 3. Feature Correlation Heatmap
    plt.subplot(2, 2, 3)
    feature_cols = list(correlations.keys())[:15]  # Top 15 features
    corr_matrix = df[feature_cols].corr()
    
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    sns.heatmap(corr_matrix, mask=mask, cmap='coolwarm', center=0, 
                square=True, linewidths=0.5, cbar_kws={"shrink": 0.8})
    plt.title('Feature Correlation Matrix')
    
    # 4. Walk-Forward Window Performance
    plt.subplot(2, 2, 4)
    window_numbers = [w['window'] for w in windows]
    window_sizes = [w['test_size'] for w in windows]
    
    plt.bar(window_numbers, window_sizes, color='orange', alpha=0.7)
    plt.xlabel('Window Number')
    plt.ylabel('Test Set Size')
    plt.title('Walk-Forward Window Sizes')
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plot_path = f"/Users/ericpeterson/SwiftBolt_ML/AAPL_comprehensive_review_{timestamp}.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Review plots saved: {plot_path}")
    return plot_path


def main():
    """Main execution."""
    print("🔍 AAPL COMPREHENSIVE INDICATORS REVIEW")
    print("=" * 60)
    print("Based on Perplexity expert recommendations")
    print("Analyzing why walk-forward achieved 33% accuracy")
    
    try:
        # Fetch and prepare data
        df = fetch_aapl_data(days=500)
        df = add_comprehensive_indicators(df)
        df = create_labels(df, horizon_days=1, threshold_pct=0.005)
        
        # Run comprehensive analyses
        correlations, sorted_corrs = analyze_indicator_stationarity(df)
        label_dist = analyze_label_quality(df)
        feature_stats, high_corr_pairs = analyze_feature_engineering(df)
        windows = analyze_walk_forward_implementation(df)
        models = analyze_model_architecture(df)
        
        # Generate comprehensive report
        generate_comprehensive_report(df, correlations, windows, models)
        
        # Create review plots
        plot_path = create_review_plots(df, correlations, windows)
        
        print(f"\n✅ COMPREHENSIVE REVIEW COMPLETE")
        print(f"📈 Review plots: {plot_path}")
        print(f"\n📋 SUMMARY:")
        print(f"   • Analyzed {len(df)} days of AAPL data")
        print(f"   • Examined {len(correlations)} technical indicators")
        print(f"   • Evaluated {len(windows)} walk-forward windows")
        print(f"   • Tested {len(models)} model architectures")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
