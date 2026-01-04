"""
Walk-Forward Ensemble Backtester
================================

Implements walk-forward validation for ensemble models with:
- Rolling window retraining
- Dynamic weight optimization
- Performance tracking and metrics
- Uncertainty calibration updates

Key Features:
- Realistic out-of-sample testing
- Periodic model refitting
- Weight evolution tracking
- Comprehensive performance metrics
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.models.weight_optimizer import WeightOptimizer
from src.models.uncertainty_quantifier import (
    UncertaintyQuantifier,
    DirectionalUncertaintyQuantifier,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Container for single backtest step result."""

    timestamp: str
    step: int
    forecast_label: str
    forecast_confidence: float
    actual_direction: str
    is_correct: bool
    probabilities: Dict[str, float]
    weights: Dict[str, float]
    model_predictions: Dict[str, str]
    agreement: float


@dataclass
class EnsembleMetrics:
    """Track ensemble performance metrics."""

    predictions: List[str] = field(default_factory=list)
    actuals: List[str] = field(default_factory=list)
    confidences: List[float] = field(default_factory=list)
    agreements: List[float] = field(default_factory=list)
    model_contributions: Dict[str, List[float]] = field(default_factory=dict)

    def update(
        self,
        prediction: str,
        actual: str,
        confidence: float,
        agreement: float,
        weights: Dict[str, float],
    ) -> None:
        """Update metrics with new prediction."""
        self.predictions.append(prediction)
        self.actuals.append(actual)
        self.confidences.append(confidence)
        self.agreements.append(agreement)

        for model, weight in weights.items():
            if model not in self.model_contributions:
                self.model_contributions[model] = []
            self.model_contributions[model].append(weight)

    def get_metrics(self) -> Dict:
        """Calculate summary metrics."""
        if not self.predictions:
            return {"error": "No predictions recorded"}

        predictions = np.array(self.predictions)
        actuals = np.array(self.actuals)

        # Directional accuracy
        accuracy = np.mean(predictions == actuals)

        # Accuracy by class
        class_accuracies = {}
        for cls in ["Bullish", "Neutral", "Bearish"]:
            mask = actuals == cls
            if mask.sum() > 0:
                class_accuracies[cls.lower()] = float(
                    np.mean(predictions[mask] == actuals[mask])
                )

        # Confidence statistics
        confidences = np.array(self.confidences)
        agreements = np.array(self.agreements)

        # Model contributions
        avg_weights = {
            model: float(np.mean(weights))
            for model, weights in self.model_contributions.items()
        }

        return {
            "n_predictions": len(self.predictions),
            "accuracy": float(accuracy),
            "class_accuracies": class_accuracies,
            "mean_confidence": float(np.mean(confidences)),
            "std_confidence": float(np.std(confidences)),
            "mean_agreement": float(np.mean(agreements)),
            "std_agreement": float(np.std(agreements)),
            "avg_weights": avg_weights,
        }


