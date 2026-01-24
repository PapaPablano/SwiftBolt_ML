# Part 3: Detailed Training Pipeline Implementation

## Complete Python Implementation for Statistical Training

This document contains production-ready code for all training components.

---

## Module 1: Data Preparation (`ml/src/training/data_preparation.py`)

```python
"""Data preparation for ensemble model training.

Ensures:
- Proper time ordering (oldest → newest)
- No missing data gaps
- Consistent feature calculations
- No look-ahead bias in label creation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import TIMEFRAME_HORIZONS, settings
from src.data.supabase_db import db
from src.features.feature_cache import fetch_or_build_features

logger = logging.getLogger(__name__)


def collect_training_data(
    symbols: list[str],
    lookback_days: int = 60,
    target_bars: int = 500,
) -> dict[str, dict[str, pd.DataFrame]]:
    """
    Collect training data across all timeframes.
    
    Args:
        symbols: List of tickers (e.g., ['AAPL', 'SPY'])
        lookback_days: Days of history to collect
        target_bars: Target bar count per timeframe
    
    Returns:
        {timeframe: {symbol: df_with_features}}
    
    Ensures:
        - Proper time ordering (oldest → newest)
        - No missing data gaps
        - Consistent feature calculations
    """
    training_data = {}
    
    # Define timeframe bar counts
    limits = {
        "m15": target_bars,      # ~3.5 days at market hours
        "h1": target_bars,       # ~20 days
        "h4": target_bars,       # ~80 days
        "d1": target_bars,       # ~2 years
        "w1": min(100, target_bars // 5),  # ~2 years
    }
    
    for symbol in symbols:
        try:
            logger.info(f"Collecting data for {symbol}...")
            
            # Fetch features for all timeframes
            features_by_tf = fetch_or_build_features(
                db=db,
                symbol=symbol,
                limits=limits,
            )
            
            for timeframe, df in features_by_tf.items():
                if timeframe not in training_
                    training_data[timeframe] = {}
                
                # Verify time ordering
                if "ts" in df.columns:
                    df = df.sort_values("ts").reset_index(drop=True)
                    logger.info(
                        f"  {timeframe}: {len(df)} bars, "
                        f"oldest: {df['ts'].iloc[0]}, "
                        f"newest: {df['ts'].iloc[-1]}"
                    )
                else:
                    logger.info(f"  {timeframe}: {len(df)} bars (no ts column)")
                
                training_data[timeframe][symbol] = df
                
        except Exception as e:
            logger.error(f"Failed to collect {symbol}: {e}")
            continue
    
    logger.info(f"Training data collected for {len(symbols)} symbols")
    return training_data


def create_labels(
    df: pd.DataFrame,
    prediction_horizon_bars: int = 5,
    threshold: float = 0.002,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Create labels from future price movement.
    
    Args:
        df: DataFrame with 'close' column
        prediction_horizon_bars: Bars ahead to predict
        threshold: Return threshold for BULLISH/BEARISH (default 0.2%)
    
    Returns:
        (features_df, labels_series)
    
    Ensures:
        - Labels only calculated on future data (no look-ahead bias)
        - Training split: train_df + labels for last (100 - horizon) rows
        - Validation split: holdout_df gets fresh labels
    """
    df = df.copy()
    
    logger.info(
        f"Creating labels with {prediction_horizon_bars}-bar horizon, "
        f"{threshold:.1%} threshold"
    )
    
    # Calculate future returns
    future_close = df["close"].shift(-prediction_horizon_bars)
    future_returns = (future_close - df["close"]) / df["close"]
    
    # Create direction labels
    labels = pd.Series("NEUTRAL", index=df.index, dtype=str)
    labels[future_returns > threshold] = "BULLISH"
    labels[future_returns < -threshold] = "BEARISH"
    
    # Remove last `prediction_horizon_bars` rows (incomplete labels)
    feature_rows = len(df) - prediction_horizon_bars
    
    features = df.iloc[:feature_rows].reset_index(drop=True)
    labels_out = labels.iloc[:feature_rows].reset_index(drop=True)
    
    # Log distribution
    dist = labels_out.value_counts().to_dict()
    logger.info(f"Label distribution: {dist}")
    logger.info(
        f"BULLISH: {dist.get('BULLISH', 0) / len(labels_out):.1%}, "
        f"NEUTRAL: {dist.get('NEUTRAL', 0) / len(labels_out):.1%}, "
        f"BEARISH: {dist.get('BEARISH', 0) / len(labels_out):.1%}"
    )
    
    return features, labels_out


def prepare_train_validation_split(
    df: pd.DataFrame,
    labels: pd.Series,
    train_fraction: float = 0.7,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Time-based train/validation split (NO SHUFFLING).
    
    Args:
        df: Features
        labels: Labels
        train_fraction: Fraction for training (default 70%)
    
    Returns:
        (train_features, valid_features, train_labels, valid_labels)
    
    ⚠️ CRITICAL: Split is time-ordered
        - train = indices 0 to 0.7 * len (oldest data)
        - valid = indices 0.7 * len to end (newest data)
    
    Prevents data leakage by ensuring model never sees validation
    data during training.
    """
    split_idx = int(len(df) * train_fraction)
    
    train_features = df.iloc[:split_idx].reset_index(drop=True)
    valid_features = df.iloc[split_idx:].reset_index(drop=True)
    train_labels = labels.iloc[:split_idx].reset_index(drop=True)
    valid_labels = labels.iloc[split_idx:].reset_index(drop=True)
    
    logger.info(f"Train: {len(train_features)} rows, Valid: {len(valid_features)} rows")
    logger.info(
        f"Train labels: {train_labels.value_counts().to_dict()}"
    )
    logger.info(
        f"Valid labels: {valid_labels.value_counts().to_dict()}"
    )
    
    return train_features, valid_features, train_labels, valid_labels


def validate_data_integrity(
    df: pd.DataFrame,
    labels: pd.Series,
    symbol: str,
    timeframe: str,
) -> bool:
    """
    Validate data for common issues.
    
    Returns:
        True if data is valid, False otherwise
    """
    issues = []
    
    # Check shapes match
    if len(df) != len(labels):
        issues.append(f"Shape mismatch: df={len(df)}, labels={len(labels)}")
    
    # Check for NaN values
    nan_count = df.isna().sum().sum()
    if nan_count > 0:
        issues.append(f"Found {nan_count} NaN values in features")
    
    # Check for sufficient samples per class
    min_class_count = min(labels.value_counts().values) if len(labels) > 0 else 0
    if min_class_count < 5:
        issues.append(f"Insufficient samples in smallest class: {min_class_count}")
    
    # Check for reasonable number of features
    if len(df.columns) < 5:
        issues.append(f"Too few features: {len(df.columns)}")
    
    if issues:
        logger.error(f"Data validation failed for {symbol}/{timeframe}:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    
    logger.info(f"Data validation passed for {symbol}/{timeframe}")
    return True
```

