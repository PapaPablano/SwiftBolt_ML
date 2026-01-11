"""
Ensemble Manager: Main Orchestrator for ML Forecasting Pipeline
================================================================

Coordinates all ensemble components:
- MultiModelEnsemble (RF, GB, ARIMA-GARCH, Prophet, LSTM)
- WeightOptimizer (dynamic weight learning)
- UncertaintyQuantifier (confidence calibration)
- WalkForwardEnsemble (backtesting)

Provides a unified API for:
- Training all models
- Generating forecasts
- Optimizing weights
- Running backtests
- Exporting configurations
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.models.multi_model_ensemble import MultiModelEnsemble
from src.models.weight_optimizer import WeightOptimizer, AdaptiveWeightOptimizer
from src.models.uncertainty_quantifier import (
    UncertaintyQuantifier,
    DirectionalUncertaintyQuantifier,
)
from src.models.walk_forward_ensemble import WalkForwardEnsemble

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Container for ensemble forecast result."""

    timestamp: str
    label: str
    confidence: float
    probabilities: Dict[str, float]
    forecast_return: Optional[float]
    forecast_volatility: Optional[float]
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    agreement: float
    n_models: int
    weights: Dict[str, float]
    component_predictions: Dict[str, Any]
    calibrated: bool = False


@dataclass
class ErrorRecord:
    """Container for error logging."""

    timestamp: str
    operation: str
    model: Optional[str]
    error: str
    details: Optional[Dict] = None


