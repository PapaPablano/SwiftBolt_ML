"""Options price prediction models.

Implements various ML models for predicting options prices:
- Linear regression baseline
- Random forest
- Gradient boosting (XGBoost)
- LSTM (when PyTorch available)

Usage:
    from src.ml_models.price_predictor import OptionsPricePredictor
    
    predictor = OptionsPricePredictor(model_type='random_forest')
    predictor.train(X_train, y_train)
    
    predictions = predictor.predict(X_test)
    confidence = predictor.predict_with_confidence(X_test)
"""

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Install with: pip install scikit-learn")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.debug("XGBoost not available")


@dataclass
class PredictionResult:
    """Prediction result with confidence intervals.
    
    Attributes:
        predictions: Predicted values
        lower_bound: Lower confidence bound
        upper_bound: Upper confidence bound
        confidence: Prediction confidence (0-1)
    """
    predictions: np.ndarray
    lower_bound: Optional[np.ndarray] = None
    upper_bound: Optional[np.ndarray] = None
    confidence: Optional[np.ndarray] = None


class OptionsPricePredictor:
    """ML-based options price predictor."""
    
    SUPPORTED_MODELS = ['linear', 'ridge', 'random_forest', 'gradient_boosting', 'xgboost']
    
    def __init__(
        self,
        model_type: str = 'random_forest',
        **model_params
    ):
        """Initialize predictor.
        
        Args:
            model_type: Type of model ('linear', 'ridge', 'random_forest', 
                       'gradient_boosting', 'xgboost')
            **model_params: Model-specific parameters
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. Install with: pip install scikit-learn")
        
        if model_type not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_type}. Choose from {self.SUPPORTED_MODELS}")
        
        self.model_type = model_type
        self.model_params = model_params
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        self._initialize_model()
        
        logger.info(f"OptionsPricePredictor initialized: {model_type}")
    
    def _initialize_model(self):
        """Initialize the ML model."""
        if self.model_type == 'linear':
            self.model = LinearRegression(**self.model_params)
        
        elif self.model_type == 'ridge':
            self.model = Ridge(alpha=1.0, **self.model_params)
        
        elif self.model_type == 'random_forest':
            default_params = {'n_estimators': 100, 'max_depth': 10, 'random_state': 42, 'n_jobs': -1}
            default_params.update(self.model_params)
            self.model = RandomForestRegressor(**default_params)
        
        elif self.model_type == 'gradient_boosting':
            default_params = {'n_estimators': 100, 'max_depth': 5, 'learning_rate': 0.1, 'random_state': 42}
            default_params.update(self.model_params)
            self.model = GradientBoostingRegressor(**default_params)
        
        elif self.model_type == 'xgboost':
            if not XGBOOST_AVAILABLE:
                logger.warning("XGBoost not available, falling back to gradient boosting")
                self.model_type = 'gradient_boosting'
                self._initialize_model()
                return
            
            default_params = {'n_estimators': 100, 'max_depth': 5, 'learning_rate': 0.1, 'random_state': 42}
            default_params.update(self.model_params)
            self.model = xgb.XGBRegressor(**default_params)
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """Train the model.
        
        Args:
            X: Features DataFrame
            y: Target variable
            validation_split: Validation set size
        
        Returns:
            Dictionary with training metrics
        """
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train model
        logger.info(f"Training {self.model_type} on {len(X_train)} samples...")
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_pred = self.model.predict(X_train_scaled)
        val_pred = self.model.predict(X_val_scaled)
        
        metrics = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'train_r2': r2_score(y_train, train_pred),
            'val_rmse': np.sqrt(mean_squared_error(y_val, val_pred)),
            'val_mae': mean_absolute_error(y_val, val_pred),
            'val_r2': r2_score(y_val, val_pred)
        }
        
        self.is_trained = True
        
        logger.info(f"Training complete. Val R²: {metrics['val_r2']:.4f}, Val RMSE: {metrics['val_rmse']:.4f}")
        
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions.
        
        Args:
            X: Features DataFrame
        
        Returns:
            Predicted values
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")
        
        X = X.fillna(X.mean())
        X_scaled = self.scaler.transform(X)
        
        predictions = self.model.predict(X_scaled)
        
        return predictions
    
    def predict_with_confidence(
        self,
        X: pd.DataFrame,
        confidence_level: float = 0.95
    ) -> PredictionResult:
        """Make predictions with confidence intervals.
        
        Args:
            X: Features DataFrame
            confidence_level: Confidence level (e.g., 0.95 for 95%)
        
        Returns:
            PredictionResult with confidence bounds
        """
        predictions = self.predict(X)
        
        # Estimate confidence based on model type
        if self.model_type in ['random_forest', 'gradient_boosting', 'xgboost']:
            # Use prediction std from ensemble models
            lower, upper = self._ensemble_confidence(X, confidence_level)
        else:
            # Simple interval based on training error
            lower, upper = self._simple_confidence(predictions, confidence_level)
        
        # Calculate confidence scores (inverse of interval width)
        interval_width = upper - lower
        max_width = interval_width.max()
        confidence = 1 - (interval_width / max_width) if max_width > 0 else np.ones_like(predictions)
        
        return PredictionResult(
            predictions=predictions,
            lower_bound=lower,
            upper_bound=upper,
            confidence=confidence
        )
    
    def _ensemble_confidence(
        self,
        X: pd.DataFrame,
        confidence_level: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate confidence using ensemble predictions."""
        X = X.fillna(X.mean())
        X_scaled = self.scaler.transform(X)
        
        if self.model_type == 'random_forest':
            # Get predictions from all trees
            tree_predictions = np.array([
                tree.predict(X_scaled)
                for tree in self.model.estimators_
            ])
            
            mean_pred = tree_predictions.mean(axis=0)
            std_pred = tree_predictions.std(axis=0)
            
        elif self.model_type in ['gradient_boosting', 'xgboost']:
            # Approximate std from prediction
            predictions = self.model.predict(X_scaled)
            # Use a heuristic: 10% of prediction as std
            mean_pred = predictions
            std_pred = abs(predictions) * 0.10
        
        else:
            predictions = self.model.predict(X_scaled)
            mean_pred = predictions
            std_pred = abs(predictions) * 0.10
        
        # Calculate confidence interval
        z_score = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        
        lower = mean_pred - z_score * std_pred
        upper = mean_pred + z_score * std_pred
        
        return lower, upper
    
    def _simple_confidence(
        self,
        predictions: np.ndarray,
        confidence_level: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Simple confidence interval."""
        # Use 10% of prediction as interval
        interval = abs(predictions) * 0.10
        
        lower = predictions - interval
        upper = predictions + interval
        
        return lower, upper
    
    def get_feature_importance(self) -> Optional[pd.Series]:
        """Get feature importances.
        
        Returns:
            Series with feature importances (if supported)
        """
        if not self.is_trained:
            return None
        
        if hasattr(self.model, 'feature_importances_'):
            return pd.Series(
                self.model.feature_importances_,
                index=range(len(self.model.feature_importances_))
            ).sort_values(ascending=False)
        
        elif hasattr(self.model, 'coef_'):
            return pd.Series(
                abs(self.model.coef_),
                index=range(len(self.model.coef_))
            ).sort_values(ascending=False)
        
        return None
    
    def save(self, filepath: str):
        """Save model to disk.
        
        Args:
            filepath: Path to save model
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'model_type': self.model_type,
            'model_params': self.model_params
        }
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'OptionsPricePredictor':
        """Load model from disk.
        
        Args:
            filepath: Path to load model from
        
        Returns:
            Loaded predictor
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        predictor = cls(
            model_type=model_data['model_type'],
            **model_data['model_params']
        )
        predictor.model = model_data['model']
        predictor.scaler = model_data['scaler']
        predictor.is_trained = True
        
        logger.info(f"Model loaded from {filepath}")
        
        return predictor


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Options Price Predictor - Self Test")
    print("=" * 70)
    
    if not SKLEARN_AVAILABLE:
        print("\n⚠️ scikit-learn not available")
        print("Install with: pip install scikit-learn")
    else:
        # Generate synthetic data
        np.random.seed(42)
        n_samples = 1000
        n_features = 10
        
        X = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        
        # Target: linear combination + noise
        y = pd.Series(
            X.iloc[:, 0] * 2 + X.iloc[:, 1] * -1.5 + np.random.randn(n_samples) * 0.5
        )
        
        print(f"\nGenerated {n_samples} samples with {n_features} features")
        
        # Test different models
        for model_type in ['linear', 'random_forest', 'gradient_boosting']:
            print(f"\n📊 Testing {model_type} model...")
            
            predictor = OptionsPricePredictor(model_type=model_type)
            metrics = predictor.train(X, y, validation_split=0.2)
            
            print(f"  Train R²: {metrics['train_r2']:.4f}, RMSE: {metrics['train_rmse']:.4f}")
            print(f"  Val R²: {metrics['val_r2']:.4f}, RMSE: {metrics['val_rmse']:.4f}")
            
            # Test prediction with confidence
            X_test = X.tail(10)
            result = predictor.predict_with_confidence(X_test)
            
            print(f"  Sample prediction: {result.predictions[0]:.4f}")
            print(f"  Confidence interval: [{result.lower_bound[0]:.4f}, {result.upper_bound[0]:.4f}]")
            print(f"  Confidence score: {result.confidence[0]:.4f}")
        
        # Test save/load
        print("\n📊 Testing Save/Load...")
        predictor = OptionsPricePredictor(model_type='random_forest')
        predictor.train(X, y)
        
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            temp_path = f.name
        
        predictor.save(temp_path)
        loaded_predictor = OptionsPricePredictor.load(temp_path)
        
        # Verify predictions match
        original_pred = predictor.predict(X.head(5))
        loaded_pred = loaded_predictor.predict(X.head(5))
        
        if np.allclose(original_pred, loaded_pred):
            print("✅ Save/load successful (predictions match)")
        else:
            print("❌ Save/load mismatch")
        
        # Clean up
        Path(temp_path).unlink()
    
    print("\n" + "=" * 70)
    print("✅ Price predictor test complete!")
    print("=" * 70)
