"""
Weight Optimizer: Dynamic Ensemble Weight Learning
===================================================

Learns optimal ensemble weights based on recent model performance.
Supports multiple optimization strategies:
- Ridge regression (minimize MSE with regularization)
- Sharpe ratio allocation
- Directional accuracy weighting

Key Features:
- Adaptive weight learning from recent performance
- Bounded weights to prevent extreme allocations
- Walk-forward compatible for live reoptimization
- Regularization to prevent overfitting
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)


class WeightOptimizer:
    """
    Learn optimal ensemble weights from model predictions.

    Optimization methods:
    - 'ridge': Ridge regression to minimize MSE
    - 'sharpe': Allocate based on Sharpe ratios
    - 'directional': Allocate based on directional accuracy
    - 'equal': Equal weights (baseline)
    """

    def __init__(
        self,
        optimization_method: str = "ridge",
        alpha: float = 0.01,
        min_weight: float = 0.05,
        max_weight: float = 0.60,
        lookback_window: int = 50,
    ) -> None:
        """
        Initialize Weight Optimizer.

        Args:
            optimization_method: 'ridge', 'sharpe', 'directional', 'equal'
            alpha: Regularization strength for ridge regression
            min_weight: Minimum weight per model
            max_weight: Maximum weight per model
            lookback_window: Recent samples to use for optimization
        """
        self.optimization_method = optimization_method
        self.alpha = alpha
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.lookback_window = lookback_window

        self.weights: Optional[Dict[str, float]] = None
        self.optimization_history: List[Dict] = []
        self.is_fitted = False

        logger.info(
            "WeightOptimizer initialized: method=%s, alpha=%.3f",
            optimization_method,
            alpha,
        )

    def optimize_weights(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        optimize_for: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Optimize weights to minimize error metric.

        Args:
            predictions_dict: {model_name: predictions_array}
            actuals: Actual values to compare against
            optimize_for: Override optimization method for this call

        Returns:
            Dict of {model_name: weight}
        """
        method = optimize_for or self.optimization_method
        model_names = list(predictions_dict.keys())
        n_models = len(model_names)

        if n_models == 0:
            return {}

        if n_models == 1:
            return {model_names[0]: 1.0}

        # Limit to lookback window
        if len(actuals) > self.lookback_window:
            actuals = actuals[-self.lookback_window :]
            predictions_dict = {
                name: preds[-self.lookback_window :] for name, preds in predictions_dict.items()
            }

        try:
            if method == "ridge":
                weights = self._ridge_regression_weights(predictions_dict, actuals, model_names)
            elif method == "sharpe":
                weights = self._sharpe_ratio_weights(predictions_dict, actuals, model_names)
            elif method == "directional":
                weights = self._directional_accuracy_weights(predictions_dict, actuals, model_names)
            elif method == "scipy":
                weights = self._scipy_optimize_weights(predictions_dict, actuals, model_names)
            else:
                # Equal weights as fallback
                weights = {name: 1.0 / n_models for name in model_names}

            self.weights = weights
            self.is_fitted = True

            # Record optimization
            self.optimization_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "method": method,
                    "n_samples": len(actuals),
                    "weights": weights.copy(),
                }
            )

            logger.info(
                "Weights optimized (%s): %s",
                method,
                {k: f"{v:.3f}" for k, v in weights.items()},
            )

            return weights

        except Exception as e:
            logger.warning("Weight optimization failed: %s. Using equal.", e)
            return {name: 1.0 / n_models for name in model_names}

    def _ridge_regression_weights(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        model_names: List[str],
    ) -> Dict[str, float]:
        """Learn weights via ridge regression."""
        # Stack predictions as feature matrix
        X = np.column_stack([predictions_dict[name] for name in model_names])

        # Fit ridge regression (no intercept to get pure weights)
        ridge = Ridge(alpha=self.alpha, fit_intercept=False)
        ridge.fit(X, actuals)

        # Extract and normalize weights
        raw_weights = np.abs(ridge.coef_)

        # Handle zero weights
        if raw_weights.sum() == 0:
            raw_weights = np.ones(len(model_names))

        normalized_weights = raw_weights / raw_weights.sum()

        # Clip to bounds
        normalized_weights = np.clip(
            normalized_weights,
            self.min_weight,
            self.max_weight,
        )
        normalized_weights /= normalized_weights.sum()

        return {name: float(weight) for name, weight in zip(model_names, normalized_weights)}

    def _sharpe_ratio_weights(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        model_names: List[str],
    ) -> Dict[str, float]:
        """Allocate based on Sharpe ratios of prediction errors."""
        sharpe_ratios = {}

        for name in model_names:
            preds = predictions_dict[name]
            errors = actuals - preds

            # Sharpe = mean / std (higher is better for returns)
            # For errors, we want negative errors (under-prediction)
            # Actually, we want low absolute error, so use -|error|
            neg_abs_errors = -np.abs(errors)

            if len(neg_abs_errors) > 1 and np.std(neg_abs_errors) > 0:
                sharpe = np.mean(neg_abs_errors) / np.std(neg_abs_errors)
            else:
                sharpe = 0

            # Convert to positive allocation score
            sharpe_ratios[name] = max(sharpe + 2, 0)  # Shift to positive

        total_sharpe = sum(sharpe_ratios.values())

        if total_sharpe == 0:
            n_models = len(model_names)
            return {name: 1.0 / n_models for name in model_names}

        weights = {name: float(sharpe_ratios[name] / total_sharpe) for name in model_names}

        # Clip to bounds
        weights = self._clip_weights(weights)

        return weights

    def _directional_accuracy_weights(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        model_names: List[str],
    ) -> Dict[str, float]:
        """Allocate based on directional accuracy."""
        accuracies = {}

        for name in model_names:
            preds = predictions_dict[name]

            # Calculate directional accuracy
            if len(preds) < 2:
                accuracies[name] = 0.5
                continue

            # Direction of change
            actual_direction = np.sign(np.diff(actuals))
            pred_direction = np.sign(np.diff(preds))

            # Accuracy
            correct = np.sum(actual_direction == pred_direction)
            total = len(actual_direction)

            accuracy = correct / total if total > 0 else 0.5

            # Adjust to favor accuracy > 0.5
            adjusted = max(accuracy - 0.5, 0) ** 2
            accuracies[name] = adjusted

        total_accuracy = sum(accuracies.values())

        if total_accuracy == 0:
            n_models = len(model_names)
            return {name: 1.0 / n_models for name in model_names}

        weights = {name: float(accuracies[name] / total_accuracy) for name in model_names}

        # Clip to bounds
        weights = self._clip_weights(weights)

        return weights

    def _scipy_optimize_weights(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        model_names: List[str],
    ) -> Dict[str, float]:
        """Optimize weights using scipy minimize."""
        n_models = len(model_names)
        X = np.column_stack([predictions_dict[name] for name in model_names])

        def objective(weights):
            """MSE objective."""
            weighted_pred = X @ weights
            mse = np.mean((actuals - weighted_pred) ** 2)
            # Add L2 regularization
            reg = self.alpha * np.sum(weights**2)
            return mse + reg

        # Constraints: weights sum to 1
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

        # Bounds: each weight between min and max
        bounds = [(self.min_weight, self.max_weight)] * n_models

        # Initial guess: equal weights
        x0 = np.ones(n_models) / n_models

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        if result.success:
            weights = result.x
            # Normalize to ensure sum = 1
            weights = weights / weights.sum()
        else:
            weights = np.ones(n_models) / n_models

        return {name: float(weight) for name, weight in zip(model_names, weights)}

    def _clip_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Clip weights to bounds and renormalize."""
        clipped = {
            name: np.clip(w, self.min_weight, self.max_weight) for name, w in weights.items()
        }

        total = sum(clipped.values())
        if total > 0:
            clipped = {k: v / total for k, v in clipped.items()}

        return clipped

    def get_weights(self) -> Dict[str, float]:
        """Get current weights."""
        return self.weights.copy() if self.weights else {}

    def update_from_performance(
        self,
        model_name: str,
        accuracy: float,
        recent_error: float,
    ) -> None:
        """
        Update weights incrementally from recent performance.

        This allows for online weight updates without full reoptimization.

        Args:
            model_name: Name of the model
            accuracy: Recent directional accuracy
            recent_error: Recent prediction error (lower is better)
        """
        if self.weights is None or model_name not in self.weights:
            return

        # Simple exponential update
        learning_rate = 0.1

        # Performance score (higher is better)
        score = accuracy - abs(recent_error)

        # Update weight
        old_weight = self.weights[model_name]
        adjustment = learning_rate * (score - 0.5)
        new_weight = np.clip(
            old_weight + adjustment,
            self.min_weight,
            self.max_weight,
        )
        self.weights[model_name] = new_weight

        # Renormalize all weights
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def get_optimization_history(self) -> pd.DataFrame:
        """Get optimization history as DataFrame."""
        if not self.optimization_history:
            return pd.DataFrame()

        records = []
        for entry in self.optimization_history:
            row = {
                "timestamp": entry["timestamp"],
                "method": entry["method"],
                "n_samples": entry["n_samples"],
            }
            for model, weight in entry["weights"].items():
                row[f"weight_{model}"] = weight
            records.append(row)

        return pd.DataFrame(records)

    def get_info(self) -> Dict:
        """Get optimizer info."""
        return {
            "optimization_method": self.optimization_method,
            "alpha": self.alpha,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "lookback_window": self.lookback_window,
            "is_fitted": self.is_fitted,
            "current_weights": self.weights,
            "n_optimizations": len(self.optimization_history),
        }


class AdaptiveWeightOptimizer(WeightOptimizer):
    """
    Adaptive weight optimizer with regime detection.

    Automatically switches optimization strategy based on market conditions.
    """

    def __init__(
        self,
        default_method: str = "ridge",
        volatility_threshold: float = 0.02,
        trend_threshold: float = 0.01,
        **kwargs,
    ) -> None:
        """
        Initialize Adaptive Weight Optimizer.

        Args:
            default_method: Default optimization method
            volatility_threshold: High volatility threshold
            trend_threshold: Strong trend threshold
            **kwargs: Passed to WeightOptimizer
        """
        super().__init__(optimization_method=default_method, **kwargs)
        self.default_method = default_method
        self.volatility_threshold = volatility_threshold
        self.trend_threshold = trend_threshold
        self.current_regime = "normal"

    def detect_regime(self, returns: np.ndarray) -> str:
        """
        Detect current market regime.

        Args:
            returns: Recent returns

        Returns:
            Regime: 'high_vol', 'trending', or 'normal'
        """
        if len(returns) < 10:
            return "normal"

        volatility = np.std(returns)
        trend = np.mean(returns)

        if volatility > self.volatility_threshold:
            return "high_vol"
        elif abs(trend) > self.trend_threshold:
            return "trending"
        else:
            return "normal"

    def optimize_weights_adaptive(
        self,
        predictions_dict: Dict[str, np.ndarray],
        actuals: np.ndarray,
        returns: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Optimize weights with automatic method selection.

        Args:
            predictions_dict: Model predictions
            actuals: Actual values
            returns: Recent returns for regime detection

        Returns:
            Optimized weights
        """
        # Detect regime
        if returns is not None:
            self.current_regime = self.detect_regime(returns)
        else:
            self.current_regime = "normal"

        # Select method based on regime
        if self.current_regime == "high_vol":
            # In high volatility, prefer directional accuracy
            method = "directional"
        elif self.current_regime == "trending":
            # In trending markets, prefer Sharpe-based
            method = "sharpe"
        else:
            # Normal: use default (ridge)
            method = self.default_method

        logger.info(
            "Regime detected: %s, using method: %s",
            self.current_regime,
            method,
        )

        return self.optimize_weights(predictions_dict, actuals, optimize_for=method)


