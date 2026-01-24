"""
Ensemble Loader - Load trained models from disk for production.
Provides EnsemblePredictor wrapper for easy integration.
"""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent.parent / "trained_models"
MODELS_DIR.mkdir(exist_ok=True)


class EnsembleLoader:
    """Load trained ensemble models from disk."""
    
    @staticmethod
    def load_latest_model(
        symbol: str,
        timeframe: str,
        max_age_days: int = 60,
    ) -> Optional[Dict]:
        """
        Load most recent trained model for symbol/timeframe.
        
        Args:
            symbol: Ticker (e.g., "AAPL")
            timeframe: Timeframe ID (e.g., "d1", "h1")
            max_age_days: Reject models older than this (60 = monthly retrain)
        
        Returns:
            Model artifact dictionary or None if not found/too old
        """
        
        # Find all model files for this symbol/timeframe
        pattern = f"{symbol}_{timeframe}_*.pkl"
        candidates = list(MODELS_DIR.glob(pattern))
        
        if not candidates:
            logger.warning(f"No models found for {symbol}/{timeframe} in {MODELS_DIR}")
            return None
        
        # Load most recent file
        latest_file = sorted(candidates)[-1]
        
        # Check age
        try:
            file_timestamp_str = latest_file.stem.split("_")[-1]
            file_date = datetime.strptime(file_timestamp_str, "%Y%m%d")
            age_days = (datetime.utcnow() - file_date).days
            
            if age_days > max_age_days:
                logger.warning(
                    f"Model too old: {age_days} days (max: {max_age_days}). "
                    f"Run monthly retraining job."
                )
                return None
        except Exception as e:
            logger.warning(f"Could not parse timestamp from {latest_file}: {e}")
            age_days = 0
        
        # Load model
        try:
            with open(latest_file, "rb") as f:
                artifact = pickle.load(f)
            
            logger.info(
                f"Loaded {symbol}/{timeframe} from {latest_file.name} "
                f"({age_days} days old, accuracy: {artifact.get('ensemble_accuracy', 0.0):.1%})"
            )
            return artifact
            
        except Exception as e:
            logger.error(f"Failed to load {latest_file}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def list_available_models() -> Dict:
        """List all available trained models on disk."""
        models = {}
        
        for pkl_file in MODELS_DIR.glob("*.pkl"):
            parts = pkl_file.stem.split("_")
            if len(parts) >= 3:
                symbol = parts[0]
                timeframe = parts[1]
                timestamp = parts[2]
                
                if symbol not in models:
                    models[symbol] = {}
                if timeframe not in models[symbol]:
                    models[symbol][timeframe] = []
                
                models[symbol][timeframe].append({
                    "file": pkl_file.name,
                    "timestamp": timestamp,
                })
        
        logger.info(f"Available models: {models}")
        return models


class EnsemblePredictor:
    """
    High-level predictor wrapper.
    Handles model loading, prediction, and error handling.
    
    Usage:
        predictor = EnsemblePredictor(symbol="AAPL", timeframe="d1")
        result = predictor.predict(df)
        if result:
            forecast = result["forecast"]
            confidence = result["confidence"]
    """
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        use_trained_weights: bool = True,
    ):
        """
        Initialize predictor.
        
        Args:
            symbol: Ticker (e.g., "AAPL")
            timeframe: Timeframe (e.g., "d1")
            use_trained_weights: If True, require trained models
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.artifact = None
        self.is_trained = False
        
        # Load trained models
        self.artifact = EnsembleLoader.load_latest_model(symbol, timeframe)
        
        if self.artifact:
            self.is_trained = True
            logger.info(
                f"Predictor initialized with trained weights for {symbol}/{timeframe}"
            )
        else:
            if use_trained_weights:
                logger.error(
                    f"No trained models for {symbol}/{timeframe}. "
                    f"Run: python ml/src/training/ensemble_training_job.py"
                )
            else:
                logger.warning(
                    f"No trained models for {symbol}/{timeframe}, "
                    f"will use default uniform weights"
                )
    
    def predict(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Generate prediction from ensemble.
        
        Args:
            df: OHLCV DataFrame with features
        
        Returns:
            {
                "forecast": "BULLISH",
                "confidence": 0.72,
                "model_agreements": {"rf": "BULLISH", "gb": "BULLISH"},
                "weights_used": {"rf": 0.50, "gb": 0.50},
                "is_trained_model": True,
            }
            OR None on error
        """
        
        if not self.is_trained:
            logger.error(f"No trained model loaded for {self.symbol}/{self.timeframe}")
            return None
        
        try:
            # Get models and weights
            models = self.artifact.get("models", {})
            weights = self.artifact.get("weights", {})
            feature_names = self.artifact.get("feature_names", [])
            
            if not models or not weights:
                logger.error("Artifact missing models or weights")
                return None
            
            # Prepare features (select last row)
            from src.training.data_preparation import select_features_for_training
            features = select_features_for_training(df)
            
            # Ensure we have the right columns
            if feature_names:
                missing_cols = set(feature_names) - set(features.columns)
                if missing_cols:
                    logger.warning(f"Missing features: {list(missing_cols)[:5]}")
                    # Add missing columns with zeros
                    for col in missing_cols:
                        features[col] = 0
                
                # Reorder to match training
                features = features[feature_names]
            
            # Get last row (most recent data point)
            last_row = features.iloc[[-1]]
            
            # Get predictions from each model
            model_predictions = {}
            weighted_score = 0.0
            
            for model_name, model in models.items():
                try:
                    pred = model.predict(last_row)[0]
                    model_predictions[model_name] = pred
                    
                    # Add to weighted score
                    weight = weights.get(model_name, 0)
                    pred_val = {"BEARISH": -1, "NEUTRAL": 0, "BULLISH": 1}.get(pred, 0)
                    weighted_score += weight * pred_val
                    
                except Exception as e:
                    logger.error(f"Prediction failed for {model_name}: {e}")
                    model_predictions[model_name] = "NEUTRAL"
            
            # Convert weighted score to forecast
            if weighted_score > 0.33:
                forecast = "BULLISH"
            elif weighted_score < -0.33:
                forecast = "BEARISH"
            else:
                forecast = "NEUTRAL"
            
            # Calculate confidence (agreement level)
            agreement = sum(1 for p in model_predictions.values() if p == forecast)
            confidence = agreement / len(model_predictions) if model_predictions else 0.33
            
            return {
                "forecast": forecast,
                "confidence": confidence,
                "model_agreements": model_predictions,
                "weights_used": weights,
                "is_trained_model": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                f"Prediction failed for {self.symbol}/{self.timeframe}: {e}",
                exc_info=True
            )
            return None
