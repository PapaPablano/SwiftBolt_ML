#!/usr/bin/env python3
"""
Regime-Specific Ensemble Model

This module implements a 3-tier regime-specific ensemble that trains separate
XGBoost models for LOW, MEDIUM, and HIGH volatility regimes. Each model is
optimized for its specific market conditions.
"""

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from sklearn.metrics import mean_absolute_error, mean_squared_error
import logging

logger = logging.getLogger(__name__)


class RegimeSpecificEnsemble:
    """
    Ensemble of XGBoost models trained on different volatility regimes.
    
    This class manages three separate XGBoost models:
    - LOW: For low volatility periods (stable markets)
    - MEDIUM: For medium volatility periods (normal market conditions)  
    - HIGH: For high volatility periods (crisis/volatile markets)
    """
    
    def __init__(self, model_dir: str = "models/regime_specific"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.models = {
            'LOW': None,
            'MEDIUM': None, 
            'HIGH': None
        }
        
        self.regime_thresholds = {
            'LOW': 0.33,      # Bottom 33% of volatility
            'MEDIUM': 0.67,   # Middle 33% of volatility
            'HIGH': 1.0       # Top 33% of volatility
        }
        
        self.feature_columns = None
        self.is_trained = False
        
    def detect_volatility_regime(self, data: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        Detect volatility regime for each data point using rolling volatility.
        
        Args:
            data: DataFrame with OHLC data
            window: Rolling window for volatility calculation
            
        Returns:
            Series with regime labels ('LOW', 'MEDIUM', 'HIGH')
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
            
        # Calculate rolling volatility
        returns = data['close'].pct_change().dropna()
        volatility = returns.rolling(window=window, min_periods=window//2).std()
        
        # Handle NaN values
        volatility = volatility.fillna(volatility.median())
        
        # Calculate percentiles for regime classification
        vol_33 = volatility.quantile(0.33)
        vol_67 = volatility.quantile(0.67)
        
        # Classify regimes
        regime = pd.Series(index=volatility.index, dtype='object')
        regime[volatility <= vol_33] = 'LOW'
        regime[(volatility > vol_33) & (volatility <= vol_67)] = 'MEDIUM'
        regime[volatility > vol_67] = 'HIGH'
        
        return regime
    
    def create_directional_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create enhanced directional features for regime-specific training."""
        features = pd.DataFrame(index=df.index)
        
        # KDJ crossover signals
        if 'close_kdj_j' in df.columns and 'close_kdj_d' in df.columns:
            features['kdj_j_above_d'] = (df['close_kdj_j'] > df['close_kdj_d']).astype(int)
            features['kdj_j_cross_d_up'] = (
                (df['close_kdj_j'] > df['close_kdj_d']) & 
                (df['close_kdj_j'].shift(1) <= df['close_kdj_d'].shift(1))
            ).astype(int)
            features['kdj_j_cross_d_down'] = (
                (df['close_kdj_j'] < df['close_kdj_d']) & 
                (df['close_kdj_j'].shift(1) >= df['close_kdj_d'].shift(1))
            ).astype(int)
        
        # MACD momentum
        if 'close_macd' in df.columns:
            features['macd_positive'] = (df['close_macd'] > 0).astype(int)
            features['macd_acceleration'] = df['close_macd'].diff()
            if 'close_macd_signal' in df.columns:
                features['macd_cross_signal'] = (
                    (df['close_macd'] > df['close_macd_signal']) & 
                    (df['close_macd'].shift(1) <= df['close_macd_signal'].shift(1))
                ).astype(int)
        
        # Price momentum
        if 'close_ma_5' in df.columns and 'close_ma_20' in df.columns:
            features['price_above_ma20'] = (df['close'] > df['close_ma_20']).astype(int)
            features['ma_5_above_ma_20'] = (df['close_ma_5'] > df['close_ma_20']).astype(int)
            features['ma_crossover'] = (
                (df['close_ma_5'] > df['close_ma_20']) & 
                (df['close_ma_5'].shift(1) <= df['close_ma_20'].shift(1))
            ).astype(int)
        
        # Volatility regime features
        vol_5 = df['close'].pct_change().rolling(5).std()
        vol_20 = df['close'].pct_change().rolling(20).std()
        features['high_volatility'] = (vol_5 > 1.5 * vol_20).astype(int)
        features['vol_ratio'] = vol_5 / vol_20
        
        # Price change features
        features['price_change_1'] = df['close'].pct_change(1)
        features['price_change_5'] = df['close'].pct_change(5)
        features['price_change_10'] = df['close'].pct_change(10)
        
        # Volume features
        if 'volume' in df.columns:
            features['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            features['volume_spike'] = (df['volume'] > 2 * df['volume'].rolling(20).mean()).astype(int)
        
        return features
    
    def prepare_training_data(self, data: pd.DataFrame, target_col: str = 'target') -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Prepare training data with regime labels and features.
        
        Args:
            data: Input DataFrame with OHLC data
            target_col: Name of target column
            
        Returns:
            Tuple of (features_df, target_series, regime_series)
        """
        # Detect regimes
        regime_series = self.detect_volatility_regime(data)
        
        # Create directional features
        directional_features = self.create_directional_features(data)
        
        # Combine with original features
        feature_cols = [col for col in data.columns if col not in ['timestamp', target_col, 'time']]
        features_df = pd.concat([data[feature_cols], directional_features], axis=1)
        
        # Store feature columns for later use
        self.feature_columns = features_df.columns.tolist()
        
        # Align all series
        common_index = features_df.index.intersection(regime_series.index).intersection(data[target_col].index)
        features_df = features_df.loc[common_index]
        target_series = data[target_col].loc[common_index]
        regime_series = regime_series.loc[common_index]
        
        return features_df, target_series, regime_series
    
    def train_regime_model(self, regime: str, X: pd.DataFrame, y: pd.Series, 
                          regime_mask: pd.Series) -> xgb.XGBRegressor:
        """
        Train XGBoost model for a specific regime.
        
        Args:
            regime: Regime name ('LOW', 'MEDIUM', 'HIGH')
            X: Feature matrix
            y: Target values
            regime_mask: Boolean mask for regime data
            
        Returns:
            Trained XGBoost model
        """
        # Filter data for this regime
        regime_data = X[regime_mask]
        regime_targets = y[regime_mask]
        
        if len(regime_data) < 10:
            logger.warning(f"Insufficient data for {regime} regime: {len(regime_data)} samples")
            return None
        
        logger.info(f"Training {regime} regime model with {len(regime_data)} samples")
        
        # Regime-specific hyperparameters
        regime_params = {
            'LOW': {
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 200,
                'min_child_weight': 3,
                'reg_alpha': 0.1,
                'reg_lambda': 1.0
            },
            'MEDIUM': {
                'max_depth': 8,
                'learning_rate': 0.15,
                'n_estimators': 250,
                'min_child_weight': 2,
                'reg_alpha': 0.05,
                'reg_lambda': 1.5
            },
            'HIGH': {
                'max_depth': 10,
                'learning_rate': 0.2,
                'n_estimators': 300,
                'min_child_weight': 1,
                'reg_alpha': 0.0,
                'reg_lambda': 2.0
            }
        }
        
        # Create and train model
        model = xgb.XGBRegressor(
            objective='reg:squarederror',
            random_state=42,
            n_jobs=-1,
            **regime_params[regime]
        )
        
        model.fit(regime_data, regime_targets)
        
        return model
    
    def train_ensemble(self, data: pd.DataFrame, target_col: str = 'target') -> Dict[str, float]:
        """
        Train all regime-specific models.
        
        Args:
            data: Training data with OHLC and target columns
            target_col: Name of target column
            
        Returns:
            Dictionary with training metrics for each regime
        """
        logger.info("Starting regime-specific ensemble training")
        
        # Prepare training data
        X, y, regimes = self.prepare_training_data(data, target_col)
        
        training_metrics = {}
        
        # Train models for each regime
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            regime_mask = (regimes == regime)
            
            if regime_mask.sum() == 0:
                logger.warning(f"No data found for {regime} regime")
                continue
                
            # Train model
            model = self.train_regime_model(regime, X, y, regime_mask)
            
            if model is not None:
                self.models[regime] = model
                
                # Calculate training metrics
                regime_data = X[regime_mask]
                regime_targets = y[regime_mask]
                predictions = model.predict(regime_data)
                
                mae = mean_absolute_error(regime_targets, predictions)
                rmse = np.sqrt(mean_squared_error(regime_targets, predictions))
                
                # Directional accuracy
                pred_direction = np.sign(np.diff(predictions))
                true_direction = np.sign(np.diff(regime_targets))
                directional_acc = np.mean(pred_direction == true_direction) * 100
                
                training_metrics[regime] = {
                    'samples': len(regime_data),
                    'mae': mae,
                    'rmse': rmse,
                    'directional_accuracy': directional_acc
                }
                
                logger.info(f"{regime} regime: {len(regime_data)} samples, MAE: {mae:.3f}, "
                          f"Dir Acc: {directional_acc:.1f}%")
                
                # Save model
                model_path = self.model_dir / f"xgboost_{regime.lower()}_volatility.pkl"
                joblib.dump(model, model_path)
                logger.info(f"Saved {regime} model to {model_path}")
        
        self.is_trained = True
        return training_metrics
    
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """
        Make predictions using the appropriate regime-specific model.
        
        Args:
            data: Input data with features
            
        Returns:
            Predictions array
        """
        if not self.is_trained:
            raise ValueError("Ensemble must be trained before making predictions")
        
        # Detect regimes for input data
        regimes = self.detect_volatility_regime(data)
        
        # Create features
        if self.feature_columns is None:
            raise ValueError("Feature columns not set. Train the ensemble first.")
        
        # Ensure we have the same features as training
        available_features = [col for col in self.feature_columns if col in data.columns]
        missing_features = [col for col in self.feature_columns if col not in data.columns]
        
        if missing_features:
            logger.warning(f"Missing features: {missing_features}")
            # Fill missing features with zeros
            for col in missing_features:
                data[col] = 0
        
        X = data[available_features]
        
        # Make predictions using appropriate models
        predictions = np.zeros(len(data))
        
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            if self.models[regime] is None:
                continue
                
            regime_mask = (regimes == regime)
            if regime_mask.sum() == 0:
                continue
                
            regime_data = X[regime_mask]
            regime_predictions = self.models[regime].predict(regime_data)
            predictions[regime_mask] = regime_predictions
        
        return predictions
    
    def load_models(self) -> bool:
        """Load pre-trained models from disk."""
        loaded_models = 0
        
        for regime in ['LOW', 'MEDIUM', 'HIGH']:
            model_path = self.model_dir / f"xgboost_{regime.lower()}_volatility.pkl"
            
            if model_path.exists():
                try:
                    self.models[regime] = joblib.load(model_path)
                    loaded_models += 1
                    logger.info(f"Loaded {regime} model from {model_path}")
                except Exception as e:
                    logger.error(f"Failed to load {regime} model: {e}")
            else:
                logger.warning(f"Model file not found: {model_path}")
        
        self.is_trained = loaded_models > 0
        return self.is_trained
    
    def get_model_info(self) -> Dict:
        """Get information about the trained models."""
        if not self.is_trained:
            return {"status": "not_trained"}
        
        info = {
            "status": "trained",
            "models": {}
        }
        
        for regime, model in self.models.items():
            if model is not None:
                info["models"][regime] = {
                    "type": "XGBRegressor",
                    "n_features": model.n_features_in_,
                    "n_estimators": model.n_estimators,
                    "max_depth": model.max_depth,
                    "learning_rate": model.learning_rate
                }
            else:
                info["models"][regime] = {"status": "not_available"}
        
        return info


def train_regime_specific_models(data_file: str, output_dir: str = "models/regime_specific") -> RegimeSpecificEnsemble:
    """
    Train regime-specific models from a data file.
    
    Args:
        data_file: Path to CSV file with training data
        output_dir: Directory to save models
        
    Returns:
        Trained RegimeSpecificEnsemble
    """
    # Load data
    data = pd.read_csv(data_file)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data = data.sort_values('timestamp').reset_index(drop=True)
    
    # Create ensemble
    ensemble = RegimeSpecificEnsemble(output_dir)
    
    # Train models
    metrics = ensemble.train_ensemble(data)
    
    # Print summary
    print("\n" + "="*60)
    print("REGIME-SPECIFIC TRAINING SUMMARY")
    print("="*60)
    
    for regime, metric in metrics.items():
        print(f"{regime} Regime:")
        print(f"  Samples: {metric['samples']}")
        print(f"  MAE: {metric['mae']:.3f}")
        print(f"  RMSE: {metric['rmse']:.3f}")
        print(f"  Directional Accuracy: {metric['directional_accuracy']:.1f}%")
        print()
    
    return ensemble


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python regime_specific_ensemble.py <data_file> [output_dir]")
        sys.exit(1)
    
    data_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "models/regime_specific"
    
    ensemble = train_regime_specific_models(data_file, output_dir)
    print(f"Training complete. Models saved to: {output_dir}")
