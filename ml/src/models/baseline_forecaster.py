"""Baseline ML forecaster using Random Forest for price movement prediction."""

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from config.settings import settings

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
        self, df: pd.DataFrame, horizon_days: int = 1
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data with features and labels.

        Args:
            df: DataFrame with technical indicators
            horizon_days: Number of days ahead to predict

        Returns:
            Tuple of (features_df, labels_series)
        """
        df = df.copy()

        # Calculate forward returns (our label)
        df["forward_return"] = df["close"].pct_change(periods=horizon_days).shift(
            -horizon_days
        )

        # Create labels: Bullish (1), Neutral (0), Bearish (-1)
        df["label"] = pd.cut(
            df["forward_return"],
            bins=[-np.inf, -0.02, 0.02, np.inf],
            labels=["Bearish", "Neutral", "Bullish"],
        )

        # Drop rows with NaN labels (last horizon_days rows + initial NaNs)
        df_clean = df.dropna(subset=["label"])

        # Select feature columns (exclude metadata and target)
        exclude_cols = [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "forward_return",
            "label",
        ]
        feature_cols = [col for col in df_clean.columns if col not in exclude_cols]

        X = df_clean[feature_cols]
        y = df_clean["label"]

        logger.info(
            f"Prepared {len(X)} training samples with {len(feature_cols)} features"
        )
        logger.info(f"Label distribution: {y.value_counts().to_dict()}")

        return X, y

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Train the forecaster model.

        Args:
            X: Feature DataFrame
            y: Label series
        """
        if len(X) < settings.min_bars_for_training:
            raise ValueError(
                f"Insufficient training data: {len(X)} < {settings.min_bars_for_training}"
            )

        # Store feature columns
        self.feature_columns = X.columns.tolist()

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        logger.info("Training Random Forest model...")
        self.model.fit(X_scaled, y)

        # Calculate training accuracy
        train_score = self.model.score(X_scaled, y)
        logger.info(f"Training accuracy: {train_score:.3f}")

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
        if label == "Bullish":
            expected_return = 0.03  # 3% gain
        elif label == "Bearish":
            expected_return = -0.03  # 3% loss
        else:  # Neutral
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