class EnsembleManager:
    """
    Main orchestrator for ensemble forecasting.

    Coordinates model training, prediction, weight optimization,
    and uncertainty quantification into a single unified interface.
    """

    def __init__(
        self,
        horizon: str = "1D",
        enable_rf: bool = True,
        enable_gb: bool = True,
        enable_arima_garch: bool = True,
        enable_prophet: bool = True,
        enable_lstm: bool = False,
        confidence_level: float = 0.95,
        optimization_method: str = "ridge",
        adaptive_weights: bool = False,
    ) -> None:
        """
        Initialize Ensemble Manager.

        Args:
            horizon: Forecast horizon ("1D", "1W", etc.)
            enable_rf: Enable Random Forest
            enable_gb: Enable Gradient Boosting
            enable_arima_garch: Enable ARIMA-GARCH
            enable_prophet: Enable Prophet
            enable_lstm: Enable LSTM
            confidence_level: Confidence level for intervals
            optimization_method: Weight optimization method
            adaptive_weights: Use regime-adaptive weight optimization
        """
        self.horizon = horizon
        self.confidence_level = confidence_level
        self.optimization_method = optimization_method

        # Initialize ensemble
        self.ensemble = MultiModelEnsemble(
            horizon=horizon,
            enable_rf=enable_rf,
            enable_gb=enable_gb,
            enable_arima_garch=enable_arima_garch,
            enable_prophet=enable_prophet,
            enable_lstm=enable_lstm,
        )

        # Initialize weight optimizer
        if adaptive_weights:
            self.weight_optimizer = AdaptiveWeightOptimizer(default_method=optimization_method)
        else:
            self.weight_optimizer = WeightOptimizer(optimization_method=optimization_method)

        # Initialize uncertainty quantifier
        self.uncertainty_quantifier = DirectionalUncertaintyQuantifier(
            confidence_level=confidence_level
        )

        # State tracking
        self.is_trained = False
        self.forecast_history: List[ForecastResult] = []
        self.error_log: List[ErrorRecord] = []
        self.training_timestamp: Optional[str] = None

        logger.info(
            "EnsembleManager initialized: horizon=%s, models=%d",
            horizon,
            len(self.ensemble.model_trained),
        )

    def train(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        labels: pd.Series,
    ) -> Dict[str, bool]:
        """
        Train all ensemble models.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            labels: Direction labels

        Returns:
            Dict of {model_name: trained_successfully}
        """
        logger.info("Training ensemble models...")

        try:
            self.ensemble.train(features_df, labels, ohlc_df)
            self.is_trained = True
            self.training_timestamp = datetime.now().isoformat()

            status = {name: trained for name, trained in self.ensemble.model_trained.items()}

            logger.info(
                "Training complete: %d/%d models trained",
                sum(status.values()),
                len(status),
            )

            return status

        except Exception as e:
            self._log_error("train", None, str(e))
            raise

    def predict(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        apply_calibration: bool = True,
    ) -> ForecastResult:
        """
        Generate ensemble forecast.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            apply_calibration: Apply uncertainty calibration

        Returns:
            ForecastResult with prediction and metadata
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained. Call train() first.")

        try:
            # Get ensemble prediction
            prediction = self.ensemble.predict(features_df.tail(1), ohlc_df)

            # Aggregate probabilities with uncertainty quantification
            uq_result = self.uncertainty_quantifier.aggregate_probabilities(
                prediction.get("component_predictions", {}),
                prediction.get("weights", {}),
            )

            # Get volatility estimate
            volatility = prediction.get("forecast_volatility")

            # Calculate confidence intervals
            forecast_return = self._estimate_forecast_return(prediction)
            ci_lower = None
            ci_upper = None

            if forecast_return is not None and volatility:
                z = self.uncertainty_quantifier.z_score
                ci_lower = forecast_return - z * volatility
                ci_upper = forecast_return + z * volatility

            # Apply calibration if available
            calibrated = False
            if apply_calibration and self.uncertainty_quantifier.calibration_ratios:
                calibrated = True

            # Create result
            result = ForecastResult(
                timestamp=datetime.now().isoformat(),
                label=prediction.get("label", "Neutral"),
                confidence=prediction.get("confidence", 0.5),
                probabilities=prediction.get("probabilities", {}),
                forecast_return=forecast_return,
                forecast_volatility=volatility,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                agreement=prediction.get("agreement", 0),
                n_models=prediction.get("n_models_used", 0),
                weights=prediction.get("weights", {}),
                component_predictions=prediction.get("component_predictions", {}),
                calibrated=calibrated,
            )

            # Store in history
            self.forecast_history.append(result)

            return result

        except Exception as e:
            self._log_error("predict", None, str(e))
            raise

    def generate_forecast(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        horizon: Optional[str] = None,
    ) -> Dict:
        """
        Generate complete forecast with points.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            horizon: Override horizon (optional)

        Returns:
            Forecast dict with label, confidence, points, etc.
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained. Call train() first.")

        try:
            forecast = self.ensemble.generate_forecast(
                ohlc_df,
                features_df,
                horizon=horizon or self.horizon,
            )

            # Add uncertainty metrics
            forecast["uncertainty_metrics"] = {
                "entropy": self._calculate_entropy(forecast.get("probabilities", {})),
                "calibrated": bool(self.uncertainty_quantifier.calibration_ratios),
            }

            return forecast

        except Exception as e:
            self._log_error("generate_forecast", None, str(e))
            raise

    def optimize_weights(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        labels: pd.Series,
        method: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Optimize ensemble weights from recent performance.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            labels: Actual direction labels
            method: Override optimization method

        Returns:
            Optimized weights dict
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained. Call train() first.")

        try:
            # Generate predictions for weight optimization
            predictions_dict = self._generate_predictions_for_optimization(
                ohlc_df, features_df, labels
            )

            if not predictions_dict:
                logger.warning("No valid predictions for weight optimization")
                return self.ensemble.weights

            # Convert labels to numeric
            actuals = np.array(
                [
                    1 if str(l).lower() == "bullish" else -1 if str(l).lower() == "bearish" else 0
                    for l in labels
                ]
            )

            # Truncate to match predictions length
            min_len = min(len(actuals), min(len(p) for p in predictions_dict.values()))
            actuals = actuals[-min_len:]
            predictions_dict = {k: v[-min_len:] for k, v in predictions_dict.items()}

            # Optimize
            new_weights = self.weight_optimizer.optimize_weights(
                predictions_dict,
                actuals,
                optimize_for=method or self.optimization_method,
            )

            # Update ensemble weights
            self.ensemble.weights = new_weights
            self.ensemble._normalize_weights()

            logger.info("Weights optimized: %s", new_weights)

            return new_weights

        except Exception as e:
            self._log_error("optimize_weights", None, str(e))
            return self.ensemble.weights

    def _generate_predictions_for_optimization(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        labels: pd.Series,
    ) -> Dict[str, np.ndarray]:
        """Generate predictions array for each model."""
        predictions_dict = {}

        # Get predictions from component models via ensemble
        for i in range(min(50, len(ohlc_df) - 1)):
            try:
                idx = len(ohlc_df) - 50 + i
                if idx < 1:
                    continue

                prediction = self.ensemble.predict(
                    features_df.iloc[:idx].tail(1),
                    ohlc_df.iloc[:idx],
                )

                for model, pred in prediction.get("component_predictions", {}).items():
                    if model not in predictions_dict:
                        predictions_dict[model] = []

                    # Convert to numeric
                    label = pred.get("label", "neutral") if isinstance(pred, dict) else str(pred)
                    val = (
                        1 if label.lower() == "bullish" else -1 if label.lower() == "bearish" else 0
                    )
                    predictions_dict[model].append(val)

            except Exception as e:
                logger.debug("Prediction %d failed: %s", i, e)
                continue

        # Convert to numpy arrays
        return {k: np.array(v) for k, v in predictions_dict.items() if len(v) > 10}

    def run_backtest(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        labels: pd.Series,
        initial_train_size: int = 100,
        refit_frequency: int = 20,
    ) -> pd.DataFrame:
        """
        Run walk-forward backtest.

        Args:
            ohlc_df: OHLC price data
            features_df: Technical indicator features
            labels: Direction labels
            initial_train_size: Initial training window
            refit_frequency: How often to retrain

        Returns:
            DataFrame with backtest results
        """
        backtester = WalkForwardEnsemble(
            initial_train_size=initial_train_size,
            refit_frequency=refit_frequency,
            weight_update_frequency=refit_frequency,
        )

        # Create fresh ensemble for backtest
        backtest_ensemble = MultiModelEnsemble(
            horizon=self.horizon,
            enable_rf=self.ensemble.enable_rf,
            enable_gb=self.ensemble.enable_gb,
            enable_arima_garch=self.ensemble.enable_arima_garch,
            enable_prophet=self.ensemble.enable_prophet,
            enable_lstm=self.ensemble.enable_lstm,
        )

        results = backtester.run_backtest(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            ensemble=backtest_ensemble,
        )

        return results

    def calibrate_uncertainty(
        self,
        actual_values: np.ndarray,
        model_name: str = "ensemble",
    ) -> Dict:
        """
        Calibrate uncertainty from historical predictions.

        Args:
            actual_values: Actual observed values
            model_name: Name for calibration record

        Returns:
            Calibration metrics
        """
        if len(self.forecast_history) < 10:
            return {"error": "Insufficient forecast history for calibration"}

        # Extract historical predictions
        ci_lower = []
        ci_upper = []

        for f in self.forecast_history:
            if f.ci_lower is not None and f.ci_upper is not None:
                ci_lower.append(f.ci_lower)
                ci_upper.append(f.ci_upper)

        if len(ci_lower) < 10:
            return {"error": "Insufficient predictions with CIs"}

        # Truncate to match
        n = min(len(ci_lower), len(actual_values))
        ci_lower = np.array(ci_lower[-n:])
        ci_upper = np.array(ci_upper[-n:])
        actuals = actual_values[-n:]

        return self.uncertainty_quantifier.calibrate_uncertainty(
            ci_lower, ci_upper, actuals, model_name
        )

    def get_status(self) -> Dict:
        """Get current ensemble status."""
        return {
            "timestamp": datetime.now().isoformat(),
            "is_trained": self.is_trained,
            "training_timestamp": self.training_timestamp,
            "horizon": self.horizon,
            "n_models_total": len(self.ensemble.model_trained),
            "n_models_trained": sum(self.ensemble.model_trained.values()),
            "models_trained": {
                name: trained for name, trained in self.ensemble.model_trained.items()
            },
            "current_weights": self.ensemble.weights,
            "n_forecasts_generated": len(self.forecast_history),
            "n_errors": len(self.error_log),
            "calibration_status": self.uncertainty_quantifier.get_calibration_status(),
        }

    def get_diagnostics(self) -> Dict:
        """Get detailed diagnostics for all models."""
        return self.ensemble.get_model_diagnostics()

    def get_forecast_history(self) -> pd.DataFrame:
        """Get forecast history as DataFrame."""
        if not self.forecast_history:
            return pd.DataFrame()

        records = []
        for f in self.forecast_history:
            record = {
                "timestamp": f.timestamp,
                "label": f.label,
                "confidence": f.confidence,
                "agreement": f.agreement,
                "n_models": f.n_models,
                "forecast_return": f.forecast_return,
                "forecast_volatility": f.forecast_volatility,
                "calibrated": f.calibrated,
            }
            for cls, prob in f.probabilities.items():
                record[f"prob_{cls}"] = prob
            records.append(record)

        return pd.DataFrame(records)

    def get_error_log(self) -> pd.DataFrame:
        """Get error log as DataFrame."""
        if not self.error_log:
            return pd.DataFrame()

        return pd.DataFrame(
            [
                {
                    "timestamp": e.timestamp,
                    "operation": e.operation,
                    "model": e.model,
                    "error": e.error,
                }
                for e in self.error_log
            ]
        )

    def export_config(self, filepath: str) -> None:
        """
        Export ensemble configuration to JSON.

        Args:
            filepath: Output file path
        """
        config = {
            "horizon": self.horizon,
            "confidence_level": self.confidence_level,
            "optimization_method": self.optimization_method,
            "models": {name: trained for name, trained in self.ensemble.model_trained.items()},
            "weights": self.ensemble.weights,
            "training_timestamp": self.training_timestamp,
            "calibration_ratios": self.uncertainty_quantifier.calibration_ratios,
            "exported_at": datetime.now().isoformat(),
        }

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(config, f, indent=2, default=str)

        logger.info("Configuration exported to %s", filepath)

    def _estimate_forecast_return(self, prediction: Dict) -> Optional[float]:
        """Estimate forecast return from prediction."""
        # Check component predictions for forecast returns
        for model, pred in prediction.get("component_predictions", {}).items():
            if isinstance(pred, dict):
                ret = pred.get("forecast_return")
                if ret is not None and ret != 0:
                    return ret

        # Estimate from label and confidence
        label = prediction.get("label", "Neutral")
        confidence = prediction.get("confidence", 0.5)

        if label == "Bullish":
            return confidence * 0.02
        elif label == "Bearish":
            return -confidence * 0.02
        else:
            return 0.0

    def _calculate_entropy(self, probabilities: Dict[str, float]) -> float:
        """Calculate Shannon entropy of probability distribution."""
        probs = np.array(list(probabilities.values()))
        probs = probs[probs > 0]
        if len(probs) == 0:
            return 0.0
        return float(-np.sum(probs * np.log(probs)))

    def _log_error(
        self,
        operation: str,
        model: Optional[str],
        error: str,
        details: Optional[Dict] = None,
    ) -> None:
        """Log an error."""
        record = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            model=model,
            error=error,
            details=details,
        )
        self.error_log.append(record)
        logger.error("Error in %s: %s", operation, error)


