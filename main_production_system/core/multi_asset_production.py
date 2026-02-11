#!/usr/bin/env python3
"""
Multi-Asset Production System with asset-specific routing.
Routes each stock to its optimal model configuration based on
stock-specific performance patterns and market regimes.
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, Tuple, Optional, Any
from pathlib import Path
import logging

# Import existing components
from .regime_specific_ensemble import RegimeSpecificEnsemble
from .walk_forward_validation import WalkForwardValidator

class MultiAssetProductionSystem:
    """
    Route each stock to its optimal model configuration.
    Based on stock-specific performance patterns from validation results.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the multi-asset production system.
        
        Args:
            config_path: Path to asset configuration file
        """
        self.logger = logging.getLogger(__name__)
        
        # Load asset configurations
        if config_path:
            self.asset_configs = self._load_asset_configs(config_path)
        else:
            self.asset_configs = self._get_default_asset_configs()
        
        # Initialize models
        self.ensemble = RegimeSpecificEnsemble()
        self.validator = WalkForwardValidator()
        
        # Performance tracking
        self.performance_history = {}
        
        self.logger.info("Multi-Asset Production System initialized")
    
    def _get_default_asset_configs(self) -> Dict[str, Dict]:
        """
        Default asset configurations based on validation results.
        """
        return {
            'CRWD': {
                'category': 'Tech/Stable',
                'primary_regime': 'LOW',
                'weights': {
                    'LOW': (0.55, 0.45),    # ARIMA-heavy for stability
                    'MEDIUM': (0.40, 0.60),  # Balanced for transitions
                    'HIGH': (0.20, 0.80)     # XGBoost-heavy for volatility
                },
                'min_confidence': 0.52,
                'max_position_size': 5000,
                'deployment_strategy': 'Deploy for stable periods'
            },
            'CLSK': {
                'category': 'Crypto/Volatile',
                'primary_regime': 'HIGH',
                'weights': {
                    'LOW': (0.30, 0.70),    # XGBoost-heavy even in LOW
                    'MEDIUM': (0.15, 0.85),  # XGBoost-heavy for transitions
                    'HIGH': (0.15, 0.85)     # XGBoost-heavy for volatility
                },
                'min_confidence': 0.58,
                'max_position_size': 2000,
                'deployment_strategy': 'Validate then deploy'
            },
            'DIS': {
                'category': 'Entertainment',
                'primary_regime': 'LOW',
                'weights': {
                    'LOW': (0.60, 0.40),    # Conservative ARIMA
                    'MEDIUM': (0.45, 0.55),  # Slightly XGBoost-heavy
                    'HIGH': (0.35, 0.65)     # XGBoost for volatility
                },
                'min_confidence': 0.50,
                'max_position_size': 3000,
                'deployment_strategy': 'Deploy conservative'
            },
            'SOFI': {
                'category': 'Fintech',
                'primary_regime': 'MEDIUM',
                'weights': {
                    'LOW': (0.50, 0.50),    # Balanced
                    'MEDIUM': (0.35, 0.65),  # XGBoost-heavy for transitions
                    'HIGH': (0.25, 0.75)     # XGBoost-heavy for volatility
                },
                'min_confidence': 0.54,
                'max_position_size': 2500,
                'deployment_strategy': 'Test before deploy'
            },
            'TSM': {
                'category': 'Tech/Medium',
                'primary_regime': 'LOW',
                'weights': {
                    'LOW': (0.50, 0.50),    # Balanced
                    'MEDIUM': (0.40, 0.60),  # XGBoost-heavy for transitions
                    'HIGH': (0.30, 0.70)     # XGBoost-heavy for volatility
                },
                'min_confidence': 0.52,
                'max_position_size': 4000,
                'deployment_strategy': 'Deploy for stable periods'
            },
            'SMR': {
                'category': 'Nuclear/High',
                'primary_regime': 'LOW',
                'weights': {
                    'LOW': (0.45, 0.55),    # Slightly XGBoost-heavy
                    'MEDIUM': (0.30, 0.70),  # XGBoost-heavy for transitions
                    'HIGH': (0.20, 0.80)     # XGBoost-heavy for volatility
                },
                'min_confidence': 0.53,
                'max_position_size': 2000,
                'deployment_strategy': 'Test before deploy'
            }
        }
    
    def _load_asset_configs(self, config_path: str) -> Dict[str, Dict]:
        """Load asset configurations from file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load config from {config_path}: {e}")
            return self._get_default_asset_configs()
    
    def route_prediction(self, ticker: str, current_regime: str, 
                        features: pd.DataFrame) -> Dict[str, Any]:
        """
        Route to optimal model based on asset and regime.
        
        Args:
            ticker: Stock ticker symbol
            current_regime: Current market regime (LOW/MEDIUM/HIGH)
            features: Feature matrix for prediction
            
        Returns:
            Dictionary with prediction, confidence, and metadata
        """
        # Get asset configuration
        config = self.asset_configs.get(ticker, self._get_default_config())
        
        # Check if regime is supported
        if current_regime not in config['weights']:
            self.logger.warning(f"Unsupported regime {current_regime} for {ticker}")
            return self._predict_default(ticker, features)
        
        # Get model weights for this regime
        arima_weight, xgb_weight = config['weights'][current_regime]
        
        # Make prediction with regime-specific weights
        prediction = self._predict_with_weights(
            ticker, features, current_regime, arima_weight, xgb_weight
        )
        
        # Add metadata
        prediction.update({
            'ticker': ticker,
            'regime': current_regime,
            'weights': {'arima': arima_weight, 'xgboost': xgb_weight},
            'config': config,
            'timestamp': pd.Timestamp.now().isoformat()
        })
        
        # Track performance
        self._track_prediction(ticker, prediction)
        
        return prediction
    
    def _predict_with_weights(self, ticker: str, features: pd.DataFrame,
                            regime: str, arima_weight: float, xgb_weight: float) -> Dict[str, Any]:
        """Make prediction with specific model weights."""
        try:
            # Get predictions from both models
            arima_pred = self.ensemble.predict_arima(ticker, features, regime)
            xgb_pred = self.ensemble.predict_xgboost(ticker, features, regime)
            
            # Weighted ensemble prediction
            ensemble_pred = (arima_weight * arima_pred['prediction'] + 
                           xgb_weight * xgb_pred['prediction'])
            
            # Calculate confidence (weighted average)
            confidence = (arima_weight * arima_pred.get('confidence', 0.5) + 
                        xgb_weight * xgb_pred.get('confidence', 0.5))
            
            return {
                'prediction': ensemble_pred,
                'confidence': confidence,
                'arima_prediction': arima_pred['prediction'],
                'xgboost_prediction': xgb_pred['prediction'],
                'arima_weight': arima_weight,
                'xgboost_weight': xgb_weight
            }
            
        except Exception as e:
            self.logger.error(f"Prediction failed for {ticker}: {e}")
            return self._predict_default(ticker, features)
    
    def _predict_default(self, ticker: str, features: pd.DataFrame) -> Dict[str, Any]:
        """Default prediction when regime-specific prediction fails."""
        try:
            # Use ensemble default prediction
            prediction = self.ensemble.predict(ticker, features)
            return {
                'prediction': prediction.get('prediction', 0.0),
                'confidence': prediction.get('confidence', 0.5),
                'method': 'default_ensemble',
                'error': 'regime_specific_failed'
            }
        except Exception as e:
            self.logger.error(f"Default prediction failed for {ticker}: {e}")
            return {
                'prediction': 0.0,
                'confidence': 0.0,
                'method': 'fallback',
                'error': str(e)
            }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default configuration for unknown assets."""
        return {
            'category': 'Unknown',
            'primary_regime': 'LOW',
            'weights': {
                'LOW': (0.50, 0.50),
                'MEDIUM': (0.40, 0.60),
                'HIGH': (0.30, 0.70)
            },
            'min_confidence': 0.52,
            'max_position_size': 1000,
            'deployment_strategy': 'Test before deploy'
        }
    
    def _track_prediction(self, ticker: str, prediction: Dict[str, Any]):
        """Track prediction for performance monitoring."""
        if ticker not in self.performance_history:
            self.performance_history[ticker] = []
        
        self.performance_history[ticker].append({
            'timestamp': prediction['timestamp'],
            'regime': prediction['regime'],
            'prediction': prediction['prediction'],
            'confidence': prediction['confidence'],
            'weights': prediction['weights']
        })
        
        # Keep only last 1000 predictions per ticker
        if len(self.performance_history[ticker]) > 1000:
            self.performance_history[ticker] = self.performance_history[ticker][-1000:]
    
    def get_asset_recommendations(self, ticker: str) -> Dict[str, Any]:
        """
        Get deployment recommendations for a specific asset.
        """
        config = self.asset_configs.get(ticker, self._get_default_config())
        
        return {
            'ticker': ticker,
            'category': config['category'],
            'primary_regime': config['primary_regime'],
            'deployment_strategy': config['deployment_strategy'],
            'min_confidence': config['min_confidence'],
            'max_position_size': config['max_position_size'],
            'regime_weights': config['weights'],
            'recent_performance': self._get_recent_performance(ticker)
        }
    
    def _get_recent_performance(self, ticker: str, days: int = 30) -> Dict[str, Any]:
        """Get recent performance metrics for an asset."""
        if ticker not in self.performance_history:
            return {'error': 'No performance data available'}
        
        recent_predictions = self.performance_history[ticker][-days:]
        
        if not recent_predictions:
            return {'error': 'No recent predictions'}
        
        # Calculate basic metrics
        confidences = [p['confidence'] for p in recent_predictions]
        regimes = [p['regime'] for p in recent_predictions]
        
        return {
            'total_predictions': len(recent_predictions),
            'avg_confidence': np.mean(confidences),
            'regime_distribution': {
                'LOW': regimes.count('LOW'),
                'MEDIUM': regimes.count('MEDIUM'),
                'HIGH': regimes.count('HIGH')
            },
            'last_prediction': recent_predictions[-1]['timestamp']
        }
    
    def should_trade(self, ticker: str, regime: str, confidence: float) -> Dict[str, Any]:
        """
        Determine if trading should be allowed based on asset configuration.
        """
        config = self.asset_configs.get(ticker, self._get_default_config())
        
        checks = {
            'regime_supported': regime in config['weights'],
            'confidence_threshold': confidence >= config['min_confidence'],
            'deployment_strategy': config['deployment_strategy'],
            'max_position_size': config['max_position_size']
        }
        
        # Additional checks based on deployment strategy
        if config['deployment_strategy'] == 'Deploy for stable periods':
            checks['regime_appropriate'] = regime in ['LOW']
        elif config['deployment_strategy'] == 'Validate then deploy':
            checks['needs_validation'] = True
        elif config['deployment_strategy'] == 'Test before deploy':
            checks['needs_testing'] = True
        
        checks['should_trade'] = all([
            checks['regime_supported'],
            checks['confidence_threshold']
        ])
        
        return checks
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status and performance."""
        status = {
            'total_assets': len(self.asset_configs),
            'active_predictions': sum(len(preds) for preds in self.performance_history.values()),
            'asset_status': {}
        }
        
        for ticker in self.asset_configs.keys():
            status['asset_status'][ticker] = {
                'config_loaded': True,
                'recent_predictions': len(self.performance_history.get(ticker, [])),
                'last_prediction': self.performance_history.get(ticker, [{}])[-1].get('timestamp', 'Never')
            }
        
        return status
    
    def save_performance_report(self, output_path: str):
        """Save performance report to file."""
        report = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'system_status': self.get_system_status(),
            'asset_configs': self.asset_configs,
            'performance_history': self.performance_history
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Performance report saved to {output_path}")