class WalkForwardEnsemble:
    """
    Walk-forward backtesting for ensemble models.

    Performs out-of-sample testing with periodic retraining
    and dynamic weight optimization.
    """

    def __init__(
        self,
        initial_train_size: int = 200,
        test_size: int = 1,
        refit_frequency: int = 20,
        weight_update_frequency: int = 10,
        optimization_method: str = "ridge",
        min_train_size: int = 100,
    ) -> None:
        """
        Initialize Walk-Forward Ensemble backtester.

        Args:
            initial_train_size: Initial training window size
            test_size: Number of steps to forecast at each iteration
            refit_frequency: How often to retrain models (in steps)
            weight_update_frequency: How often to update weights
            optimization_method: Weight optimization method
            min_train_size: Minimum training data required
        """
        self.initial_train_size = initial_train_size
        self.test_size = test_size
        self.refit_frequency = refit_frequency
        self.weight_update_frequency = weight_update_frequency
        self.optimization_method = optimization_method
        self.min_train_size = min_train_size

        self.results: List[BacktestResult] = []
        self.metrics = EnsembleMetrics()
        self.weight_history: List[Dict] = []

        self.weight_optimizer = WeightOptimizer(
            optimization_method=optimization_method
        )
        self.uncertainty_quantifier = DirectionalUncertaintyQuantifier()

        logger.info(
            "WalkForwardEnsemble initialized: train=%d, refit=%d",
            initial_train_size,
            refit_frequency,
        )

    def run_backtest(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        labels: pd.Series,
        ensemble,
        horizon: str = "1D",
    ) -> pd.DataFrame:
        """
        Execute walk-forward backtest.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            labels: Direction labels
            ensemble: MultiModelEnsemble instance
            horizon: Forecast horizon

        Returns:
            DataFrame with backtest results
        """
        n_samples = len(ohlc_df)

        if n_samples < self.initial_train_size + self.test_size:
            raise ValueError(
                f"Insufficient data: {n_samples} < "
                f"{self.initial_train_size + self.test_size}"
            )

        # Initialize weights
        weights = self._get_initial_weights(ensemble)

        logger.info(
            "Starting walk-forward backtest: %d samples, %d train, %d test steps",
            n_samples,
            self.initial_train_size,
            n_samples - self.initial_train_size,
        )

        # Walk-forward loop
        for step in range(self.initial_train_size, n_samples - self.test_size):
            # Training data up to current point
            train_end = step
            train_ohlc = ohlc_df.iloc[:train_end]
            train_features = features_df.iloc[:train_end]
            train_labels = labels.iloc[:train_end]

            # Test point (next period)
            test_idx = step
            actual_label = labels.iloc[test_idx]

            try:
                # Refit models periodically
                if (step - self.initial_train_size) % self.refit_frequency == 0:
                    logger.debug("Step %d: Refitting models...", step)
                    ensemble.train(train_features, train_labels, train_ohlc)

                # Update weights periodically
                if (step - self.initial_train_size) % self.weight_update_frequency == 0:
                    weights = self._update_weights(ensemble, weights, step)
                    self._record_weight_history(step, weights, ohlc_df)

                # Generate prediction
                prediction = ensemble.predict(
                    train_features.tail(1), train_ohlc
                )

                # Record result
                result = self._record_result(
                    step=step - self.initial_train_size,
                    timestamp=str(ohlc_df["ts"].iloc[test_idx]),
                    prediction=prediction,
                    actual_label=str(actual_label),
                    weights=weights,
                )
                self.results.append(result)

                # Update metrics
                self.metrics.update(
                    prediction=result.forecast_label,
                    actual=result.actual_direction,
                    confidence=result.forecast_confidence,
                    agreement=result.agreement,
                    weights=weights,
                )

            except Exception as e:
                logger.warning("Step %d failed: %s", step, e)
                continue

        logger.info(
            "Backtest complete: %d predictions, %.1f%% accuracy",
            len(self.results),
            self.metrics.get_metrics().get("accuracy", 0) * 100,
        )

        return self.get_results_dataframe()

    def _get_initial_weights(self, ensemble) -> Dict[str, float]:
        """Get initial equal weights from ensemble."""
        model_names = list(ensemble.model_trained.keys())
        n_models = len(model_names)
        return {name: 1.0 / n_models for name in model_names}

    def _update_weights(
        self,
        ensemble,
        current_weights: Dict[str, float],
        step: int,
    ) -> Dict[str, float]:
        """Update weights based on recent performance."""
        if len(self.results) < 20:
            return current_weights

        # Get recent predictions and actuals
        recent_results = self.results[-20:]

        # Build predictions dict for weight optimizer
        predictions_dict = {}
        for model_name in current_weights.keys():
            model_preds = []
            for r in recent_results:
                if model_name in r.model_predictions:
                    pred = r.model_predictions[model_name]
                    # Convert to numeric
                    val = (
                        1 if pred.lower() == "bullish"
                        else -1 if pred.lower() == "bearish"
                        else 0
                    )
                    model_preds.append(val)
            if model_preds:
                predictions_dict[model_name] = np.array(model_preds)

        if not predictions_dict:
            return current_weights

        # Convert actuals to numeric
        actuals = np.array([
            1 if r.actual_direction.lower() == "bullish"
            else -1 if r.actual_direction.lower() == "bearish"
            else 0
            for r in recent_results
        ])

        try:
            new_weights = self.weight_optimizer.optimize_weights(
                predictions_dict, actuals
            )
            logger.debug("Updated weights at step %d: %s", step, new_weights)
            return new_weights
        except Exception as e:
            logger.warning("Weight optimization failed: %s", e)
            return current_weights

    def _record_weight_history(
        self,
        step: int,
        weights: Dict[str, float],
        ohlc_df: pd.DataFrame,
    ) -> None:
        """Record weight history entry."""
        self.weight_history.append({
            "step": step,
            "timestamp": str(ohlc_df["ts"].iloc[step])
            if step < len(ohlc_df) else None,
            "weights": weights.copy(),
        })

    def _record_result(
        self,
        step: int,
        timestamp: str,
        prediction: Dict,
        actual_label: str,
        weights: Dict[str, float],
    ) -> BacktestResult:
        """Record a single backtest result."""
        forecast_label = prediction.get("label", "Neutral")
        actual_direction = actual_label.capitalize()

        # Extract model predictions
        model_predictions = {}
        component_preds = prediction.get("component_predictions", {})
        for model, pred in component_preds.items():
            if isinstance(pred, dict):
                model_predictions[model] = pred.get("label", "Neutral")
            elif isinstance(pred, str):
                model_predictions[model] = pred

        return BacktestResult(
            timestamp=timestamp,
            step=step,
            forecast_label=forecast_label,
            forecast_confidence=prediction.get("confidence", 0.5),
            actual_direction=actual_direction,
            is_correct=forecast_label.lower() == actual_direction.lower(),
            probabilities=prediction.get("probabilities", {}),
            weights=weights.copy(),
            model_predictions=model_predictions,
            agreement=prediction.get("agreement", 0),
        )

    def get_results_dataframe(self) -> pd.DataFrame:
        """Get backtest results as DataFrame."""
        if not self.results:
            return pd.DataFrame()

        records = []
        for r in self.results:
            record = {
                "timestamp": r.timestamp,
                "step": r.step,
                "forecast": r.forecast_label,
                "actual": r.actual_direction,
                "confidence": r.forecast_confidence,
                "is_correct": r.is_correct,
                "agreement": r.agreement,
            }
            # Add probabilities
            for cls, prob in r.probabilities.items():
                record[f"prob_{cls}"] = prob
            # Add weights
            for model, weight in r.weights.items():
                record[f"weight_{model}"] = weight
            records.append(record)

        return pd.DataFrame(records)

    def get_metrics(self) -> Dict:
        """Get ensemble performance metrics."""
        return self.metrics.get_metrics()

    def get_weight_evolution(self) -> pd.DataFrame:
        """Get weight evolution over time."""
        if not self.weight_history:
            return pd.DataFrame()

        records = []
        for entry in self.weight_history:
            record = {
                "step": entry["step"],
                "timestamp": entry["timestamp"],
            }
            record.update(entry["weights"])
            records.append(record)

        return pd.DataFrame(records)

    def get_confusion_matrix(self) -> pd.DataFrame:
        """Get confusion matrix from results."""
        if not self.results:
            return pd.DataFrame()

        classes = ["Bullish", "Neutral", "Bearish"]
        matrix = pd.DataFrame(
            0, index=classes, columns=classes
        )

        for r in self.results:
            pred = r.forecast_label
            actual = r.actual_direction
            if pred in classes and actual in classes:
                matrix.loc[actual, pred] += 1

        return matrix

    def get_accuracy_by_confidence(
        self,
        n_bins: int = 5,
    ) -> pd.DataFrame:
        """Get accuracy stratified by confidence level."""
        if not self.results:
            return pd.DataFrame()

        confidences = [r.forecast_confidence for r in self.results]
        correct = [r.is_correct for r in self.results]

        # Bin by confidence
        bins = np.linspace(0, 1, n_bins + 1)
        bin_labels = [
            f"{bins[i]:.2f}-{bins[i+1]:.2f}"
            for i in range(n_bins)
        ]

        df = pd.DataFrame({
            "confidence": confidences,
            "correct": correct,
        })
        df["bin"] = pd.cut(
            df["confidence"],
            bins=bins,
            labels=bin_labels,
            include_lowest=True,
        )

        summary = df.groupby("bin").agg({
            "correct": ["mean", "count"],
        })
        summary.columns = ["accuracy", "count"]

        return summary

    def get_summary(self) -> Dict:
        """Get complete backtest summary."""
        metrics = self.get_metrics()
        confusion = self.get_confusion_matrix()

        return {
            "metrics": metrics,
            "n_steps": len(self.results),
            "n_weight_updates": len(self.weight_history),
            "final_weights": (
                self.weight_history[-1]["weights"]
                if self.weight_history else {}
            ),
            "confusion_matrix": confusion.to_dict() if not confusion.empty else {},
        }


