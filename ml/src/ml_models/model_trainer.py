"""Model training pipeline with W&B integration.

Coordinates feature engineering, model training, and experiment tracking.

Usage:
    from src.ml_models.model_trainer import ModelTrainer, TrainingConfig
    
    config = TrainingConfig(
        model_type='random_forest',
        target_horizon=5,
        validation_split=0.2
    )
    
    trainer = ModelTrainer(config, use_wandb=True)
    model, metrics = trainer.train(price_data, options_data)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .feature_engineering import FeatureEngineer
from .price_predictor import OptionsPricePredictor

logger = logging.getLogger(__name__)

# Try to import W&B
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    logger.debug("W&B not available")


@dataclass
class TrainingConfig:
    """Training configuration.
    
    Attributes:
        model_type: Type of ML model
        target_horizon: Days ahead to predict
        validation_split: Validation set size
        test_split: Test set size
        include_greeks: Include Greeks in features
        model_params: Model-specific parameters
    """
    model_type: str = 'random_forest'
    target_horizon: int = 5
    validation_split: float = 0.2
    test_split: float = 0.1
    include_greeks: bool = True
    model_params: Dict = field(default_factory=dict)


class ModelTrainer:
    """Model training pipeline with experiment tracking."""
    
    def __init__(
        self,
        config: TrainingConfig,
        use_wandb: bool = False,
        wandb_project: str = "swiftbolt-ml"
    ):
        """Initialize trainer.
        
        Args:
            config: Training configuration
            use_wandb: Whether to use W&B tracking
            wandb_project: W&B project name
        """
        self.config = config
        self.use_wandb = use_wandb and WANDB_AVAILABLE
        self.wandb_project = wandb_project
        
        self.feature_engineer = FeatureEngineer()
        self.model: Optional[OptionsPricePredictor] = None
        
        if self.use_wandb and not WANDB_AVAILABLE:
            logger.warning("W&B requested but not available")
            self.use_wandb = False
        
        logger.info(f"ModelTrainer initialized: {config.model_type}, horizon={config.target_horizon}d")
    
    def train(
        self,
        price_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None,
        run_name: Optional[str] = None
    ) -> Tuple[OptionsPricePredictor, Dict]:
        """Train model on data.
        
        Args:
            price_data: Price DataFrame
            options_data: Optional options/Greeks data
            run_name: W&B run name
        
        Returns:
            Tuple of (trained_model, metrics_dict)
        """
        # Initialize W&B if enabled
        if self.use_wandb:
            wandb.init(
                project=self.wandb_project,
                name=run_name,
                config=self.config.__dict__
            )
        
        try:
            # Create features
            logger.info("Creating features...")
            features = self.feature_engineer.create_features(
                price_data,
                options_data,
                include_greeks=self.config.include_greeks
            )
            
            # Create target (forward returns)
            target = self._create_target(price_data)
            
            # Align features and target
            valid_idx = ~(features.isna().any(axis=1) | target.isna())
            features_clean = features[valid_idx]
            target_clean = target[valid_idx]
            
            logger.info(f"Training on {len(features_clean)} samples with {len(features_clean.columns)} features")
            
            # Split data (chronological)
            train_size = int(len(features_clean) * (1 - self.config.test_split - self.config.validation_split))
            val_size = int(len(features_clean) * self.config.validation_split)
            
            X_train = features_clean.iloc[:train_size]
            y_train = target_clean.iloc[:train_size]
            
            X_val = features_clean.iloc[train_size:train_size+val_size]
            y_val = target_clean.iloc[train_size:train_size+val_size]
            
            X_test = features_clean.iloc[train_size+val_size:]
            y_test = target_clean.iloc[train_size+val_size:]
            
            # Train model
            self.model = OptionsPricePredictor(
                model_type=self.config.model_type,
                **self.config.model_params
            )
            
            # Train on train+val combined for final model
            X_train_full = pd.concat([X_train, X_val])
            y_train_full = pd.concat([y_train, y_val])
            
            train_metrics = self.model.train(X_train_full, y_train_full, validation_split=0.2)
            
            # Test set evaluation
            test_pred = self.model.predict(X_test)
            from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
            
            test_metrics = {
                'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
                'test_mae': mean_absolute_error(y_test, test_pred),
                'test_r2': r2_score(y_test, test_pred)
            }
            
            # Directional accuracy
            directional_accuracy = np.mean(
                np.sign(y_test) == np.sign(test_pred)
            )
            test_metrics['directional_accuracy'] = directional_accuracy
            
            # Combine metrics
            all_metrics = {**train_metrics, **test_metrics}
            
            # Log to W&B
            if self.use_wandb:
                wandb.log(all_metrics)
                
                # Log feature importance
                importance = self.model.get_feature_importance()
                if importance is not None:
                    wandb.log({"feature_importance": wandb.Histogram(importance.values)})
            
            logger.info(
                f"Training complete. Test R²: {test_metrics['test_r2']:.4f}, "
                f"Directional Accuracy: {directional_accuracy:.2%}"
            )
            
            return self.model, all_metrics
            
        finally:
            if self.use_wandb:
                wandb.finish()
    
    def _create_target(self, price_data: pd.DataFrame) -> pd.Series:
        """Create target variable.
        
        Args:
            price_data: Price DataFrame
        
        Returns:
            Target series
        """
        # Forward returns
        close = price_data['close']
        target = close.pct_change(self.config.target_horizon).shift(-self.config.target_horizon)
        
        return target
    
    def cross_validate(
        self,
        price_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None,
        n_splits: int = 5
    ) -> Dict:
        """Perform time-series cross-validation.
        
        Args:
            price_data: Price DataFrame
            options_data: Optional options data
            n_splits: Number of CV splits
        
        Returns:
            CV metrics dictionary
        """
        # Create features
        features = self.feature_engineer.create_features(
            price_data,
            options_data,
            include_greeks=self.config.include_greeks
        )
        
        target = self._create_target(price_data)
        
        # Clean data
        valid_idx = ~(features.isna().any(axis=1) | target.isna())
        features_clean = features[valid_idx]
        target_clean = target[valid_idx]
        
        # Time-series CV splits
        split_size = len(features_clean) // (n_splits + 1)
        
        cv_scores = []
        
        for i in range(n_splits):
            train_end = split_size * (i + 1)
            test_end = split_size * (i + 2)
            
            X_train = features_clean.iloc[:train_end]
            y_train = target_clean.iloc[:train_end]
            
            X_test = features_clean.iloc[train_end:test_end]
            y_test = target_clean.iloc[train_end:test_end]
            
            # Train model
            model = OptionsPricePredictor(
                model_type=self.config.model_type,
                **self.config.model_params
            )
            model.train(X_train, y_train, validation_split=0.2)
            
            # Evaluate
            test_pred = model.predict(X_test)
            
            from sklearn.metrics import mean_squared_error, r2_score
            rmse = np.sqrt(mean_squared_error(y_test, test_pred))
            r2 = r2_score(y_test, test_pred)
            
            cv_scores.append({'rmse': rmse, 'r2': r2})
            
            logger.info(f"CV Fold {i+1}/{n_splits}: RMSE={rmse:.4f}, R²={r2:.4f}")
        
        # Aggregate scores
        avg_metrics = {
            'cv_rmse_mean': np.mean([s['rmse'] for s in cv_scores]),
            'cv_rmse_std': np.std([s['rmse'] for s in cv_scores]),
            'cv_r2_mean': np.mean([s['r2'] for s in cv_scores]),
            'cv_r2_std': np.std([s['r2'] for s in cv_scores])
        }
        
        logger.info(
            f"CV Results: RMSE={avg_metrics['cv_rmse_mean']:.4f} ± {avg_metrics['cv_rmse_std']:.4f}, "
            f"R²={avg_metrics['cv_r2_mean']:.4f} ± {avg_metrics['cv_r2_std']:.4f}"
        )
        
        return avg_metrics


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Model Trainer - Self Test")
    print("=" * 70)
    
    # Generate synthetic data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=300, freq='D')
    
    prices = 100 * (1 + np.random.randn(300) * 0.02).cumprod()
    
    price_data = pd.DataFrame({
        'open': prices * (1 + np.random.randn(300) * 0.005),
        'high': prices * (1 + abs(np.random.randn(300)) * 0.01),
        'low': prices * (1 - abs(np.random.randn(300)) * 0.01),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, 300)
    }, index=dates)
    
    print(f"\nGenerated {len(price_data)} days of price data")
    
    # Test training
    print("\n📊 Testing Model Training...")
    
    config = TrainingConfig(
        model_type='random_forest',
        target_horizon=5,
        validation_split=0.2,
        test_split=0.1,
        include_greeks=False
    )
    
    trainer = ModelTrainer(config, use_wandb=False)
    model, metrics = trainer.train(price_data)
    
    print(f"\nTraining Metrics:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
    
    # Test cross-validation
    print("\n📊 Testing Cross-Validation...")
    cv_metrics = trainer.cross_validate(price_data, n_splits=3)
    
    print(f"\nCV Metrics:")
    for key, value in cv_metrics.items():
        print(f"  {key}: {value:.4f}")
    
    print("\n" + "=" * 70)
    print("✅ Model trainer test complete!")
    print("=" * 70)