if __name__ == "__main__":
    # Quick test
    print("Testing EnsembleManager...")

    np.random.seed(42)
    n = 200

    # Create sample data
    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    ohlc_df = pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        }
    )

    # Create features
    ohlc_df["return_1d"] = ohlc_df["close"].pct_change()
    ohlc_df["return_5d"] = ohlc_df["close"].pct_change(5)
    ohlc_df["sma_20"] = ohlc_df["close"].rolling(20).mean()
    ohlc_df["vol_20"] = ohlc_df["return_1d"].rolling(20).std()
    ohlc_df = ohlc_df.dropna()

    features_df = ohlc_df[["return_1d", "return_5d", "sma_20", "vol_20"]]

    # Create labels
    fwd = ohlc_df["close"].pct_change().shift(-1)
    labels = fwd.apply(
        lambda x: "bullish" if x > 0.01 else "bearish" if x < -0.01 else "neutral"
    ).iloc[:-1]
    features_df = features_df.iloc[:-1]
    ohlc_df = ohlc_df.iloc[:-1]

    # Initialize manager
    manager = EnsembleManager(
        horizon="1D",
        enable_rf=True,
        enable_gb=True,
        enable_arima_garch=True,
        enable_prophet=True,
        enable_lstm=False,
    )

    # Train
    print("\nTraining...")
    status = manager.train(ohlc_df, features_df, labels)
    print(f"Training status: {status}")

    # Predict
    print("\nPredicting...")
    result = manager.predict(ohlc_df, features_df)
    print(f"Prediction: {result.label} ({result.confidence:.3f})")
    print(f"Agreement: {result.agreement:.2f}")

    # Generate forecast
    print("\nGenerating forecast...")
    forecast = manager.generate_forecast(ohlc_df, features_df, horizon="1W")
    print(f"Forecast: {forecast['label']}")
    print(f"Points: {len(forecast['points'])}")

    # Get status
    print("\nStatus:")
    print(json.dumps(manager.get_status(), indent=2, default=str))

    print("\n\nSUCCESS: EnsembleManager working!")
