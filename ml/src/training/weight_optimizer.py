"""Ensemble weight optimization using Ridge regression.

Optimizes model weights based on validation set performance.
"""

import logging
from typing import Dict, List

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
        3. Weights reflect each model's out-of-sample strength
        4. Solve: minimize ||y_true - (w1*pred1 + w2*pred2 + ...)||^2 + λ||w||^2
    
    Example:
        optimizer = EnsembleWeightOptimizer(alpha=1.0)
        model_predictions = {
            "rf": ["BULLISH", "BEARISH", "NEUTRAL", ...],
            "gb": ["BULLISH", "BULLISH", "BEARISH", ...],
        }
        actual = ["BULLISH", "BEARISH", "NEUTRAL", ...]
        weights = optimizer.optimize_weights(model_predictions, actual)
        # Returns: {"rf": 0.52, "gb": 0.48}
    """
    
    def __init__(self, alpha: float = 1.0):
        """
        Initialize optimizer.
        
        Args:
            alpha: Ridge regularization strength
                   Higher = more uniform weights
                   Lower = specialized weights based on individual performance
        """
        self.alpha = alpha
        self.ridge_model = Ridge(alpha=alpha, fit_intercept=False)
        self.weights = None
    
    def optimize_weights(
        self,
        model_predictions: Dict[str, List[str]],
        actual_labels: pd.Series,
    ) -> Dict[str, float]:
        """
        Find optimal weights for ensemble models.
        
        Args:
            model_predictions: Dict mapping model name to list of predictions
                              Each prediction is "BULLISH", "NEUTRAL", or "BEARISH"
            actual_labels: True direction labels (same length as predictions)
        
        Returns:
            Dict mapping model name to weight (0-1, normalized to sum to 1)
        
        Example:
            model_predictions = {
                "rf": ["BULLISH", "BULLISH", "BEARISH"],
                "gb": ["BULLISH", "BEARISH", "BEARISH"],
            }
            actual = pd.Series(["BULLISH", "BEARISH", "BEARISH"])
            weights = optimizer.optimize_weights(model_predictions, actual)
            # Returns: {"rf": 0.50, "gb": 0.50}
        """
        
        # Convert labels to numeric targets
        label_to_value = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
        
        # Target: convert actual labels to numeric
        y_target = np.array([
            label_to_value.get(label, 0) for label in actual_labels
        ])
        
        # Stack model predictions as features
        model_names = list(model_predictions.keys())
        n_samples = len(actual_labels)
        
        # Create feature matrix: (n_samples, n_models)
        X_ensemble = np.zeros((n_samples, len(model_names)))
        
        for i, model_name in enumerate(model_names):
            preds = model_predictions[model_name]
            X_ensemble[:, i] = [
                label_to_value.get(pred, 0) for pred in preds
            ]
        
        logger.info(f"Optimizing weights for {len(model_names)} models")
        logger.info(f"  Training samples: {n_samples}")
        logger.info(f"  Models: {model_names}")
        
        # Fit Ridge regression
        self.ridge_model.fit(X_ensemble, y_target)
        raw_weights = self.ridge_model.coef_
        
        # Normalize weights
        # Clip negative weights to 0 (no negative contributions)
        raw_weights = np.maximum(raw_weights, 0)
        
        # Normalize to sum to 1
        if raw_weights.sum() > 0:
            normalized_weights = raw_weights / raw_weights.sum()
        else:
            # Fallback: uniform weights if all are zero
            logger.warning("All weights were negative/zero, using uniform weights")
            normalized_weights = np.ones(len(model_names)) / len(model_names)
        
        # Create result dictionary
        self.weights = {
            name: float(weight)
            for name, weight in zip(model_names, normalized_weights)
        }
        
        # Log results
        logger.info("Optimized Weights:")
        for name, weight in sorted(self.weights.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {name}: {weight:.2%}")
        
        # Validate weights
        if not self.validate_weights():
            logger.warning("Weight validation failed, using uniform weights as fallback")
            self.weights = {name: 1.0 / len(model_names) for name in model_names}
        
        return self.weights
    
    def validate_weights(self) -> bool:
        """
        Check weights are valid.
        
        Returns:
            True if weights are valid (sum to ~1, all non-negative)
        """
        
        if self.weights is None:
            return False
        
        total = sum(self.weights.values())
        
        # Allow small floating-point error
        if not (0.99 < total < 1.01):
            logger.warning(f"Weights don't sum to 1: {total}")
            return False
        
        if any(w < 0 for w in self.weights.values()):
            logger.warning(f"Negative weights found: {self.weights}")
            return False
        
        return True
    
    def get_ensemble_score(
        self,
        model_predictions: Dict[str, str],
    ) -> float:
        """
        Calculate weighted ensemble score from model predictions.
        
        Args:
            model_predictions: Dict mapping model name to single prediction
        
        Returns:
            Weighted score (-1 to 1, where >0.33 = BULLISH, <-0.33 = BEARISH)
        
        Example:
            score = optimizer.get_ensemble_score({
                "rf": "BULLISH",
                "gb": "BEARISH",
            })
            # With weights {"rf": 0.6, "gb": 0.4}:
            # score = 0.6 * 1 + 0.4 * (-1) = 0.2 (NEUTRAL)
        """
        
        if self.weights is None:
            raise ValueError("Weights not optimized yet. Call optimize_weights() first.")
        
        label_to_value = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
        
        score = 0.0
        for model_name, pred in model_predictions.items():
            weight = self.weights.get(model_name, 0)
            pred_value = label_to_value.get(pred, 0)
            score += weight * pred_value
        
        return score
