#!/usr/bin/env python3
"""
Quick fix for NaN features in prepare_training_data_binary

Add this to your XGBoostForecaster.prepare_training_data_binary method
AFTER creating X and y, but BEFORE returning them.
"""

import pandas as pd
import numpy as np

def clean_features(X: pd.DataFrame, y: pd.Series) -> tuple:
    """
    Clean features to handle NaN and ensure quality
    
    Add this RIGHT BEFORE the return statement in prepare_training_data_binary
    """
    # Step 1: Replace Inf with NaN
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Step 2: Drop columns with >50% NaN
    nan_threshold = 0.5
    nan_pct = X.isna().mean()
    valid_cols = nan_pct[nan_pct < nan_threshold].index
    
    dropped_cols = X.columns.difference(valid_cols)
    if len(dropped_cols) > 0:
        print(f"Dropping {len(dropped_cols)} features with >50% NaN: {list(dropped_cols)[:5]}...")
    
    X = X[valid_cols]
    
    # Step 3: Fill remaining NaN with 0
    # (This is safe after dropping mostly-NaN columns)
    X = X.fillna(0)
    
    # Step 4: Ensure all numeric
    for col in X.columns:
        if X[col].dtype == 'object':
            print(f"Converting non-numeric column: {col}")
            X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    
    return X, y


# ===========================================================================
# WHERE TO ADD THIS IN YOUR CODE
# ===========================================================================

"""
In src/models/xgboost_forecaster.py, modify prepare_training_data_binary:

def prepare_training_data_binary(self, df, horizon_days=5, threshold_pct=0.015):
    # ... your existing code to create X and y ...
    
    # ADD THIS RIGHT BEFORE RETURN:
    # Clean features
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Drop columns with >50% NaN
    nan_threshold = 0.5
    nan_pct = X.isna().mean()
    valid_cols = nan_pct[nan_pct < nan_threshold].index
    X = X[valid_cols]
    
    # Fill remaining NaN with 0
    X = X.fillna(0)
    
    # Ensure all numeric
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    
    return X, y
"""

print("""
╔════════════════════════════════════════════════════════════════════════╗
║                    NaN FEATURE FIX                                     ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  Add this code to your prepare_training_data_binary method:           ║
║                                                                        ║
║  1. Open: src/models/xgboost_forecaster.py                           ║
║  2. Find: def prepare_training_data_binary(...)                      ║
║  3. Add the cleaning code RIGHT BEFORE the return statement          ║
║                                                                        ║
║  This will:                                                           ║
║  - Replace Inf with NaN                                              ║
║  - Drop features with >50% NaN                                       ║
║  - Fill remaining NaN with 0                                         ║
║  - Convert any string columns to numeric                             ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
""")
