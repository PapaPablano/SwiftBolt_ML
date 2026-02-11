#!/usr/bin/env python3
"""
XGBoost Trainer - Production System
Handles XGBoost model training with KDJ-enhanced features.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
import joblib
from pathlib import Path
import json
from datetime import datetime

from xgboost import XGBRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from .purged_cv import PurgedTimeSeriesSplit, validate_purged_splits

class XGBoostTrainer:
    """
    Production-grade XGBoost trainer with hyperparameter optimization.
    Optimized for KDJ-enhanced feature sets.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            'random_state': 42,
            'n_jobs': -1,
            'early_stopping_rounds': 50,
            'eval_metric': 'mae'
        }
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.best_params = None
        self.training_history = []
        
    def train(self, 
              X_train: pd.DataFrame, 
              y_train: pd.Series,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[pd.Series] = None,
              hyperparameter_tuning: bool = True) -> Dict[str, Any]:
        """
        Train XGBoost model with optional hyperparameter tuning.
        """
        self.logger.info(f"Training XGBoost on {len(X_train)} samples, {len(X_train.columns)} features")
        
        # Get optimal hyperparameters
        if hyperparameter_tuning:
            best_params = self._tune_hyperparameters(X_train, y_train)
        else:
            best_params = self._get_default_params()
            
        self.best_params = best_params
        
        # Train final model
        self.model = XGBRegressor(**best_params)
        
        # Use validation set if provided
        eval_set = None
        if X_val is not None and y_val is not None:
            eval_set = [(X_train, y_train), (X_val, y_val)]
            
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            verbose=False
        )
        
        # Generate training metrics
        training_results = self._evaluate_model(X_train, y_train, X_val, y_val)
        
        # Save training history
        training_record = {
            'timestamp': datetime.now().isoformat(),
            'n_samples': len(X_train),
            'n_features': len(X_train.columns),
            'hyperparameters': best_params,
            'metrics': training_results,
            'feature_names': list(X_train.columns)
        }
        self.training_history.append(training_record)
        
        self.logger.info(f"Training complete. CV MAE: {training_results.get('cv_mae', 'N/A'):.4f}")
        
        return training_results
    
    def _tune_hyperparameters(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Perform hyperparameter tuning using GridSearchCV."""
        self.logger.info("Starting hyperparameter tuning...")
        
        # Define parameter grid optimized for KDJ features
        param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [6, 8, 10],
            'learning_rate': [0.1, 0.15, 0.2],
            'min_child_weight': [1, 3, 5],
            'gamma': [0.0, 0.1],
            'reg_alpha': [0.0, 0.1],
            'reg_lambda': [1.0, 1.5]
        }
        
        # Use TimeSeriesSplit for proper time series validation
        tscv = TimeSeriesSplit(n_splits=3)
        
        # Base model
        base_model = XGBRegressor(
            random_state=self.config['random_state'],
            n_jobs=self.config['n_jobs']
        )
        
        # Grid search
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=tscv,
            scoring='neg_mean_absolute_error',
            n_jobs=1,  # XGBoost already uses all cores
            verbose=1
        )
        
        grid_search.fit(X, y)
        
        self.logger.info(f"Best CV score: {-grid_search.best_score_:.4f}")
        self.logger.info(f"Best parameters: {grid_search.best_params_}")
        
        return grid_search.best_params_
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default optimized parameters for KDJ-enhanced models."""
        return {
            'n_estimators': 200,
            'max_depth': 10,
            'learning_rate': 0.15,
            'min_child_weight': 3,
            'gamma': 0.0,
            'reg_alpha': 0.0,
            'reg_lambda': 1.0,
            'random_state': self.config['random_state'],
            'n_jobs': self.config['n_jobs']
        }
    
    def _evaluate_model(self, 
                       X_train: pd.DataFrame, 
                       y_train: pd.Series,
                       X_val: Optional[pd.DataFrame] = None,
                       y_val: Optional[pd.Series] = None) -> Dict[str, float]:
        """Evaluate model performance with comprehensive metrics."""
        
        # Training predictions
        y_train_pred = self.model.predict(X_train)
        
        metrics = {
            'train_mae': mean_absolute_error(y_train, y_train_pred),
            'train_rmse': np.sqrt(mean_squared_error(y_train, y_train_pred)),
            'train_r2': r2_score(y_train, y_train_pred)
        }
        
        # Validation predictions if available
        if X_val is not None and y_val is not None:
            y_val_pred = self.model.predict(X_val)
            metrics.update({
                'val_mae': mean_absolute_error(y_val, y_val_pred),
                'val_rmse': np.sqrt(mean_squared_error(y_val, y_val_pred)),
                'val_r2': r2_score(y_val, y_val_pred),
                'val_mape': np.mean(np.abs((y_val - y_val_pred) / y_val)) * 100
            })
            
            # Directional accuracy
            metrics['val_directional_accuracy'] = self._calculate_directional_accuracy(y_val, y_val_pred)
        
        # Cross-validation score (if available from tuning)
        if self.best_params:
            # Use Purged TimeSeriesSplit for better temporal validation
            purged_cv = PurgedTimeSeriesSplit(n_splits=3, embargo_pct=0.01, test_size=0.2)
            cv_scores = []
            
            # Validate purged splits prevent leakage
            try:
                validation_passed, validation_results = validate_purged_splits(X_train, y_train, purged_cv)
                if validation_passed:
                    self.logger.info("Purged CV validation passed - no temporal leakage detected")
                else:
                    self.logger.warning(f"Temporal leakage detected: max correlation {validation_results['max_correlation']:.3f}")
            except Exception as e:
                self.logger.warning(f"Purged CV validation failed: {e}")
            
            for train_idx, test_idx in purged_cv.split(X_train, y_train):
                if len(train_idx) == 0 or len(test_idx) == 0:
                    continue
                    
                X_cv_train, X_cv_test = X_train.iloc[train_idx], X_train.iloc[test_idx]
                y_cv_train, y_cv_test = y_train.iloc[train_idx], y_train.iloc[test_idx]
                
                cv_model = XGBRegressor(**self.best_params)
                cv_model.fit(X_cv_train, y_cv_train)
                cv_pred = cv_model.predict(X_cv_test)
                cv_scores.append(mean_absolute_error(y_cv_test, cv_pred))
                
            if cv_scores:
                metrics['cv_mae'] = np.mean(cv_scores)
                metrics['cv_mae_std'] = np.std(cv_scores)
                metrics['cv_mae_min'] = np.min(cv_scores)
                metrics['cv_mae_max'] = np.max(cv_scores)
        
        return metrics
    
    def analyze_residuals(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Analyze model residuals for diagnostic purposes."""
        try:
            from src.option_analysis.residual_diagnostics import ResidualAnalyzer
            
            # Get predictions
            predictions = self.model.predict(X)
            residuals = y - predictions
            
            # Perform residual diagnostics
            analyzer = ResidualAnalyzer()
            diagnostics = analyzer.analyze_residuals(residuals)
            
            return {
                'diagnostics_passed': diagnostics.diagnostics_passed,
                'ljung_box_passed': diagnostics.ljung_box_passed,
                'jarque_bera_passed': diagnostics.jarque_bera_passed,
                'arch_passed': diagnostics.arch_passed,
                'issues': diagnostics.issues,
                'warnings': diagnostics.warnings,
                'mean_residual': diagnostics.mean_residual,
                'std_residual': diagnostics.std_residual,
                'skewness': diagnostics.skewness,
                'kurtosis': diagnostics.kurtosis
            }
        except Exception as e:
            self.logger.warning(f"Residual analysis failed: {e}")
            return {'diagnostics_passed': False, 'error': str(e)}
    
    def compare_with_benchmarks(self, X_train: pd.DataFrame, y_train: pd.Series, 
                               X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, Any]:
        """Compare model performance against benchmark models."""
        try:
            from src.option_analysis.benchmark_models import BenchmarkComparator
            
            # Get our model predictions
            our_predictions = self.model.predict(X_test)
            
            # Create benchmark comparator
            comparator = BenchmarkComparator()
            comparator.add_default_benchmarks()
            
            # Compare models
            results = comparator.compare_models(
                X_train.values, y_train.values,
                X_test.values, y_test.values,
                target_model_name="XGBoost Model",
                target_predictions=our_predictions
            )
            
            # Extract key metrics
            benchmark_summary = {}
            for name, result in results.items():
                benchmark_summary[name] = {
                    'mae': result.metrics['mae'],
                    'rmse': result.metrics['rmse'],
                    'r2': result.metrics['r2'],
                    'is_better': result.is_significantly_better
                }
            
            return {
                'benchmark_comparison': benchmark_summary,
                'our_model_rank': self._calculate_model_rank(results),
                'improvement_over_best_benchmark': self._calculate_improvement(results)
            }
        except Exception as e:
            self.logger.warning(f"Benchmark comparison failed: {e}")
            return {'benchmark_comparison': {}, 'error': str(e)}
    
    def _calculate_model_rank(self, results: Dict) -> int:
        """Calculate rank of our model among all models."""
        sorted_models = sorted(results.items(), key=lambda x: x[1].metrics['mae'])
        for rank, (name, _) in enumerate(sorted_models, 1):
            if name == "XGBoost Model":
                return rank
        return len(sorted_models)
    
    def _calculate_improvement(self, results: Dict) -> float:
        """Calculate improvement over best benchmark."""
        if "XGBoost Model" not in results:
            return 0.0
            
        our_mae = results["XGBoost Model"].metrics['mae']
        benchmark_maes = [result.metrics['mae'] for name, result in results.items() 
                         if name != "XGBoost Model"]
        
        if not benchmark_maes:
            return 0.0
            
        best_benchmark_mae = min(benchmark_maes)
        improvement = (best_benchmark_mae - our_mae) / best_benchmark_mae * 100
        return improvement
    
    def _calculate_directional_accuracy(self, actual: pd.Series, predicted: np.ndarray) -> float:
        """Calculate directional accuracy (% of correct direction predictions)."""
        actual_direction = np.diff(actual.values) > 0
        predicted_direction = np.diff(predicted) > 0
        return (actual_direction == predicted_direction).mean() * 100
    
    def get_feature_importance(self) -> pd.Series:
        """Get feature importance from trained model."""
        if self.model is None:
            raise ValueError("Model must be trained first")
            
        return pd.Series(
            self.model.feature_importances_,
            index=self.model.feature_names_in_
        ).sort_values(ascending=False)
    
    def analyze_kdj_importance(self) -> Dict[str, Any]:
        """Analyze KDJ feature importance specifically."""
        if self.model is None:
            raise ValueError("Model must be trained first")
            
        importance = self.get_feature_importance()
        
        # Identify KDJ features
        kdj_features = [col for col in importance.index if 'kdj' in col.lower()]
        
        if not kdj_features:
            return {'kdj_features_found': False}
            
        kdj_importance = importance[kdj_features]
        total_importance = importance.sum()
        
        return {
            'kdj_features_found': True,
            'kdj_feature_count': len(kdj_features),
            'kdj_total_importance': kdj_importance.sum(),
            'kdj_importance_percentage': (kdj_importance.sum() / total_importance) * 100,
            'kdj_feature_rankings': kdj_importance.to_dict(),
            'top_kdj_feature': kdj_importance.index[0] if len(kdj_importance) > 0 else None
        }
    
    def save_model(self, path: Path, include_metadata: bool = True):
        """Save trained model and metadata."""
        if self.model is None:
            raise ValueError("No trained model to save")
            
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model
        joblib.dump(self.model, path)
        self.logger.info(f"Model saved to {path}")
        
        # Save metadata
        if include_metadata:
            metadata_path = path.with_suffix('.json')
            metadata = {
                'training_history': self.training_history,
                'best_params': self.best_params,
                'feature_importance': self.get_feature_importance().to_dict(),
                'kdj_analysis': self.analyze_kdj_importance()
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            self.logger.info(f"Metadata saved to {metadata_path}")
    
    def load_model(self, path: Path):
        """Load trained model and metadata."""
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
            
        # Load model
        self.model = joblib.load(path)
        self.logger.info(f"Model loaded from {path}")
        
        # Load metadata if available
        metadata_path = path.with_suffix('.json')
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            self.training_history = metadata.get('training_history', [])
            self.best_params = metadata.get('best_params', {})
            
            self.logger.info(f"Metadata loaded from {metadata_path}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using trained model."""
        if self.model is None:
            raise ValueError("Model must be trained or loaded first")
            
        return self.model.predict(X)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information."""
        if self.model is None:
            return {'model_trained': False}
            
        return {
            'model_trained': True,
            'n_features': self.model.n_features_in_,
            'n_estimators': self.model.n_estimators,
            'best_params': self.best_params,
            'training_records': len(self.training_history),
            'kdj_analysis': self.analyze_kdj_importance()
        }