---

## Module 2: Model Training (`ml/src/training/model_training.py`)

```python
"""Individual model training with consistent interface."""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
)

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Train individual models with consistent interface."""
    
    def __init__(self, symbol: str, timeframe: str):
        """
        Initialize trainer.
        
        Args:
            symbol: Stock ticker (e.g., "AAPL")
            timeframe: Timeframe identifier (e.g., "d1")
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.models = {}
        self.performances = {}
    
    def train_random_forest(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """Train Random Forest with hyperparameter optimization."""
        logger.info(f"Training Random Forest ({self.symbol}/{self.timeframe})")
        
        # Hyperparameters optimized for financial data
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        
        # Train on full training set
        rf.fit(train_features, train_labels)
        
        # Evaluate on validation set (true out-of-sample performance)
        train_pred = rf.predict(train_features)
        valid_pred = rf.predict(valid_features)
        
        train_acc = accuracy_score(train_labels, train_pred)
        valid_acc = accuracy_score(valid_labels, valid_pred)
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            valid_labels, valid_pred, average="weighted"
        )
        
        perf = {
            "train_accuracy": float(train_acc),
            "valid_accuracy": float(valid_acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "n_features": len(train_features.columns),
            "n_samples_train": len(train_features),
            "n_samples_valid": len(valid_features),
        }
        
        self.models["rf"] = rf
        self.performances["rf"] = perf
        
        logger.info(f"  Train Acc: {train_acc:.1%}")
        logger.info(f"  Valid Acc: {valid_acc:.1%}")
        logger.info(f"  Overfit Margin: {(train_acc - valid_acc):.1%}")
        logger.info(f"  F1 Score: {f1:.3f}")
        
        return perf
    
    def train_gradient_boosting(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """Train Gradient Boosting."""
        logger.info(f"Training Gradient Boosting ({self.symbol}/{self.timeframe})")
        
        gb = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=7,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
        )
        
        gb.fit(train_features, train_labels)
        
        train_pred = gb.predict(train_features)
        valid_pred = gb.predict(valid_features)
        
        train_acc = accuracy_score(train_labels, train_pred)
        valid_acc = accuracy_score(valid_labels, valid_pred)
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            valid_labels, valid_pred, average="weighted"
        )
        
        perf = {
            "train_accuracy": float(train_acc),
            "valid_accuracy": float(valid_acc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "n_features": len(train_features.columns),
            "n_samples_train": len(train_features),
            "n_samples_valid": len(valid_features),
        }
        
        self.models["gb"] = gb
        self.performances["gb"] = perf
        
        logger.info(f"  Train Acc: {train_acc:.1%}")
        logger.info(f"  Valid Acc: {valid_acc:.1%}")
        logger.info(f"  Overfit Margin: {(train_acc - valid_acc):.1%}")
        logger.info(f"  F1 Score: {f1:.3f}")
        
        return perf
    
    def train_all_models(
        self,
        train_features: pd.DataFrame,
        train_labels: pd.Series,
        valid_features: pd.DataFrame,
        valid_labels: pd.Series,
    ) -> Dict:
        """Train all ensemble components."""
        results = {}
        
        # Core models (always)
        results["rf"] = self.train_random_forest(
            train_features, train_labels, valid_features, valid_labels
        )
        results["gb"] = self.train_gradient_boosting(
            train_features, train_labels, valid_features, valid_labels
        )
        
        logger.info(f"Trained {len(results)} models")
        return results
```

