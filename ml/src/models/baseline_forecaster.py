"""Baseline ML forecaster using Random Forest for price movement prediction."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import RobustScaler

from config.settings import settings
from src.data.data_validator import OHLCValidator, ValidationResult
from src.features.adaptive_thresholds import AdaptiveThresholds
from src.features.temporal_indicators import TemporalFeatureEngineer
from src.monitoring.confidence_calibrator import ConfidenceCalibrator

logger = logging.getLogger(__name__)


class BaselineForecaster:
    """
    Baseline forecaster using Random Forest to predict price direction.

    Predicts: Bullish (up >2%), Neutral (-2% to 2%), Bearish (down >2%)
    """

    def __init__(self) -> None:
        """Initialize the forecaster."""
        # RobustScaler uses median/IQR instead of mean/std
        # Better for OHLC data with gaps and outliers
        self.scaler = RobustScaler()
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
        )
        self.feature_columns: list[str] = []
        self.is_trained = False

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data with adaptive thresholds and temporal features.
        """
        df = df.copy()

        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds(df)
        logger.info(
            "Adaptive thresholds: bearish=%.4f, bullish=%.4f",
            bearish_thresh,
            bullish_thresh,
        )

        forward_returns = df["close"].pct_change(periods=horizon_days).shift(-horizon_days)

        engineer = TemporalFeatureEngineer()
        X_list: list[dict[str, Any]] = []
        y_list: list[str] = []

        for idx in range(50, len(df) - horizon_days):
            features = engineer.add_features_to_point(df, idx)
            actual_return = forward_returns.iloc[idx]

            if pd.notna(actual_return):
                X_list.append(features)
                if actual_return > bullish_thresh:
                    label = "bullish"
                elif actual_return < bearish_thresh:
                    label = "bearish"
                else:
                    label = "neutral"
                y_list.append(label)

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)

        logger.info("Training data prepared: %s samples", len(X))
        logger.info("Label distribution: %s", y.value_counts().to_dict())

        return X, y

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Train the forecaster model with enhanced metrics logging.
        """
        if len(X) < settings.min_bars_for_training:
            raise ValueError(
                f"Insufficient training data: {len(X)} " f"< {settings.min_bars_for_training}"
            )

        # Exclude non-numeric columns (e.g., timestamps)
        numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        X = X[numeric_cols]
        self.feature_columns = numeric_cols
        X_scaled = self.scaler.fit_transform(X)

        logger.info("Training Random Forest model...")
        self.model.fit(X_scaled, y)

        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
        )

        predictions = self.model.predict(X_scaled)
        accuracy = accuracy_score(y, predictions)
        precision = precision_score(
            y,
            predictions,
            average="weighted",
            zero_division=0,
        )
        recall = recall_score(
            y,
            predictions,
            average="weighted",
            zero_division=0,
        )
        f1 = f1_score(y, predictions, average="weighted", zero_division=0)
        cm = confusion_matrix(y, predictions)
        # Feature importances (RF supports this attribute)
        importances = getattr(self.model, "feature_importances_", None)
        if importances is not None and len(importances) == len(self.feature_columns):
            importance_pairs = sorted(
                zip(self.feature_columns, importances),
                key=lambda kv: kv[1],
                reverse=True,
            )
            top_features = importance_pairs[:10]
        else:
            top_features = []

        self.training_stats = {
            "timestamp": datetime.now().isoformat(),
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "confusion_matrix": cm.tolist(),
            "n_samples": len(X),
            "n_features": len(self.feature_columns),
            "class_distribution": y.value_counts().to_dict(),
            "top_features": top_features,
        }

        logger.info(
            "Training metrics - acc=%.3f, prec=%.3f, rec=%.3f, f1=%.3f",
            accuracy,
            precision,
            recall,
            f1,
        )
        logger.info("Confusion matrix:\n%s", cm)
        if top_features:
            logger.info(
                "Top features: %s",
                ", ".join(f"{name}={score:.3f}" for name, score in top_features),
            )

        self.is_trained = True

    def predict(self, X: pd.DataFrame) -> tuple[str, float, np.ndarray]:
        """
        Make a prediction on new data.

        Args:
            X: Feature DataFrame (single row or multiple rows)

        Returns:
            Tuple of (label, confidence, probabilities)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")

        # Ensure features match training
        X = X[self.feature_columns]

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Predict
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        # Get most recent prediction (last row)
        label = predictions[-1]
        proba = probabilities[-1]
        confidence = float(proba.max())

        logger.info(f"Prediction: {label} (confidence: {confidence:.3f})")
        logger.info(f"Probabilities: {dict(zip(self.model.classes_, proba))}")

        return label, confidence, probabilities

    def generate_forecast(
        self,
        df: pd.DataFrame,
        horizon: str,
        calibrator: Optional[ConfidenceCalibrator] = None,
        validate_data: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a complete forecast with label, confidence, and future points.

        Args:
            df: DataFrame with OHLC + technical indicators
            horizon: Forecast horizon ("1D", "1W", etc.)
            calibrator: Optional confidence calibrator for adjusting scores
            validate_data: Whether to validate OHLC data before processing

        Returns:
            Forecast dictionary with label, confidence, and points
        """
        # Validate data if requested
        data_quality_multiplier = 1.0
        validation_result: Optional[ValidationResult] = None

        if validate_data:
            validator = OHLCValidator()
            df, validation_result = validator.validate(df, fix_issues=True)

            if validation_result and not validation_result.is_valid:
                logger.warning(f"Data quality issues detected: {validation_result.issues}")
                # Apply slight confidence penalty for data with issues
                data_quality_multiplier = max(
                    0.9, 1.0 - (validation_result.rows_flagged / len(df) * 0.2)
                )

        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Prepare training data
        X, y = self.prepare_training_data(df, horizon_days=horizon_days)

        # Calculate data quality multiplier based on sample size
        # Less data = lower confidence (per improvement plan 1.1)
        sample_size_multiplier = min(1.0, len(X) / settings.min_bars_for_high_confidence)

        # Train model
        self.train(X, y)

        # Get last row features for prediction
        last_features = X.tail(1)
        last_close = df["close"].iloc[-1]
        last_ts = pd.to_datetime(df["ts"].iloc[-1]).to_pydatetime()

        # Predict
        label, raw_confidence, probabilities = self.predict(last_features)

        # Apply confidence adjustments
        adjusted_confidence = raw_confidence

        # 1. Apply calibration if calibrator is provided
        if calibrator and calibrator.is_fitted:
            adjusted_confidence = calibrator.calibrate(adjusted_confidence)
            logger.info(f"Calibration: {raw_confidence:.3f} -> {adjusted_confidence:.3f}")

        # 2. Apply data quality multiplier
        adjusted_confidence *= data_quality_multiplier

        # 3. Apply sample size multiplier
        adjusted_confidence *= sample_size_multiplier

        # Ensure confidence stays in valid range
        adjusted_confidence = float(np.clip(adjusted_confidence, 0.40, 0.95))

        if adjusted_confidence != raw_confidence:
            logger.info(
                f"Final confidence: {raw_confidence:.3f} -> {adjusted_confidence:.3f} "
                f"(data_qual={data_quality_multiplier:.2f}, "
                f"sample_size={sample_size_multiplier:.2f})"
            )

        # Convert probabilities array to dict for _generate_forecast_points
        proba_dict = dict(zip(self.model.classes_, probabilities[-1]))

        # Generate forecast points with probability-based directional estimates
        points = self._generate_forecast_points(
            last_ts, last_close, label, adjusted_confidence, horizon_days, proba_dict
        )

        return {
            "label": label,
            "confidence": adjusted_confidence,
            "raw_confidence": raw_confidence,
            "horizon": horizon,
            "points": points,
            "probabilities": probabilities,
            "data_quality": {
                "validation_issues": (validation_result.issues if validation_result else []),
                "quality_multiplier": data_quality_multiplier,
                "sample_size_multiplier": sample_size_multiplier,
                "n_training_samples": len(X),
            },
        }

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of days."""
        if horizon == "1D":
            return 1
        elif horizon == "1W":
            return 5  # 5 trading days
        elif horizon == "1M":
            return 20  # ~20 trading days
        else:
            raise ValueError(f"Unknown horizon: {horizon}")

    def _generate_forecast_points(
        self,
        last_ts: datetime,
        last_close: float,
        label: str,
        confidence: float,
        horizon_days: int,
        probabilities: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate forecast points for visualization.

        Creates directional projections based on the full probability distribution,
        ensuring forecasts always show meaningful price movement.
        """
        points = []

        # Calculate directional expected return from probability distribution
        if probabilities:
            # Use weighted probabilities for more nuanced predictions
            # Convert numpy types to float to avoid calculation issues
            bull_prob = float(probabilities.get("bullish", 0.0))
            bear_prob = float(probabilities.get("bearish", 0.0))

            # Net directional signal: positive = bullish bias, negative = bearish bias
            directional_bias = bull_prob - bear_prob

            # Base expected return scaled by directional strength
            # Maximum move is 5% for 100% directional confidence
            expected_return = directional_bias * 0.05

            logger.info(
                f"Directional: bull={bull_prob:.3f}, bear={bear_prob:.3f}, "
                f"bias={directional_bias:.3f}, return={expected_return:.4f}"
            )
        else:
            # Fallback to label-based approach
            if label == "bullish":
                expected_return = 0.03 * confidence
            elif label == "bearish":
                expected_return = -0.03 * confidence
            else:
                expected_return = 0.0

        # Ensure minimum visible movement for 1-week+ horizons
        # Even "neutral" should show slight directional tendency
        min_move = 0.005 * (horizon_days / 5)  # 0.5% per week minimum
        if abs(expected_return) < min_move and probabilities:
            # Use sign of directional bias or default to slight bullish
            sign = 1 if (probabilities.get("bullish", 0) >= probabilities.get("bearish", 0)) else -1
            expected_return = sign * min_move

        # Scale expected return by horizon (longer = more movement)
        # 1D = base, 1W = 1.5x, 1M = 2x
        horizon_multiplier = 1.0 + (horizon_days - 1) * 0.1
        expected_return *= min(horizon_multiplier, 2.0)

        logger.info(
            f"Forecast: close={last_close:.2f}, return={expected_return:.4f}, "
            f"horizon={horizon_days}d"
        )

        # Generate daily points
        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            progress = i / horizon_days

            # Linear interpolation of price movement
            forecast_value = float(last_close) * (1 + expected_return * progress)

            # Confidence bands (wider for less confident, more for longer horizons)
            base_uncertainty = (1 - confidence) * 0.03  # 3% max base uncertainty
            time_uncertainty = progress * 0.02  # +2% uncertainty over time
            total_uncertainty = base_uncertainty + time_uncertainty

            lower_bound = forecast_value * (1 - total_uncertainty)
            upper_bound = forecast_value * (1 + total_uncertainty)

            if i == 1:
                logger.info(
                    f"  Day {i}: val={forecast_value:.2f}, "
                    f"low={lower_bound:.2f}, up={upper_bound:.2f}"
                )

            points.append(
                {
                    "ts": int(forecast_ts.timestamp()),
                    "value": round(forecast_value, 2),
                    "lower": round(lower_bound, 2),
                    "upper": round(upper_bound, 2),
                }
            )

        return points