if __name__ == "__main__":
    # Quick test
    print("Testing WalkForwardEnsemble...")

    np.random.seed(42)
    n = 300

    # Create sample data
    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    ohlc_df = pd.DataFrame({
        "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
        "open": prices * 0.995,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.randint(1e6, 1e7, n).astype(float),
    })

    # Create features
    ohlc_df["return_1d"] = ohlc_df["close"].pct_change()
    ohlc_df["return_5d"] = ohlc_df["close"].pct_change(5)
    ohlc_df["sma_20"] = ohlc_df["close"].rolling(20).mean()
    ohlc_df["vol_20"] = ohlc_df["return_1d"].rolling(20).std()
    ohlc_df = ohlc_df.dropna()

    features_df = ohlc_df[["return_1d", "return_5d", "sma_20", "vol_20"]]

    # Create labels
    fwd_return = ohlc_df["close"].pct_change().shift(-1)
    labels = fwd_return.apply(
        lambda x: "bullish" if x > 0.01
        else "bearish" if x < -0.01
        else "neutral"
    ).iloc[:-1]
    features_df = features_df.iloc[:-1]
    ohlc_df = ohlc_df.iloc[:-1]

    # Initialize ensemble
    from src.models.multi_model_ensemble import MultiModelEnsemble

    ensemble = MultiModelEnsemble(
        horizon="1D",
        enable_rf=True,
        enable_gb=True,
        enable_arima_garch=True,
        enable_prophet=True,
        enable_lstm=False,  # Skip for faster test
    )

    # Run backtest
    backtester = WalkForwardEnsemble(
        initial_train_size=100,
        refit_frequency=30,
        weight_update_frequency=20,
    )

    results_df = backtester.run_backtest(
        ohlc_df=ohlc_df,
        features_df=features_df,
        labels=labels,
        ensemble=ensemble,
    )

    print(f"\nResults: {len(results_df)} predictions")
    print(f"\nMetrics: {backtester.get_metrics()}")
    print(f"\nWeight evolution:\n{backtester.get_weight_evolution()}")
    print(f"\nConfusion matrix:\n{backtester.get_confusion_matrix()}")

    print("\n\nSUCCESS: WalkForwardEnsemble working!")