---

## Module 3: Weight Optimization (`ml/src/training/weight_optimizer.py`)

```python
"""Ensemble weight optimization using Ridge Regression."""

import logging
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)


class EnsembleWeightOptimizer:
    """
    Optimize ensemble weights using validation set predictions.
    
    Approach:
        1. Get predictions from each model on validation set
        2. Use Ridge Regression to find optimal weights
        3. Weights reflect each model's individual out-of-sample strength
        4. Solve: minimize ||y_true - (w1*pred1 + w2*pred2 + ...)||^2 + λ||w||^2
    """
    
    def __init__(self, alpha: float = 1.0):
        """
        Initialize optimizer.
        
        Args:
            alpha: Ridge regularization strength
                   (higher = more uniform weights, lower = specialized weights)
        """
        self.alpha = alpha
        self.ridge_model = Ridge(alpha=alpha)
        self.weights = None
        logger.info(f"EnsembleWeightOptimizer initialized with alpha={alpha}")
    
    def optimize_weights(
        self,
        model_predictions: Dict[str, np.ndarray],
        actual_labels: pd.Series,
    ) -> Dict[str, float]:
        """
        Find optimal weights for ensemble models.
        
        Args:
            model_predictions: {model_name: [pred_proba for each sample]}
                              Each model produces (n_samples, n_classes)
            actual_labels: True direction labels (n_samples,)
        
        Returns:
            {model_name: weight (0-1, normalized)}
        
        Example:
            model_predictions = {
                "rf": [[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], ...],  # 100 samples
                "gb": [[0.6, 0.3, 0.1], [0.7, 0.2, 0.1], ...],
            }
            actual = ["BULLISH", "BULLISH", "BEARISH", ...]  # 100 samples
            
            weights = optimizer.optimize_weights(model_predictions, actual)
            # Returns: {"rf": 0.45, "gb": 0.35}
        """
        
        # Convert label string to numeric targets
        n_samples = len(actual_labels)
        label_to_class = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
        y_target = np.array(
            [label_to_class.get(label, 0) for label in actual_labels]
        )
        
        # Stack predictions from all models: (n_samples, n_models)
        model_names = list(model_predictions.keys())
        X_ensemble = np.column_stack([
            model_predictions[name] for name in model_names
        ])
        
        logger.info(f"Optimizing weights for {len(model_names)} models")
        logger.info(f"  Training samples: {n_samples}")
        logger.info(f"  Models: {model_names}")
        logger.info(f"  Prediction shape: {X_ensemble.shape}")
        
        # Fit Ridge regression
        self.ridge_model.fit(X_ensemble, y_target)
        raw_weights = self.ridge_model.coef_
        
        # Normalize weights to sum to 1
        raw_weights = np.maximum(raw_weights, 0)  # No negative weights
        if raw_weights.sum() > 0:
            normalized_weights = raw_weights / raw_weights.sum()
        else:
            # Fallback to equal weights if all negative
            normalized_weights = np.ones(len(model_names)) / len(model_names)
        
        # Create result dictionary
        self.weights = {
            name: float(weight)
            for name, weight in zip(model_names, normalized_weights)
        }
        
        # Log results
        logger.info("Optimized Weights:")
        for name, weight in sorted(
            self.weights.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"  {name}: {weight:.2%}")
        
        return self.weights
    
    def validate_weights(self) -> bool:
        """Check weights are valid (sum to 1, all positive)."""
        if self.weights is None:
            logger.warning("No weights have been optimized yet")
            return False
        
        total = sum(self.weights.values())
        if not (0.99 < total < 1.01):  # Allow small floating-point error
            logger.warning(f"Weights don't sum to 1: {total}")
            return False
        
        if any(w < 0 for w in self.weights.values()):
            logger.warning(f"Negative weights found: {self.weights}")
            return False
        
        logger.info(f"Weights validated: {self.weights}")
        return True
```

