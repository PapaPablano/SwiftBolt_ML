"""
Walk-Forward Cross-Validation for Time Series.

CRITICAL: Standard K-fold CV causes ~250% performance overestimation in time series
because it shuffles data, allowing future information to leak into training.

Walk-Forward CV maintains temporal order:
  - Train: Jan-Aug, Validate: Sep
  - Train: Jan-Sep, Validate: Oct
  - Train: Jan-Oct, Validate: Nov

This gives realistic accuracy estimates for production deployment.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

logger = logging.getLogger(__name__)


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate directional accuracy (trend prediction).

    Measures how often the model correctly predicts if price goes up or down.
    Critical metric for trading - more important than MSE.

    Args:
        y_true: Actual values
        y_pred: Predicted values

    Returns:
        Directional accuracy (0.0 to 1.0)
    """
    if len(y_true) < 2:
        return np.nan

    direction_true = np.diff(y_true) > 0
    direction_pred = np.diff(y_pred) > 0
    return np.mean(direction_true == direction_pred)


class WalkForwardCV:
    """
    Walk-forward cross-validation for time series.

    NEVER shuffles data - maintains temporal order to prevent data leakage.

    Attributes:
        n_splits: Number of validation folds
        test_size: Size of each test fold (in samples, typically days)
        gap: Gap between train and test to prevent lookahead bias

    Example:
        cv = WalkForwardCV(n_splits=5, test_size=28)
        results = cv.validate(model, X, y)
        print(f"Directional Accuracy: {results['directional_accuracy_mean']:.2%}")
    """

    def __init__(
        self,
        n_splits: int = 5,
        test_size: int = 28,  # 28 days as per M5 Kaggle competition
        gap: int = 0,  # Gap between train/test to prevent leakage
    ):
        self.n_splits = n_splits
        self.test_size = test_size
        self.gap = gap

        logger.info(
            f"Walk-Forward CV initialized: {n_splits} splits, "
            f"{test_size} samples test, {gap} samples gap"
        )

    def split(self, X: pd.DataFrame) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate train/test indices for walk-forward validation.

        The training set grows with each fold while test set slides forward.

        Args:
            X: Feature DataFrame (used only for length)

        Returns:
            List of (train_indices, test_indices) tuples
        """
        n_samples = len(X)
        splits = []

        # Calculate initial training size
        initial_train_size = n_samples - (self.n_splits * self.test_size)

        if initial_train_size < self.test_size:
            raise ValueError(
                f"Not enough data! Have {n_samples} samples but need at least "
                f"{self.n_splits * self.test_size * 2} for {self.n_splits} splits "
                f"with test_size={self.test_size}"
            )

        for i in range(self.n_splits):
            # Training set grows with each fold
            train_end = initial_train_size + (i * self.test_size) - self.gap
            train_idx = np.arange(0, train_end)

            # Test set slides forward
            test_start = train_end + self.gap
            test_end = test_start + self.test_size
            test_idx = np.arange(test_start, min(test_end, n_samples))

            if len(test_idx) > 0:
                splits.append((train_idx, test_idx))

        logger.debug(f"Created {len(splits)} splits: initial_train={initial_train_size}")
        return splits

    def validate(
        self,
        model: BaseEstimator,
        X: pd.DataFrame,
        y: pd.Series,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform walk-forward validation with comprehensive metrics.

        Args:
            model: Sklearn-compatible model with fit() and predict() methods
            X: Feature DataFrame
            y: Target Series
            verbose: Whether to log per-fold results

        Returns:
            Dict containing mean/std of all metrics plus fold-level results
        """
        results: Dict[str, List[float]] = {
            "mae": [],
            "rmse": [],
            "r2": [],
            "mape": [],
            "directional_accuracy": [],
        }

        splits = self.split(X)

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            # Split data maintaining temporal order
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            # Train and predict
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            # Calculate regression metrics
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            # MAPE with protection against zeros
            with np.errstate(divide="ignore", invalid="ignore"):
                mape_values = np.abs((y_test - y_pred) / y_test)
                mape = np.nanmean(mape_values[np.isfinite(mape_values)]) * 100

            # Directional accuracy (critical for trading)
            dir_acc = directional_accuracy(y_test.values, y_pred)

            # Store results
            results["mae"].append(mae)
            results["rmse"].append(rmse)
            results["r2"].append(r2)
            results["mape"].append(mape if np.isfinite(mape) else np.nan)
            results["directional_accuracy"].append(dir_acc)

            if verbose:
                logger.info(
                    f"Fold {fold_idx + 1}/{len(splits)}: "
                    f"MAE={mae:.4f}, RMSE={rmse:.4f}, "
                    f"R2={r2:.4f}, Dir.Acc={dir_acc:.2%}"
                )

        # Aggregate results
        summary = {
            "mae_mean": np.mean(results["mae"]),
            "mae_std": np.std(results["mae"]),
            "rmse_mean": np.mean(results["rmse"]),
            "rmse_std": np.std(results["rmse"]),
            "r2_mean": np.mean(results["r2"]),
            "r2_std": np.std(results["r2"]),
            "mape_mean": np.nanmean(results["mape"]),
            "directional_accuracy_mean": np.nanmean(results["directional_accuracy"]),
            "directional_accuracy_std": np.nanstd(results["directional_accuracy"]),
            "n_folds": len(splits),
            "fold_results": results,
        }

        if verbose:
            logger.info(
                f"Walk-Forward CV Complete: "
                f"MAE={summary['mae_mean']:.4f}±{summary['mae_std']:.4f}, "
                f"Dir.Acc={summary['directional_accuracy_mean']:.2%}"
            )

        return summary

    def validate_classifier(
        self,
        model: BaseEstimator,
        X: pd.DataFrame,
        y: pd.Series,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Walk-forward validation for classification models.

        Args:
            model: Sklearn-compatible classifier
            X: Feature DataFrame
            y: Target Series (class labels)
            verbose: Whether to log per-fold results

        Returns:
            Dict with accuracy metrics
        """
        results: Dict[str, List[float]] = {
            "accuracy": [],
        }

        splits = self.split(X)

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            acc = accuracy_score(y_test, y_pred)
            results["accuracy"].append(acc)

            if verbose:
                logger.info(f"Fold {fold_idx + 1}/{len(splits)}: Accuracy={acc:.2%}")

        summary = {
            "accuracy_mean": np.mean(results["accuracy"]),
            "accuracy_std": np.std(results["accuracy"]),
            "n_folds": len(splits),
            "fold_results": results,
        }

        if verbose:
            logger.info(
                f"Walk-Forward CV Complete: "
                f"Accuracy={summary['accuracy_mean']:.2%}±{summary['accuracy_std']:.2%}"
            )

        return summary
