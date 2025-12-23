"""Baseline ML forecaster using Random Forest for price movement prediction."""

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from config.settings import settings
from src.features.adaptive_thresholds import AdaptiveThresholds
from src.features.temporal_indicators import TemporalFeatureEngineer

logger = logging.getLogger(__name__)


class BaselineForecaster:
    """
    Baseline forecaster using Random Forest to predict price direction.

    Predicts: Bullish (up >2%), Neutral (-2% to 2%), Bearish (down >2%)
    """

    def __init__(self) -> None:
        """Initialize the forecaster."""
        self.scaler = StandardScaler()
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

        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds(
            df
        )
        logger.info(
            "Adaptive thresholds: bearish=%.4f, bullish=%.4f",
            bearish_thresh,
            bullish_thresh,
        )

        forward_returns = df["close"].pct_change(periods=horizon_days).shift(
            -horizon_days
        )

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
                f"Insufficient training data: {len(X)} "
                f"< {settings.min_bars_for_training}"
            )

        self.feature_columns = X.columns.tolist()
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
        }

        logger.info(
            "Training metrics - acc=%.3f, prec=%.3f, rec=%.3f, f1=%.3f",
            accuracy,
            precision,
            recall,
            f1,
        )
        logger.info("Confusion matrix:\n%s", cm)

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
        self, df: pd.DataFrame, horizon: str
    ) -> dict[str, Any]:
        """
        Generate a complete forecast with label, confidence, and future points.

        Args:
            df: DataFrame with OHLC + technical indicators
            horizon: Forecast horizon ("1D", "1W", etc.)

        Returns:
            Forecast dictionary with label, confidence, and points
        """
        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Prepare training data
        X, y = self.prepare_training_data(df, horizon_days=horizon_days)

        # Train model
        self.train(X, y)

        # Get last row features for prediction
        last_features = X.tail(1)
        last_close = df["close"].iloc[-1]
        last_ts = df["ts"].iloc[-1]

        # Predict
        label, confidence, probabilities = self.predict(last_features)

        # Generate forecast points (simple projection based on prediction)
        points = self._generate_forecast_points(
            last_ts, last_close, label, confidence, horizon_days
        )

        return {
            "label": label,
            "confidence": confidence,
            "horizon": horizon,
            "points": points,
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
    ) -> list[dict[str, Any]]:
        """
        Generate forecast points for visualization.

        Creates a simple linear projection with confidence bands.
        """
        points = []

        # Determine expected return based on label
        if label == "bullish":
            expected_return = 0.03  # 3% gain
        elif label == "bearish":
            expected_return = -0.03  # 3% loss
        else:  # neutral
            expected_return = 0.0

        # Scale by confidence
        expected_return *= confidence

        # Generate daily points
        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            progress = i / horizon_days

            # Linear interpolation of price movement
            forecast_value = last_close * (1 + expected_return * progress)

            # Confidence bands (wider for less confident predictions)
            uncertainty = (1 - confidence) * 0.05  # 5% max uncertainty
            lower_bound = forecast_value * (1 - uncertainty)
            upper_bound = forecast_value * (1 + uncertainty)

            points.append(
                {
                    "ts": int(forecast_ts.timestamp()),
                    "value": round(forecast_value, 2),
                    "lower": round(lower_bound, 2),
                    "upper": round(upper_bound, 2),
                }
            )

        return points
