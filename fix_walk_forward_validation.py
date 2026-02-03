#!/usr/bin/env python3
"""
FIXED: Walk-Forward Validation for Regime Testing
Prevents overfitting by using proper time-series cross-validation
"""

import sys
from pathlib import Path
# Resolve src to ml/src when run from project root
_ml = Path(__file__).resolve().parent / "ml"
if _ml.exists():
    sys.path.insert(0, str(_ml))

import pandas as pd
import numpy as np
from typing import Dict, Optional


def walk_forward_validate(X: pd.DataFrame, y: pd.Series, 
                          min_train_size: int = 50,
                          test_size: int = 5) -> Dict:
    """
    Walk-forward validation for time series
    
    This prevents data leakage by:
    1. Always training on past data only
    2. Testing on multiple future windows
    3. Averaging results across windows
    
    Args:
        X: Features (sorted by time)
        y: Target (sorted by time)
        min_train_size: Minimum training samples
        test_size: Size of each test window
    
    Returns:
        Dictionary with accuracy and details
    """
    from src.models.xgboost_forecaster import XGBoostForecaster
    
    if len(X) < min_train_size + test_size:
        return None
    
    # Calculate number of windows
    n_windows = (len(X) - min_train_size) // test_size
    
    if n_windows < 2:
        return None
    
    accuracies = []
    predictions_all = []
    actuals_all = []
    
    for i in range(n_windows):
        # Expanding window: train on all past data
        train_end = min_train_size + (i * test_size)
        test_start = train_end
        test_end = test_start + test_size
        
        if test_end > len(X):
            break
        
        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]
        X_test = X.iloc[test_start:test_end]
        y_test = y.iloc[test_start:test_end]
        
        # Train model
        model = XGBoostForecaster()
        model.train(X_train, y_train)
        
        # Predict
        y_pred_proba = model.predict_proba(X_test)
        y_pred = (y_pred_proba[:, 1] > 0.5).astype(int)
        
        # Calculate accuracy for this window
        window_acc = (y_pred == y_test.values).mean()
        accuracies.append(window_acc)
        
        predictions_all.extend(y_pred)
        actuals_all.extend(y_test.values)
    
    if len(accuracies) == 0:
        return None
    
    # Overall metrics
    overall_acc = (np.array(predictions_all) == np.array(actuals_all)).mean()
    
    return {
        'accuracy': overall_acc,
        'accuracy_std': np.std(accuracies),
        'n_windows': len(accuracies),
        'window_accuracies': accuracies,
        'total_test_samples': len(predictions_all)
    }


# ============================================================================
# UPDATED evaluate_stock_in_regime WITH WALK-FORWARD
# ============================================================================

def evaluate_stock_in_regime_fixed(
    symbol: str,
    regime_name: str,
    regime: dict,
    category_config: dict,
    df_full: pd.DataFrame = None
) -> dict:
    """
    FIXED VERSION: Uses walk-forward validation
    """
    from src.data.supabase_db import SupabaseDatabase
    from src.data.data_cleaner import DataCleaner
    from src.models.xgboost_forecaster import XGBoostForecaster
    import pandas as pd
    import numpy as np
    
    horizon = category_config['horizon']
    threshold = category_config['threshold']
    
    # Load data if not provided
    if df_full is None:
        db = SupabaseDatabase()
        df_full = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=2000)
        
        if df_full is None:
            return None
        
        df_full = DataCleaner.clean_all(df_full, verbose=False)
    
    # Filter to regime
    df_full['ts'] = pd.to_datetime(df_full['ts'])
    start = pd.to_datetime(regime['start'])
    end = pd.to_datetime(regime['end'])
    df = df_full[(df_full['ts'] >= start) & (df_full['ts'] <= end)].copy()
    
    if len(df) < 100:  # Need at least 100 bars for walk-forward
        return None
    
    try:
        # Prepare features
        forecaster = XGBoostForecaster()
        X, y = forecaster.prepare_training_data_binary(
            df,
            horizon_days=horizon,
            threshold_pct=threshold,
        )
        
        if X is None or len(X) < 60:  # Need 60+ for walk-forward
            return None
        
        # Clean features
        X = X.replace([np.inf, -np.inf], np.nan)
        nan_pct = X.isna().mean()
        valid_cols = nan_pct[nan_pct < 0.5].index
        X = X[valid_cols].fillna(0)
        
        if X.shape[1] == 0:
            return None
        
        # Use walk-forward validation
        result = walk_forward_validate(X, y, min_train_size=50, test_size=5)
        
        if result is None:
            return None
        
        return {
            'accuracy': result['accuracy'],
            'accuracy_std': result['accuracy_std'],
            'samples': len(X),
            'features': X.shape[1],
            'test_samples': result['total_test_samples'],
            'n_windows': result['n_windows'],
            'positive_rate': y.mean(),
            'bars': len(df)
        }
        
    except Exception as e:
        print(f"    ❌ Error: {str(e)[:100]}")
        return None


# ============================================================================
# HOW TO USE THIS FIX
# ============================================================================

print("""
╔════════════════════════════════════════════════════════════════════════╗
║                  WALK-FORWARD VALIDATION FIX                           ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  PROBLEM: Your 80/20 split with tiny regimes causes overfitting       ║
║                                                                        ║
║  SOLUTION: Walk-forward validation with multiple windows              ║
║                                                                        ║
║  How it works:                                                        ║
║  1. Train on bars 1-50, test on bars 51-55                           ║
║  2. Train on bars 1-55, test on bars 56-60                           ║
║  3. Train on bars 1-60, test on bars 61-65                           ║
║  ... continue for entire regime                                       ║
║  4. Average accuracy across all windows                               ║
║                                                                        ║
║  Benefits:                                                            ║
║  - Larger test set (50+ bars vs 15 bars)                             ║
║  - Multiple validation windows reduce variance                        ║
║  - Always tests on future data only                                   ║
║  - More realistic accuracy estimates                                  ║
║                                                                        ║
║  TO APPLY:                                                            ║
║  1. Copy evaluate_stock_in_regime_fixed to test_regimes_fixed.py     ║
║  2. Replace existing evaluate_stock_in_regime function                ║
║  3. Re-run: python test_regimes_fixed.py                             ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
""")
