#!/usr/bin/env python3
"""
Hybrid Ensemble System - Production Main Component
Combines KDJ-Enhanced XGBoost with ARIMA-GARCH for superior predictions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
from pathlib import Path
import json
from datetime import datetime
from dataclasses import dataclass

from .xgboost_trainer import XGBoostTrainer
from .kdj_feature_engineer import KDJFeatureEngineer
from .legacy_feature_engineer import LegacyFeatureEngineer
from .data_processor import DataProcessor

@dataclass
class EnsemblePrediction:
    """Structure for ensemble prediction results."""
    timestamp: str
    ensemble_forecast: float
    xgboost_forecast: float
    arima_forecast: Optional[float]
    confidence_score: float
    directional_signal: str  # 'UP', 'DOWN', 'NEUTRAL'
    component_weights: Dict[str, float]
    prediction_metadata: Dict[str, Any]

class HybridEnsemble:
    """
    Production Hybrid Ensemble System.
    Combines KDJ-Enhanced XGBoost with ARIMA-GARCH baseline.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            'ensemble_weights': {
                'xgboost': 0.6,
                'arima_garch': 0.4
            },
            'confidence_threshold': 0.7,
            'directional_threshold': 0.02,  # 2% price change threshold
            'max_prediction_horizon': 5
        }
        
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.data_processor = DataProcessor()
        self.feature_engineer = LegacyFeatureEngineer()  # Use legacy engineer for compatibility
        self.xgboost_trainer = XGBoostTrainer()
        
        # Models
        self.xgboost_model = None
        self.arima_classifier = None
        
        # Performance tracking
        self.prediction_history = []
        self.performance_metrics = {}
        
    def load_models(self, xgboost_path: Path, arima_classifier_module: str = None):
        """Load pre-trained models."""
        # Load XGBoost model
        self.xgboost_trainer.load_model(xgboost_path)
        self.xgboost_model = self.xgboost_trainer.model
        self.logger.info(f"XGBoost model loaded from {xgboost_path}")
        
        # Load ARIMA-GARCH classifier (if available)
        try:
            if arima_classifier_module:
                # Dynamic import of ARIMA classifier
                import importlib
                module = importlib.import_module(arima_classifier_module)
                self.arima_classifier = module.ProductionStockClassifier()
                self.logger.info("ARIMA-GARCH classifier loaded")
        except Exception as e:
            self.logger.warning(f"Could not load ARIMA classifier: {e}")
            self.arima_classifier = None
    
    def train_ensemble(self, 
                      training_data: Union[str, Path, pd.DataFrame],
                      target_col: str = 'close',
                      validation_split: float = 0.2) -> Dict[str, Any]:
        """Train the complete ensemble system."""
        
        self.logger.info("Starting ensemble training...")
        
        # Load and process data
        if isinstance(training_data, (str, Path)):
            df = self.data_processor.load_data(training_data)
        else:
            df = training_data.copy()
        
        # Feature engineering with KDJ
        features = self.feature_engineer.create_features(df, include_kdj=True)
        
        # Prepare training data
        features_aligned, target = self.data_processor.prepare_for_training(df, target_col)
        
        # Align features and target
        min_len = min(len(features), len(target))
        features = features.iloc[:min_len]
        target = target.iloc[:min_len]
        
        # Split data
        split_data = self.data_processor.split_data(features, target, test_size=0.2, validation_size=0.1)
        
        # Train XGBoost component
        xgb_results = self.xgboost_trainer.train(
            split_data['X_train'], 
            split_data['y_train'],
            split_data['X_val'],
            split_data['y_val'],
            hyperparameter_tuning=True
        )
        
        # Store the trained model
        self.xgboost_model = self.xgboost_trainer.model
        
        # Evaluate ensemble on test set
        ensemble_results = self._evaluate_ensemble(
            split_data['X_test'], 
            split_data['y_test'],
            df.iloc[-len(split_data['X_test']):]  # Original data for ARIMA
        )
        
        # Combine results
        training_results = {
            'xgboost_results': xgb_results,
            'ensemble_results': ensemble_results,
            'training_samples': len(split_data['X_train']),
            'validation_samples': len(split_data['X_val']),
            'test_samples': len(split_data['X_test']),
            'features_used': len(features.columns),
            'kdj_analysis': self.xgboost_trainer.analyze_kdj_importance()
        }
        
        self.logger.info("Ensemble training complete")
        return training_results
    
    def predict(self, 
                input_data: Union[pd.DataFrame, Dict],
                include_confidence: bool = True) -> EnsemblePrediction:
        """Generate ensemble prediction for new data."""
        
        if self.xgboost_model is None:
            raise ValueError("XGBoost model not loaded. Call load_models() first.")
        
        # Process input data
        if isinstance(input_data, dict):
            input_df = pd.DataFrame([input_data])
        else:
            input_df = input_data.copy()
        
        # Generate features
        features = self.feature_engineer.create_features(input_df, include_kdj=True)
        
        if len(features) == 0:
            raise ValueError("Insufficient data for feature generation")
        
        # Get latest feature vector
        latest_features = features.iloc[-1:] 
        
        # XGBoost prediction
        xgb_forecast = self.xgboost_model.predict(latest_features)[0]
        
        # ARIMA-GARCH prediction (if available)
        arima_forecast = None
        if self.arima_classifier:
            try:
                # This would need the actual ARIMA interface
                arima_forecast = self._get_arima_prediction(input_df)
            except Exception as e:
                self.logger.warning(f"ARIMA prediction failed: {e}")
        
        # Combine predictions
        ensemble_forecast = self._combine_predictions(xgb_forecast, arima_forecast)
        
        # Calculate confidence
        confidence_score = self._calculate_confidence(xgb_forecast, arima_forecast)
        
        # Determine directional signal
        directional_signal = self._determine_direction(input_df, ensemble_forecast)
        
        # Create prediction result
        prediction = EnsemblePrediction(
            timestamp=datetime.now().isoformat(),
            ensemble_forecast=ensemble_forecast,
            xgboost_forecast=xgb_forecast,
            arima_forecast=arima_forecast,
            confidence_score=confidence_score,
            directional_signal=directional_signal,
            component_weights=self.config['ensemble_weights'],
            prediction_metadata={
                'features_used': len(latest_features.columns),
                'kdj_features': len([col for col in latest_features.columns if 'kdj' in col.lower()]),
                'input_data_shape': input_df.shape
            }
        )
        
        # Store prediction history
        self.prediction_history.append(prediction)
        
        return prediction
    
    def _combine_predictions(self, xgb_forecast: float, arima_forecast: Optional[float], ticker: Optional[str] = None) -> float:
        """Combine XGBoost and ARIMA predictions using ensemble weights."""
        # Check for stock-specific weights
        if ticker and 'stock_specific_weights' in self.config:
            stock_weights = self.config['stock_specific_weights'].get(ticker)
            if stock_weights:
                weights = stock_weights
                self.logger.info(f"Using stock-specific weights for {ticker}: ARIMA={weights.get('arima_garch', 0.0):.0%}")
            else:
                weights = self.config['ensemble_weights']
        else:
            weights = self.config['ensemble_weights']
        
        if arima_forecast is None:
            # Use only XGBoost if ARIMA not available
            return xgb_forecast
        
        # Weighted combination
        ensemble = (weights['xgboost'] * xgb_forecast + 
                   weights['arima_garch'] * arima_forecast)
        
        return ensemble
    
    def _calculate_confidence(self, xgb_forecast: float, arima_forecast: Optional[float]) -> float:
        """Calculate prediction confidence based on model agreement."""
        if arima_forecast is None:
            return 0.6  # Moderate confidence with single model
        
        # Calculate agreement between models
        relative_difference = abs(xgb_forecast - arima_forecast) / max(abs(xgb_forecast), abs(arima_forecast), 1)
        
        # Higher confidence when models agree
        confidence = max(0.3, 1.0 - relative_difference)
        
        return min(confidence, 0.95)  # Cap at 95%
    
    def _determine_direction(self, input_df: pd.DataFrame, forecast: float) -> str:
        """Determine directional signal based on forecast vs current price."""
        if 'close' not in input_df.columns:
            return 'NEUTRAL'
        
        current_price = input_df['close'].iloc[-1]
        price_change = (forecast - current_price) / current_price
        
        threshold = self.config['directional_threshold']
        
        if price_change > threshold:
            return 'UP'
        elif price_change < -threshold:
            return 'DOWN'
        else:
            return 'NEUTRAL'
    
    def _get_arima_prediction(self, data: pd.DataFrame) -> Optional[float]:
        """Get ARIMA-GARCH prediction (placeholder for actual implementation)."""
        # This would interface with the actual ARIMA classifier
        # For now, return None to indicate ARIMA not available
        return None
    
    def _evaluate_ensemble(self, X_test: pd.DataFrame, y_test: pd.Series, original_data: pd.DataFrame) -> Dict[str, float]:
        """Evaluate ensemble performance on test set."""
        predictions = []
        
        for i in range(len(X_test)):
            # Get features for this sample
            features = X_test.iloc[i:i+1]
            
            # XGBoost prediction
            xgb_pred = self.xgboost_model.predict(features)[0]
            
            # For evaluation, assume no ARIMA (or implement actual ARIMA calls)
            arima_pred = None
            
            # Combine predictions
            ensemble_pred = self._combine_predictions(xgb_pred, arima_pred)
            predictions.append(ensemble_pred)
        
        predictions = np.array(predictions)
        
        # Calculate metrics
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))
        r2 = r2_score(y_test, predictions)
        mape = np.mean(np.abs((y_test - predictions) / y_test)) * 100
        
        # Directional accuracy
        actual_direction = np.diff(y_test.values) > 0
        predicted_direction = np.diff(predictions) > 0
        directional_accuracy = (actual_direction == predicted_direction).mean() * 100
        
        return {
            'ensemble_mae': mae,
            'ensemble_rmse': rmse,
            'ensemble_r2': r2,
            'ensemble_mape': mape,
            'ensemble_directional_accuracy': directional_accuracy
        }
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get comprehensive model status."""
        return {
            'xgboost_loaded': self.xgboost_model is not None,
            'arima_loaded': self.arima_classifier is not None,
            'predictions_made': len(self.prediction_history),
            'ensemble_weights': self.config['ensemble_weights'],
            'last_prediction': self.prediction_history[-1].__dict__ if self.prediction_history else None,
            'model_info': self.xgboost_trainer.get_model_info() if self.xgboost_model else {}
        }
    
    def update_ensemble_weights(self, new_weights: Dict[str, float]):
        """Update ensemble component weights."""
        if abs(sum(new_weights.values()) - 1.0) > 1e-6:
            raise ValueError("Ensemble weights must sum to 1.0")
        
        self.config['ensemble_weights'] = new_weights
        self.logger.info(f"Updated ensemble weights: {new_weights}")
    
    def save_ensemble(self, save_dir: Path):
        """Save complete ensemble system."""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save XGBoost model
        if self.xgboost_model:
            xgb_path = save_dir / 'xgboost_model.pkl'
            self.xgboost_trainer.save_model(xgb_path)
        
        # Save ensemble configuration
        config_path = save_dir / 'ensemble_config.json'
        ensemble_config = {
            'config': self.config,
            'prediction_history_count': len(self.prediction_history),
            'performance_metrics': self.performance_metrics
        }
        
        with open(config_path, 'w') as f:
            json.dump(ensemble_config, f, indent=2)
        
        self.logger.info(f"Ensemble saved to {save_dir}")
    
    def batch_predict(self, data_list: List[Union[pd.DataFrame, Dict]]) -> List[EnsemblePrediction]:
        """Generate predictions for multiple inputs."""
        return [self.predict(data) for data in data_list]