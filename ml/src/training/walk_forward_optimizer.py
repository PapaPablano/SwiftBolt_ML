"""
Walk-Forward Optimizer with Per-Window Hyperparameter Tuning
=============================================================

Implements rigorous walk-forward validation methodology from research on
LSTM-ARIMA hybrid models for financial forecasting (University of Warsaw, 2024).

Key Features:
- In-sample: 1000 days training + 250 days validation
- Out-of-sample: 250 days test (no data reuse)
- Per-window hyperparameter retraining prevents regime overfitting
- Divergence monitoring detects overfitting early (val_rmse vs test_rmse)
- Sequential window rolling captures nonstationary market conditions

Based on: "LSTM-ARIMA as a hybrid approach in algorithmic investment"
https://www.sciencedirect.com/science/article/pii/S0950705125006094
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class WindowConfig:
    """Configuration for a single walk-forward window."""

    train_start: datetime
    train_end: datetime
    val_start: datetime
    val_end: datetime
    test_start: datetime
    test_end: datetime
    window_id: int

    def __str__(self) -> str:
        """Return human-readable window description."""
        return (
            f"Window {self.window_id}: "
            f"Train {self.train_start.date()} - {self.train_end.date()}, "
            f"Val {self.val_start.date()} - {self.val_end.date()}, "
            f"Test {self.test_start.date()} - {self.test_end.date()}"
        )


@dataclass
class WindowResult:
    """Results from optimizing a single walk-forward window."""

    window_id: int
    best_params: Dict = field(default_factory=dict)
    val_rmse: float = 0.0
    test_rmse: float = 0.0
    divergence: float = 0.0  # abs(val_rmse - test_rmse) / val_rmse
    n_train_samples: int = 0
    n_val_samples: int = 0
    n_test_samples: int = 0
    trained_at: datetime = field(default_factory=datetime.now)
    models_used: List[str] = field(default_factory=list)
    train_rmse: Optional[float] = None

    def __str__(self) -> str:
        """Return human-readable result summary."""
        return (
            f"Window {self.window_id}: "
            f"val_rmse={self.val_rmse:.4f}, test_rmse={self.test_rmse:.4f}, "
            f"divergence={self.divergence:.2%}"
        )


class WalkForwardOptimizer:
    """
    Walk-forward optimizer with divergence monitoring for overfitting detection.

    Prevents overfitting by:
    1. No look-ahead bias (sequential data splits)
    2. Hyperparameter tuning on validation set only
    3. Test set completely held out until final evaluation
    4. Per-window retraining captures market regime changes
    5. Divergence tracking (val vs test performance)

    Attributes:
        train_days: Days for training data (default: 1000)
        val_days: Days for validation data (default: 250)
        test_days: Days for test data (default: 250)
        step_size: Days to roll forward window (default: 1)
        divergence_threshold: Divergence > this indicates overfitting (default: 0.20)
    """

    def __init__(
        self,
        train_days: int = 1000,
        val_days: int = 250,
        test_days: int = 250,
        step_size: int = 1,
        divergence_threshold: float = 0.20,
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            train_days: Training window size (days)
            val_days: Validation window size (days)
            test_days: Test window size (days)
            step_size: Days to roll forward (1 = daily, 5 = weekly)
            divergence_threshold: Divergence threshold for overfitting alert
        """
        self.train_days = train_days
        self.val_days = val_days
        self.test_days = test_days
        self.step_size = step_size
        self.divergence_threshold = divergence_threshold

        self.window_results: List[WindowResult] = []
        self.divergence_history: List[float] = []

        logger.info(
            "WalkForwardOptimizer initialized: "
            "train=%d days, val=%d days, test=%d days, step=%d days",
            train_days,
            val_days,
            test_days,
            step_size,
        )

    def create_windows(self, data: pd.DataFrame) -> List[WindowConfig]:
        """
        Create sequential walk-forward windows from data.

        Args:
            data: DataFrame with datetime index

        Returns:
            List of WindowConfig objects
        """
        windows = []
        start_date = data.index.min()
        end_date = data.index.max()

        total_window_days = self.train_days + self.val_days + self.test_days
        current_start = start_date
        window_id = 0

        logger.info(
            "Creating walk-forward windows from %s to %s (span: %d days)",
            start_date.date(),
            end_date.date(),
            (end_date - start_date).days,
        )

        while True:
            train_end = current_start + timedelta(days=self.train_days)
            val_end = train_end + timedelta(days=self.val_days)
            test_end = val_end + timedelta(days=self.test_days)

            if test_end > end_date:
                logger.info(
                    "Reached end of data at window %d "
                    "(test_end %s > end_date %s)",
                    window_id,
                    test_end.date(),
                    end_date.date(),
                )
                break

            window = WindowConfig(
                train_start=current_start,
                train_end=train_end,
                val_start=train_end,
                val_end=val_end,
                test_start=val_end,
                test_end=test_end,
                window_id=window_id,
            )
            windows.append(window)

            logger.debug("Created %s", window)

            current_start += timedelta(days=self.step_size)
            window_id += 1

        logger.info(
            "Created %d walk-forward windows (each %d days total)",
            len(windows),
            total_window_days,
        )

        return windows

    def optimize_window(
        self,
        window: WindowConfig,
        data: pd.DataFrame,
        ensemble,
        param_grid: Optional[Dict] = None,
    ) -> WindowResult:
        """
        Optimize hyperparameters for a single walk-forward window.

        Steps:
        1. Extract train/val/test data (no overlap, no look-ahead)
        2. Tune hyperparameters on validation data only
        3. Train on train+val combined with best params
        4. Evaluate on held-out test set
        5. Calculate divergence (val_rmse vs test_rmse)

        Args:
            window: WindowConfig specifying data splits
            data: Full DataFrame with datetime index
            ensemble: Ensemble forecaster to optimize
            param_grid: Optional hyperparameter search grid

        Returns:
            WindowResult with performance metrics and divergence
        """
        logger.info("Optimizing %s", window)

        # Extract data for this window (no overlap, no look-ahead)
        train_data = data[window.train_start : window.train_end]
        val_data = data[window.val_start : window.val_end]
        test_data = data[window.test_start : window.test_end]

        logger.debug(
            "Window data: train=%d, val=%d, test=%d samples",
            len(train_data),
            len(val_data),
            len(test_data),
        )

        # Tune hyperparameters on validation data only
        best_params = self._tune_hyperparameters(
            train_data, val_data, param_grid, ensemble
        )

        # Train ensemble on train + validation combined with best hyperparams
        try:
            ensemble.set_hyperparameters(best_params)
            ensemble.train(pd.concat([train_data, val_data]))
            logger.debug("Ensemble trained with best params")
        except Exception as e:
            logger.warning("Ensemble training failed: %s", e)
            best_params = {}

        # Evaluate on validation set (for divergence calculation)
        try:
            val_pred = ensemble.predict(val_data)
            val_rmse = self._calculate_rmse(val_pred, val_data.get("actual", val_data.iloc[:, 0]))
        except Exception as e:
            logger.warning("Validation prediction failed: %s", e)
            val_rmse = np.inf

        # Evaluate on held-out test set (final performance)
        try:
            test_pred = ensemble.predict(test_data)
            test_rmse = self._calculate_rmse(test_pred, test_data.get("actual", test_data.iloc[:, 0]))
        except Exception as e:
            logger.warning("Test prediction failed: %s", e)
            test_rmse = np.inf

        # Calculate divergence (overfitting indicator)
        if val_rmse > 0:
            divergence = abs(val_rmse - test_rmse) / val_rmse
        else:
            divergence = 0.0

        self.divergence_history.append(divergence)

        # Log if overfitting detected
        if divergence > self.divergence_threshold:
            logger.warning(
                "Window %d: HIGH DIVERGENCE %.2f%% indicates overfitting "
                "(val_rmse=%.4f, test_rmse=%.4f). "
                "Consider reducing model complexity.",
                window.window_id,
                divergence * 100,
                val_rmse,
                test_rmse,
            )
        else:
            logger.info(
                "Window %d: Divergence %.2f%% (val_rmse=%.4f, test_rmse=%.4f)",
                window.window_id,
                divergence * 100,
                val_rmse,
                test_rmse,
            )

        result = WindowResult(
            window_id=window.window_id,
            best_params=best_params,
            val_rmse=val_rmse,
            test_rmse=test_rmse,
            divergence=divergence,
            n_train_samples=len(train_data),
            n_val_samples=len(val_data),
            n_test_samples=len(test_data),
            trained_at=datetime.now(),
            models_used=self._get_active_models(ensemble),
        )

        self.window_results.append(result)
        return result

    def _tune_hyperparameters(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame,
        param_grid: Optional[Dict],
        ensemble,
    ) -> Dict:
        """
        Tune hyperparameters on validation set only.

        This method prevents validation leakage by:
        1. Training on train_data
        2. Evaluating on val_data (never on train_data)
        3. Selecting hyperparameters that minimize val_data loss

        Args:
            train_data: Training data for model fitting
            val_data: Validation data for hyperparameter selection
            param_grid: Search grid for hyperparameter optimization
            ensemble: Ensemble model to tune

        Returns:
            Dictionary of best hyperparameters
        """
        if param_grid is None or not param_grid:
            logger.debug("No hyperparameter grid provided, using defaults")
            return {}

        logger.debug("Tuning hyperparameters on %d validation samples", len(val_data))

        # Simple grid search on validation set
        best_params = {}
        best_val_loss = np.inf

        for params_combo in self._generate_param_combos(param_grid):
            try:
                # Train with this parameter combo
                ensemble.set_hyperparameters(params_combo)
                ensemble.train(train_data)

                # Evaluate on validation set (NOT on training set!)
                val_pred = ensemble.predict(val_data)
                val_loss = self._calculate_rmse(val_pred, val_data.get("actual", val_data.iloc[:, 0]))

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    best_params = params_combo
                    logger.debug("Found better params with val_loss=%.4f", val_loss)

            except Exception as e:
                logger.debug("Parameter combo failed: %s", e)
                continue

        logger.debug("Best hyperparameters: %s (val_loss=%.4f)", best_params, best_val_loss)
        return best_params

    def _generate_param_combos(self, param_grid: Dict) -> List[Dict]:
        """
        Generate all combinations of hyperparameters.

        Args:
            param_grid: Dictionary of param_name -> list of values

        Returns:
            List of parameter dictionaries
        """
        if not param_grid:
            return [{}]

        # Simple cartesian product
        from itertools import product

        keys = param_grid.keys()
        values = param_grid.values()
        return [dict(zip(keys, combo)) for combo in product(*values)]

    def _calculate_rmse(
        self, predictions: np.ndarray, actuals: np.ndarray
    ) -> float:
        """
        Calculate root mean squared error.

        Args:
            predictions: Predicted values
            actuals: Actual values

        Returns:
            RMSE value
        """
        if len(predictions) == 0 or len(actuals) == 0:
            return np.inf

        try:
            # Handle Series or array
            if hasattr(actuals, 'values'):
                actuals = actuals.values
            if hasattr(predictions, 'values'):
                predictions = predictions.values

            # Ensure same length
            min_len = min(len(predictions), len(actuals))
            predictions = predictions[:min_len]
            actuals = actuals[:min_len]

            rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
            return rmse if np.isfinite(rmse) else np.inf
        except Exception as e:
            logger.warning("RMSE calculation failed: %s", e)
            return np.inf

    def _get_active_models(self, ensemble) -> List[str]:
        """
        Get list of active models from ensemble.

        Args:
            ensemble: Ensemble object

        Returns:
            List of model names
        """
        models = []
        for attr in ["enable_lstm", "enable_arima_garch", "enable_gb", "enable_rf"]:
            if hasattr(ensemble, attr) and getattr(ensemble, attr):
                model_name = attr.replace("enable_", "").upper()
                models.append(model_name)
        return models

    def get_divergence_summary(self) -> Dict[str, float]:
        """
        Get summary statistics of divergence history.

        Returns:
            Dictionary with divergence metrics
        """
        if not self.divergence_history:
            return {
                "mean_divergence": 0.0,
                "max_divergence": 0.0,
                "n_overfitting_windows": 0,
                "total_windows": 0,
                "divergence_threshold": self.divergence_threshold,
            }

        divergences = np.array(self.divergence_history)
        return {
            "mean_divergence": float(np.mean(divergences)),
            "max_divergence": float(np.max(divergences)),
            "min_divergence": float(np.min(divergences)),
            "std_divergence": float(np.std(divergences)),
            "n_overfitting_windows": int(
                np.sum(divergences > self.divergence_threshold)
            ),
            "total_windows": len(divergences),
            "divergence_threshold": self.divergence_threshold,
            "pct_overfitting": float(
                np.mean(divergences > self.divergence_threshold) * 100
            ),
        }

    def run_backtest(
        self,
        data: pd.DataFrame,
        ensemble,
        param_grid: Optional[Dict] = None,
    ) -> Dict:
        """
        Run full walk-forward backtest on entire dataset.

        Args:
            data: Full historical data
            ensemble: Ensemble forecaster
            param_grid: Hyperparameter search grid

        Returns:
            Dictionary with backtest results
        """
        logger.info("Starting walk-forward backtest")

        # Create windows
        windows = self.create_windows(data)

        if not windows:
            logger.error("No walk-forward windows created")
            return {"error": "No windows created", "total_windows": 0}

        logger.info("Running optimization on %d windows", len(windows))

        # Optimize each window
        for i, window in enumerate(windows):
            logger.info("Processing window %d/%d", i + 1, len(windows))
            result = self.optimize_window(window, data, ensemble, param_grid)

        # Compile results
        summary = self.get_divergence_summary()
        summary.update({
            "total_windows": len(self.window_results),
            "mean_test_rmse": float(
                np.mean([r.test_rmse for r in self.window_results if r.test_rmse < np.inf])
            ),
            "mean_val_rmse": float(
                np.mean([r.val_rmse for r in self.window_results if r.val_rmse < np.inf])
            ),
            "window_results": self.window_results,
        })

        logger.info("Walk-forward backtest complete: %s", summary)
        return summary