if __name__ == "__main__":
    # Quick test
    print("Testing WeightOptimizer...")

    np.random.seed(42)
    n = 100

    # Generate actuals
    actuals = np.cumsum(np.random.randn(n) * 0.01) + 100

    # Generate model predictions with different biases
    predictions = {
        "rf": actuals + np.random.randn(n) * 0.5,
        "gb": actuals + np.random.randn(n) * 0.3 + 0.1,
        "arima": actuals + np.random.randn(n) * 0.4 - 0.05,
        "prophet": actuals + np.random.randn(n) * 0.6,
        "lstm": actuals + np.random.randn(n) * 0.35,
    }

    # Test different optimization methods
    for method in ["ridge", "sharpe", "directional", "scipy", "equal"]:
        optimizer = WeightOptimizer(optimization_method=method)
        weights = optimizer.optimize_weights(predictions, actuals)
        print(f"\n{method.upper()} weights:")
        for name, weight in sorted(weights.items(), key=lambda x: -x[1]):
            print(f"  {name}: {weight:.3f}")

    # Test adaptive optimizer
    print("\n\nTesting AdaptiveWeightOptimizer...")
    adaptive = AdaptiveWeightOptimizer()

    # Normal regime
    normal_returns = np.random.randn(50) * 0.005
    weights = adaptive.optimize_weights_adaptive(predictions, actuals, returns=normal_returns)
    print(f"\nNormal regime (detected: {adaptive.current_regime}):")
    print(f"  Weights: {weights}")

    # High volatility regime
    high_vol_returns = np.random.randn(50) * 0.05
    weights = adaptive.optimize_weights_adaptive(predictions, actuals, returns=high_vol_returns)
    print(f"\nHigh vol regime (detected: {adaptive.current_regime}):")
    print(f"  Weights: {weights}")

    # Trending regime
    trending_returns = np.ones(50) * 0.02 + np.random.randn(50) * 0.002
    weights = adaptive.optimize_weights_adaptive(predictions, actuals, returns=trending_returns)
    print(f"\nTrending regime (detected: {adaptive.current_regime}):")
    print(f"  Weights: {weights}")

    print("\n\nSUCCESS: WeightOptimizer working!")