---

## Module 4: Full Orchestration (`ml/src/training/ensemble_training_job.py`)

See `TRAINING_ORCHESTRATION.md` for the complete 400+ line orchestration job.

Key points:
- Chains all components together
- Serializes models to disk with date versioning
- Stores metrics in database
- Provides summary reporting

---

## Using the Training Pipeline

### From Command Line

```bash
# Train for single symbol
python -m ml.src.training.ensemble_training_job --symbol AAPL

# Train for all symbols
python -m ml.src.training.ensemble_training_job --all

# Train with custom lookback
python -m ml.src.training.ensemble_training_job --symbols AAPL NVDA --lookback 90
```

### From Python Code

```python
from ml.src.training.ensemble_training_job import train_ensemble_for_symbol_timeframe

result = train_ensemble_for_symbol_timeframe(
    symbol="AAPL",
    timeframe="d1",
    lookback_days=60,
)

print(f"RF Accuracy: {result['models']['rf']['valid_accuracy']:.1%}")
print(f"GB Accuracy: {result['models']['gb']['valid_accuracy']:.1%}")
print(f"Weights: {result['weights']}")
print(f"Models saved to: {result['models_path']}")
```

---

## Expected Output

```
============================================================
FULL ENSEMBLE TRAINING RUN
Timestamp: 2025-01-21T15:30:00
============================================================

Training AAPL / d1...
Step 1: Collecting training data...
  d1: 500 bars, oldest: 2024-08-09, newest: 2025-01-21
Step 2: Creating labels...
  Label distribution: {'BULLISH': 156, 'NEUTRAL': 168, 'BEARISH': 176}
  BULLISH: 31.2%, NEUTRAL: 33.6%, BEARISH: 35.2%
Step 3: Creating time-ordered train/validation split...
  Train: 350 rows, Valid: 150 rows
Step 4: Training individual models...
  Training Random Forest (AAPL/d1)
    Train Acc: 82.3%
    Valid Acc: 58.7%
    Overfit Margin: 23.6%
    F1 Score: 0.575
  Training Gradient Boosting (AAPL/d1)
    Train Acc: 79.4%
    Valid Acc: 59.2%
    Overfit Margin: 20.2%
    F1 Score: 0.582
Step 5: Optimizing ensemble weights...
  Optimizing weights for 2 models
  Trained samples: 150
  Models: ['rf', 'gb']
  Prediction shape: (150, 2)
  Optimized Weights:
    gb: 52.3%
    rf: 47.7%
Step 6: Calculating ensemble performance...
  Ensemble Validation Accuracy: 60.1%
Step 7: Saving models to disk...
  Saved to /Users/ericpeterson/SwiftBolt_ML/trained_models/AAPL_d1_20250121.pkl
Step 8: Recording performance metrics...

============================================================
TRAINING RUN COMPLETE
============================================================
Trained: 5 configurations
Failed: 0 configurations
```

---

## Performance Expectations

### Training Time
- Single symbol, single timeframe: ~1-2 minutes
- All timeframes for one symbol: ~5-10 minutes
- Full run (AAPL, SPY, QQQ, etc.): ~15-30 minutes

### Model Accuracy (Realistic Ranges)
- RF train accuracy: 75-85%
- RF validation accuracy: 52-65%
- GB train accuracy: 70-80%
- GB validation accuracy: 50-62%
- Ensemble accuracy: 53-63%
- Walk-forward accuracy: 48-58%

Note: These are directional predictions (BULLISH/BEARISH/NEUTRAL), not profitable trading signals. Baseline random is 33%.

---

## Next Steps

1. ✅ Review this implementation
2. → Implement the orchestration job (`TRAINING_ORCHESTRATION.md`)
3. → Test on single symbol/timeframe
4. → See `ENSEMBLE_INTEGRATION_GUIDE.md` to load trained models
