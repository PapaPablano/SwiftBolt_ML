"""
Uncertainty Quantifier: Ensemble Confidence Interval Aggregation
================================================================

Aggregates and calibrates uncertainty estimates from multiple models.
Provides calibrated confidence intervals for ensemble predictions.

Key Features:
- Weighted forecast aggregation
- Volatility aggregation using mean-variance framework
- Confidence interval calibration from historical coverage
- Model disagreement metrics
- Prediction interval adjustment
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class ModelForecast:
    """Container for individual model forecast."""

    model_name: str
    forecast_value: float
    forecast_volatility: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    label: Optional[str] = None
    probabilities: Optional[Dict[str, float]] = None


class UncertaintyQuantifier:
    """
    Aggregate and calibrate uncertainty from ensemble predictions.

    Combines forecasts from multiple models with proper uncertainty
    propagation and optional calibration based on historical coverage.
    """

    def __init__(
        self,
        confidence_level: float = 0.95,
        min_samples_for_calibration: int = 30,
    ) -> None:
        """
        Initialize Uncertainty Quantifier.

        Args:
            confidence_level: Target confidence level for intervals
            min_samples_for_calibration: Min samples needed for calibration
        """
        self.confidence_level = confidence_level
        self.z_score = stats.norm.ppf((1 + confidence_level) / 2)
        self.min_samples_for_calibration = min_samples_for_calibration

        # Calibration state
        self.calibration_ratios: Dict[str, float] = {}
        self.calibration_history: List[Dict] = []

        # Historical tracking for calibration
        self.prediction_history: List[Dict] = []

        logger.info(
            "UncertaintyQuantifier initialized: confidence=%.2f, z=%.3f",
            confidence_level,
            self.z_score,
        )

    def aggregate_forecasts(
        self,
        forecasts: List[ModelForecast],
        weights: Dict[str, float],
    ) -> Dict:
        """
        Aggregate multiple model forecasts into ensemble forecast.

        Args:
            forecasts: List of ModelForecast objects
            weights: Dict of {model_name: weight}

        Returns:
            Aggregated forecast with uncertainty metrics
        """
        if not forecasts:
            return self._null_ensemble_forecast("No forecasts provided")

        # Extract forecast components
        forecast_values = np.array([f.forecast_value for f in forecasts])
        volatilities = np.array([f.forecast_volatility for f in forecasts])
        ci_lowers = np.array([f.confidence_interval_lower for f in forecasts])
        ci_uppers = np.array([f.confidence_interval_upper for f in forecasts])
        model_names = [f.model_name for f in forecasts]

        # Get weights for each model
        weight_array = np.array([weights.get(name, 1.0 / len(forecasts)) for name in model_names])

        # Filter out NaN forecasts
        valid_idx = ~np.isnan(forecast_values)
        if not np.any(valid_idx):
            return self._null_ensemble_forecast("All models returned NaN")

        forecast_values = forecast_values[valid_idx]
        volatilities = volatilities[valid_idx]
        ci_lowers = ci_lowers[valid_idx]
        ci_uppers = ci_uppers[valid_idx]
        weight_array = weight_array[valid_idx]
        valid_names = [n for n, v in zip(model_names, valid_idx) if v]

        # Renormalize weights
        weight_array = weight_array / weight_array.sum()

        # Weighted average forecast
        ensemble_forecast = np.average(forecast_values, weights=weight_array)

        # Aggregate volatility
        ensemble_volatility = self._aggregate_volatility(
            volatilities, weight_array, forecast_values
        )

        # Confidence intervals from aggregated volatility
        ensemble_ci_lower = ensemble_forecast - self.z_score * ensemble_volatility
        ensemble_ci_upper = ensemble_forecast + self.z_score * ensemble_volatility

        # Alternative: weighted average of individual CIs
        avg_ci_lower = np.average(ci_lowers, weights=weight_array)
        avg_ci_upper = np.average(ci_uppers, weights=weight_array)

        # Use wider of the two interval estimates
        final_ci_lower = min(ensemble_ci_lower, avg_ci_lower)
        final_ci_upper = max(ensemble_ci_upper, avg_ci_upper)

        # Model disagreement metrics
        forecast_dispersion = np.std(forecast_values)
        model_agreement = self._calculate_model_agreement(forecast_values, ensemble_volatility)

        return {
            "forecast": float(ensemble_forecast),
            "volatility": float(ensemble_volatility),
            "ci_lower": float(final_ci_lower),
            "ci_upper": float(final_ci_upper),
            "ensemble_dispersion": float(forecast_dispersion),
            "model_agreement": float(model_agreement),
            "n_valid_models": int(np.sum(valid_idx)),
            "models_used": valid_names,
            "weights_used": {n: float(w) for n, w in zip(valid_names, weight_array)},
            "confidence_level": self.confidence_level,
        }

    def aggregate_from_predictions(
        self,
        predictions: Dict[str, Dict],
        weights: Dict[str, float],
    ) -> Dict:
        """
        Aggregate from prediction dicts (compatible with MultiModelEnsemble).

        Args:
            predictions: Dict of {model_name: prediction_dict}
            weights: Dict of {model_name: weight}

        Returns:
            Aggregated forecast with uncertainty
        """
        forecasts = []

        for model_name, pred in predictions.items():
            # Extract forecast value (could be return or price)
            forecast_val = pred.get("forecast_return", 0)
            if forecast_val == 0:
                # Try confidence as proxy
                confidence = pred.get("confidence", 0.5)
                label = pred.get("label", "Neutral")
                # Convert to directional forecast
                if isinstance(label, str):
                    direction = (
                        1 if label.lower() == "bullish" else -1 if label.lower() == "bearish" else 0
                    )
                else:
                    direction = 0
                forecast_val = direction * confidence * 0.02  # Scale by 2%

            # Extract volatility
            volatility = pred.get("forecast_volatility", 0.02)
            if volatility == 0 or volatility is None:
                volatility = 0.02  # Default 2%

            # Extract or compute CIs
            ci_lower = pred.get(
                "ci_lower",
                forecast_val - self.z_score * volatility,
            )
            ci_upper = pred.get(
                "ci_upper",
                forecast_val + self.z_score * volatility,
            )

            forecasts.append(
                ModelForecast(
                    model_name=model_name,
                    forecast_value=forecast_val,
                    forecast_volatility=volatility,
                    confidence_interval_lower=ci_lower,
                    confidence_interval_upper=ci_upper,
                    label=pred.get("label"),
                    probabilities=pred.get("probabilities"),
                )
            )

        return self.aggregate_forecasts(forecasts, weights)

    def _aggregate_volatility(
        self,
        volatilities: np.ndarray,
        weights: np.ndarray,
        forecast_values: np.ndarray,
    ) -> float:
        """
        Aggregate volatility from ensemble using mean-variance framework.

        Formula: sigma_ensemble = sqrt(sum(w_i * sigma_i^2) + var(forecasts))

        This accounts for both individual model uncertainty AND
        disagreement between models.
        """
        # Weighted variance of individual volatilities
        weighted_var = np.average(volatilities**2, weights=weights)

        # Variance of forecasts (model disagreement)
        forecast_var = np.var(forecast_values) if len(forecast_values) > 1 else 0

        # Combined uncertainty
        total_var = weighted_var + forecast_var

        return float(np.sqrt(total_var))

    def _calculate_model_agreement(
        self,
        forecast_values: np.ndarray,
        ensemble_volatility: float,
    ) -> float:
        """
        Calculate model agreement score (0-1).

        High agreement means models produce similar forecasts.
        """
        if len(forecast_values) < 2:
            return 1.0

        forecast_dispersion = np.std(forecast_values)

        if ensemble_volatility > 0:
            # Ratio of dispersion to overall uncertainty
            disagreement_ratio = forecast_dispersion / ensemble_volatility
            agreement = max(0, 1.0 - disagreement_ratio)
        else:
            agreement = 1.0 if forecast_dispersion == 0 else 0.0

        return float(np.clip(agreement, 0, 1))

    def calibrate_uncertainty(
        self,
        predicted_ci_lower: np.ndarray,
        predicted_ci_upper: np.ndarray,
        actuals: np.ndarray,
        model_name: str = "ensemble",
    ) -> Dict:
        """
        Calibrate prediction intervals based on empirical coverage.

        Args:
            predicted_ci_lower: Predicted lower bounds
            predicted_ci_upper: Predicted upper bounds
            actuals: Actual observed values
            model_name: Name for this calibration

        Returns:
            Calibration metrics
        """
        if len(actuals) < self.min_samples_for_calibration:
            return {
                "error": f"Insufficient samples: {len(actuals)} < "
                f"{self.min_samples_for_calibration}",
                "calibration_ratio": 1.0,
            }

        # Calculate empirical coverage
        in_bounds = (actuals >= predicted_ci_lower) & (actuals <= predicted_ci_upper)
        coverage = np.mean(in_bounds)

        # Interval width statistics
        interval_widths = predicted_ci_upper - predicted_ci_lower
        mean_width = np.mean(interval_widths)
        std_width = np.std(interval_widths)

        # Calibration ratio
        # If coverage < target: ratio < 1, need to widen intervals
        # If coverage > target: ratio > 1, can narrow intervals
        calibration_ratio = coverage / self.confidence_level

        # Store calibration
        self.calibration_ratios[model_name] = calibration_ratio
        self.calibration_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "model_name": model_name,
                "empirical_coverage": coverage,
                "target_coverage": self.confidence_level,
                "calibration_ratio": calibration_ratio,
                "n_samples": len(actuals),
            }
        )

        logger.info(
            "Calibration for %s: coverage=%.3f (target=%.3f), ratio=%.3f",
            model_name,
            coverage,
            self.confidence_level,
            calibration_ratio,
        )

        return {
            "empirical_coverage": float(coverage),
            "target_coverage": self.confidence_level,
            "calibration_ratio": float(calibration_ratio),
            "mean_interval_width": float(mean_width),
            "std_interval_width": float(std_width),
            "n_samples": len(actuals),
            "needs_widening": coverage < self.confidence_level,
            "needs_narrowing": coverage > self.confidence_level,
            "n_in_bounds": int(np.sum(in_bounds)),
        }

    def apply_calibration(
        self,
        ensemble_forecast: Dict,
        model_name: str = "ensemble",
    ) -> Dict:
        """
        Apply calibration adjustment to ensemble forecast.

        Args:
            ensemble_forecast: Forecast dict from aggregate_forecasts
            model_name: Which calibration to apply

        Returns:
            Calibrated forecast dict
        """
        # Get calibration ratio
        ratio = self.calibration_ratios.get(model_name)

        if ratio is None:
            # Try average of all calibrations
            if self.calibration_ratios:
                ratio = np.mean(list(self.calibration_ratios.values()))
            else:
                # No calibration available
                return {
                    **ensemble_forecast,
                    "calibration_applied": False,
                }

        # Adjust volatility based on calibration
        # If ratio < 1 (under-coverage), increase volatility
        # If ratio > 1 (over-coverage), decrease volatility
        adjustment_factor = np.sqrt(1.0 / ratio) if ratio > 0 else 1.0

        original_vol = ensemble_forecast.get("volatility", 0)
        calibrated_vol = original_vol * adjustment_factor

        forecast_val = ensemble_forecast.get("forecast", 0)

        # Recalculate confidence intervals
        calibrated_ci_lower = forecast_val - self.z_score * calibrated_vol
        calibrated_ci_upper = forecast_val + self.z_score * calibrated_vol

        return {
            **ensemble_forecast,
            "volatility": float(calibrated_vol),
            "ci_lower": float(calibrated_ci_lower),
            "ci_upper": float(calibrated_ci_upper),
            "calibration_applied": True,
            "calibration_ratio": float(ratio),
            "adjustment_factor": float(adjustment_factor),
            "original_volatility": float(original_vol),
        }

    def record_prediction(
        self,
        prediction: Dict,
        actual: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """
        Record a prediction for future calibration.

        Args:
            prediction: Prediction dict with ci_lower, ci_upper
            actual: Actual observed value (if known)
            timestamp: When prediction was made
        """
        record = {
            "timestamp": timestamp or datetime.now().isoformat(),
            "ci_lower": prediction.get("ci_lower"),
            "ci_upper": prediction.get("ci_upper"),
            "forecast": prediction.get("forecast"),
            "volatility": prediction.get("volatility"),
            "actual": actual,
        }
        self.prediction_history.append(record)

    def update_calibration_from_history(
        self,
        model_name: str = "ensemble",
    ) -> Optional[Dict]:
        """
        Update calibration using recorded prediction history.

        Returns:
            Calibration metrics or None if insufficient data
        """
        # Filter predictions with actuals
        completed = [p for p in self.prediction_history if p.get("actual") is not None]

        if len(completed) < self.min_samples_for_calibration:
            return None

        ci_lower = np.array([p["ci_lower"] for p in completed])
        ci_upper = np.array([p["ci_upper"] for p in completed])
        actuals = np.array([p["actual"] for p in completed])

        return self.calibrate_uncertainty(ci_lower, ci_upper, actuals, model_name)

    def _null_ensemble_forecast(self, error_msg: str) -> Dict:
        """Return null forecast when aggregation fails."""
        return {
            "forecast": np.nan,
            "volatility": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "error": error_msg,
            "n_valid_models": 0,
        }

    def get_calibration_status(self) -> Dict:
        """Get current calibration status."""
        return {
            "confidence_level": self.confidence_level,
            "z_score": self.z_score,
            "calibration_ratios": self.calibration_ratios.copy(),
            "n_calibrations": len(self.calibration_history),
            "n_recorded_predictions": len(self.prediction_history),
            "models_calibrated": list(self.calibration_ratios.keys()),
        }

    def get_calibration_history(self) -> pd.DataFrame:
        """Get calibration history as DataFrame."""
        if not self.calibration_history:
            return pd.DataFrame()
        return pd.DataFrame(self.calibration_history)


class DirectionalUncertaintyQuantifier(UncertaintyQuantifier):
    """
    Uncertainty quantifier for directional (classification) forecasts.

    Aggregates class probabilities and provides calibrated confidence.
    """

    def aggregate_probabilities(
        self,
        predictions: Dict[str, Dict],
        weights: Dict[str, float],
    ) -> Dict:
        """
        Aggregate class probabilities from multiple models.

        Args:
            predictions: {model_name: {label, confidence, probabilities}}
            weights: {model_name: weight}

        Returns:
            Aggregated probabilities and confidence
        """
        # Initialize probability accumulators
        prob_sums = {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}
        total_weight = 0.0

        for model_name, pred in predictions.items():
            weight = weights.get(model_name, 0)
            if weight <= 0:
                continue

            probs = pred.get("probabilities", {})
            for cls in prob_sums:
                prob_sums[cls] += probs.get(cls, 0.33) * weight

            total_weight += weight

        # Normalize
        if total_weight > 0:
            probs = {k: v / total_weight for k, v in prob_sums.items()}
        else:
            probs = {k: 1 / 3 for k in prob_sums}

        # Ensure sum = 1
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        # Determine final label and confidence
        final_label = max(probs, key=probs.get)
        confidence = probs[final_label]

        # Entropy-based uncertainty
        entropy = self._calculate_entropy(list(probs.values()))
        max_entropy = np.log(3)  # Maximum entropy for 3 classes
        normalized_entropy = entropy / max_entropy

        return {
            "label": final_label.capitalize(),
            "confidence": float(confidence),
            "probabilities": probs,
            "entropy": float(entropy),
            "normalized_entropy": float(normalized_entropy),
            "uncertainty": float(normalized_entropy),  # Higher = more uncertain
        }

    def _calculate_entropy(self, probabilities: List[float]) -> float:
        """Calculate Shannon entropy of probability distribution."""
        probs = np.array(probabilities)
        probs = probs[probs > 0]  # Avoid log(0)
        return float(-np.sum(probs * np.log(probs)))


if __name__ == "__main__":
    # Quick test
    print("Testing UncertaintyQuantifier...")

    np.random.seed(42)

    # Create sample forecasts
    forecasts = [
        ModelForecast(
            model_name="rf",
            forecast_value=0.015,
            forecast_volatility=0.02,
            confidence_interval_lower=-0.025,
            confidence_interval_upper=0.055,
        ),
        ModelForecast(
            model_name="gb",
            forecast_value=0.012,
            forecast_volatility=0.018,
            confidence_interval_lower=-0.022,
            confidence_interval_upper=0.046,
        ),
        ModelForecast(
            model_name="arima",
            forecast_value=0.008,
            forecast_volatility=0.025,
            confidence_interval_lower=-0.040,
            confidence_interval_upper=0.056,
        ),
        ModelForecast(
            model_name="lstm",
            forecast_value=0.018,
            forecast_volatility=0.022,
            confidence_interval_lower=-0.028,
            confidence_interval_upper=0.064,
        ),
    ]

    weights = {"rf": 0.25, "gb": 0.25, "arima": 0.25, "lstm": 0.25}

    # Test aggregation
    uq = UncertaintyQuantifier(confidence_level=0.95)
    result = uq.aggregate_forecasts(forecasts, weights)

    print(f"\nAggregated forecast: {result['forecast']:.4f}")
    print(f"Volatility: {result['volatility']:.4f}")
    print(f"95% CI: [{result['ci_lower']:.4f}, {result['ci_upper']:.4f}]")
    print(f"Model agreement: {result['model_agreement']:.3f}")
    print(f"Models used: {result['n_valid_models']}")

    # Test calibration
    print("\n\nTesting calibration...")
    n = 100
    predicted_lower = np.random.randn(n) * 0.02 - 0.04
    predicted_upper = predicted_lower + 0.08
    actuals = np.random.randn(n) * 0.03  # Actual values

    cal_result = uq.calibrate_uncertainty(predicted_lower, predicted_upper, actuals, "test_model")
    print(f"\nCalibration results:")
    print(f"  Empirical coverage: {cal_result['empirical_coverage']:.3f}")
    print(f"  Target coverage: {cal_result['target_coverage']:.3f}")
    print(f"  Calibration ratio: {cal_result['calibration_ratio']:.3f}")
    print(f"  Needs widening: {cal_result['needs_widening']}")

    # Apply calibration
    calibrated = uq.apply_calibration(result, "test_model")
    print(f"\nCalibrated forecast:")
    print(f"  Original vol: {calibrated['original_volatility']:.4f}")
    print(f"  Calibrated vol: {calibrated['volatility']:.4f}")
    print(f"  Adjustment factor: {calibrated['adjustment_factor']:.3f}")

    # Test directional quantifier
    print("\n\nTesting DirectionalUncertaintyQuantifier...")
    duq = DirectionalUncertaintyQuantifier()

    predictions = {
        "rf": {
            "label": "Bullish",
            "confidence": 0.7,
            "probabilities": {"bullish": 0.7, "neutral": 0.2, "bearish": 0.1},
        },
        "gb": {
            "label": "Bullish",
            "confidence": 0.6,
            "probabilities": {"bullish": 0.6, "neutral": 0.25, "bearish": 0.15},
        },
        "arima": {
            "label": "Neutral",
            "confidence": 0.5,
            "probabilities": {"bullish": 0.35, "neutral": 0.5, "bearish": 0.15},
        },
    }

    dir_result = duq.aggregate_probabilities(predictions, weights)
    print(f"\nDirectional aggregation:")
    print(f"  Label: {dir_result['label']}")
    print(f"  Confidence: {dir_result['confidence']:.3f}")
    print(f"  Entropy: {dir_result['entropy']:.3f}")
    print(f"  Uncertainty: {dir_result['uncertainty']:.3f}")

    print("\n\nSUCCESS: UncertaintyQuantifier working!")