# Example usage and testing
if __name__ == "__main__":
    # Initialize system
    system = MultiAssetProductionSystem()
    
    # Example prediction
    features = pd.DataFrame({
        'close': [100.0],
        'volume': [1000000],
        'rsi': [50.0],
        'macd': [0.1]
    })
    
    # Test different assets and regimes
    test_cases = [
        ('CRWD', 'LOW'),
        ('CLSK', 'HIGH'),
        ('DIS', 'LOW'),
        ('SOFI', 'MEDIUM')
    ]
    
    for ticker, regime in test_cases:
        print(f"\n🎯 Testing {ticker} in {regime} regime:")
        prediction = system.route_prediction(ticker, regime, features)
        print(f"   Prediction: {prediction['prediction']:.4f}")
        print(f"   Confidence: {prediction['confidence']:.3f}")
        print(f"   Weights: ARIMA={prediction['arima_weight']:.2f}, XGBoost={prediction['xgboost_weight']:.2f}")
        
        # Check if should trade
        trade_check = system.should_trade(ticker, regime, prediction['confidence'])
        print(f"   Should trade: {trade_check['should_trade']}")
        print(f"   Strategy: {trade_check['deployment_strategy']}")
    
    # Get system status
    print(f"\n📊 System Status:")
    status = system.get_system_status()
    print(f"   Total assets: {status['total_assets']}")
    print(f"   Active predictions: {status['active_predictions']}")
