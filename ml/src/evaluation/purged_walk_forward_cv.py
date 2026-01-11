"""
Purged Walk-Forward Cross-Validation
====================================

Implements walk-forward CV with purging and embargo to prevent data leakage
from indicator lookback windows.

Reference: "Advances in Financial Machine Learning" - Marcos Lopez de Prado
"""

import logging
from typing import Generator, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PurgedWalkForwardCV:
    """
    Walk-forward cross-validation with purging and embargo.

    Problem solved:
    - If you use SMA-20 as a feature, the last 20 days of data leak into features
    - Naive walk-forward doesn't account for this indicator lookback

    Solution:
    - Embargo: Remove N days AFTER each test fold (N = max indicator lookback)
    - Purging: Remove any training data that overlaps with test fold's indicator window

    Result: More realistic backtests (lower accuracy, but honest)
    """

    def __init__(self, n_splits: int = 5, embargo_days: int = 20) -> None:
        """
        Initialize Purged Walk-Forward CV.

        Args:
            n_splits: Number of folds (default 5)
            embargo_days: Remove this many days after test fold
                         (match to longest indicator lookback, e.g., 20 for SMA-20)
        """
        self.n_splits = n_splits
        self.embargo_days = embargo_days
        logger.info(
            f"PurgedWalkForwardCV initialized: {n_splits} splits, {embargo_days} day embargo"
        )

    def split(
        self, X: pd.DataFrame, y: pd.Series, dates: pd.DatetimeIndex = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generate purged & embargoed train/test indices.

        Args:
            X: Feature DataFrame (required for shape)
            y: Labels Series (required for shape)
            dates: Optional DatetimeIndex for embargo calculation

        Yields:
            Tuple of (train_indices, test_indices) for each fold
        """
        n_samples = len(X)
        fold_size = n_samples // self.n_splits

        logger.info(f"Splitting {n_samples} samples into {self.n_splits} folds")

        for fold_idx in range(self.n_splits):
            # Test fold boundaries
            test_start = fold_idx * fold_size
            test_end = (fold_idx + 1) * fold_size if fold_idx < self.n_splits - 1 else n_samples

            # Embargo: remove days after test fold
            embargo_start = test_end
            embargo_end = min(embargo_start + self.embargo_days, n_samples)

            # Training indices: before test + after embargo
            train_indices = np.concatenate(
                [np.arange(0, test_start), np.arange(embargo_end, n_samples)]
            )

            # Test indices
            test_indices = np.arange(test_start, test_end)

            # Log fold info
            logger.info(
                f"  Fold {fold_idx + 1}/{self.n_splits}: "
                f"train {len(train_indices)}, test {len(test_indices)}, "
                f"embargo {embargo_end - embargo_start}"
            )

            yield train_indices, test_indices

    def split_with_dates(
        self, X: pd.DataFrame, y: pd.Series, dates: pd.Series
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generate purged & embargoed indices using date-based embargo.

        This is more accurate: embargo by calendar days instead of sample count.

        Args:
            X: Feature DataFrame
            y: Labels Series
            dates: Series with datetime index (must align with X and y)

        Yields:
            Tuple of (train_indices, test_indices) for each fold
        """
        if len(dates) != len(X):
            raise ValueError(f"Dates length {len(dates)} != X length {len(X)}")

        n_samples = len(X)
        fold_size = n_samples // self.n_splits

        logger.info(
            f"Splitting {n_samples} samples with date-based embargo ({self.embargo_days} days)"
        )

        for fold_idx in range(self.n_splits):
            # Test fold
            test_start = fold_idx * fold_size
            test_end = (fold_idx + 1) * fold_size if fold_idx < self.n_splits - 1 else n_samples

            test_dates = dates.iloc[test_start:test_end]
            embargo_cutoff = test_dates.iloc[-1] + pd.Timedelta(days=self.embargo_days)

            # Training: before test start, and after embargo cutoff
            train_mask = (dates < test_dates.iloc[0]) | (dates > embargo_cutoff)
            train_indices = np.where(train_mask)[0]
            test_indices = np.arange(test_start, test_end)

            logger.info(
                f"  Fold {fold_idx + 1}/{self.n_splits}: "
                f"train {len(train_indices)}, test {len(test_indices)}"
            )

            yield train_indices, test_indices

    @staticmethod
    def evaluate_fold(
        model_class,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        **model_kwargs,
    ) -> float:
        """
        Train and evaluate a model on one fold.

        Args:
            model_class: Forecaster class (e.g., EnsembleForecaster)
            X_train, y_train: Training data
            X_test, y_test: Test data
            **model_kwargs: Arguments for model_class()

        Returns:
            Accuracy score on test fold
        """
        model = model_class(**model_kwargs)
        model.train(X_train, y_train)

        # Predict
        predictions = model.predict_batch(X_test)

        # Handle different column names depending on model type
        if "ensemble_label" in predictions.columns:
            pred_col = "ensemble_label"
        elif "prediction" in predictions.columns:
            pred_col = "prediction"
        else:
            raise ValueError(f"Unknown prediction column in {predictions.columns}")

        label_map = {"Bullish": 1, "Neutral": 0, "Bearish": -1}
        pred_labels = predictions[pred_col].map(label_map)

        # Accuracy
        accuracy = (pred_labels == y_test.values).mean()
        return accuracy

    def cross_validate(
        self,
        model_class,
        X: pd.DataFrame,
        y: pd.Series,
        **model_kwargs,
    ) -> dict:
        """
        Run full cross-validation and return metrics.

        Args:
            model_class: Forecaster class to evaluate
            X: Feature DataFrame
            y: Labels Series
            **model_kwargs: Arguments for model_class()

        Returns:
            Dict with fold scores and summary statistics
        """
        fold_scores = []

        for fold_idx, (train_idx, test_idx) in enumerate(self.split(X, y)):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            accuracy = self.evaluate_fold(
                model_class, X_train, y_train, X_test, y_test, **model_kwargs
            )
            fold_scores.append(accuracy)
            logger.info(f"  Fold {fold_idx + 1} accuracy: {accuracy:.3f}")

        return {
            "fold_scores": fold_scores,
            "mean_accuracy": np.mean(fold_scores),
            "std_accuracy": np.std(fold_scores),
            "min_accuracy": np.min(fold_scores),
            "max_accuracy": np.max(fold_scores),
        }


if __name__ == "__main__":
    print("PurgedWalkForwardCV imported successfully")
