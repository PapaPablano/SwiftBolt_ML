"""
TabPFN-based forecasting module for SwiftBolt ML.
Standalone implementation using zero-shot transformer-based predictions.
"""
import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

# Reduce segfault risk on macOS/Apple Silicon (PyTorch/TabPFN native code).
# Set before importing torch/tabpfn.
if "OMP_NUM_THREADS" not in os.environ:
    os.environ["OMP_NUM_THREADS"] = "1"
if "MKL_NUM_THREADS" not in os.environ:
    os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from config.settings import settings
from src.features.adaptive_thresholds import AdaptiveThresholds
from src.features.temporal_indicators import TemporalFeatureEngineer

logger = logging.getLogger(__name__)

# Check TabPFN availability
try:
    from tabpfn import TabPFNRegressor
    TABPFN_AVAILABLE = True
except ImportError:
    TABPFN_AVAILABLE = False
    logger.warning("TabPFN not installed. Install with: pip install tabpfn")


class TabPFNForecaster:
    """
    TabPFN-based stock price forecaster.

    Features:
    - Zero-shot learning (no hyperparameter tuning needed)
    - Fast inference (<1 sec per symbol)
    - Built-in uncertainty quantification
    - Optimized for small datasets (<10k rows)
    - Compatible with BaselineForecaster interface

    TabPFN (Tabular Prior-Fitted Networks) uses a transformer pretrained on
    synthetic classification tasks to make predictions without traditional training.
    """

    def __init__(
        self,
        device: str = 'cpu',
        n_estimators: int = 16,  # TabPFN ensemble size (lower for faster inference)
    ):
        """
        Initialize TabPFN forecaster.

        Args:
            device: Device to run on ('cpu' or 'cuda')
            n_estimators: Number of ensemble configurations (trade-off: speed vs accuracy)
        """
        if not TABPFN_AVAILABLE:
            raise ImportError(
                "TabPFN not installed. Install with: pip install tabpfn\n"
                "Note: TabPFN requires PyTorch. Install with: pip install torch"
            )

        self.device = device
        self.n_estimators = n_estimators
        self.model: Optional[TabPFNRegressor] = None
        self.scaler = StandardScaler()
        self.feature_columns: list[str] = []
        self.is_trained = False
        self._last_df: Optional[pd.DataFrame] = None
        self._bearish_thresh: float = -0.02
        self._bullish_thresh: float = 0.02
        self.training_stats: Dict[str, Any] = {}

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data with adaptive thresholds.

        Args:
            df: OHLC DataFrame with technical indicators
            horizon_days: Forecast horizon in trading days

        Returns:
            (X, y): Features and target returns
        """
        df = df.copy()

        # Get adaptive thresholds
        self._bearish_thresh, self._bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
            df, horizon_days=horizon_days
        )
        logger.info(
            f"TabPFN adaptive thresholds ({horizon_days}D): "
            f"bearish={self._bearish_thresh:.4f}, bullish={self._bullish_thresh:.4f}"
        )

        # Calculate forward returns
        horizon_days_int = max(1, int(np.ceil(horizon_days)))
        forward_returns = df["close"].pct_change(periods=horizon_days_int).shift(-horizon_days_int)

        # Build features using TemporalFeatureEngineer
        engineer = TemporalFeatureEngineer()
        X_list: list[Dict[str, Any]] = []
        y_list: list[float] = []

        # Adaptive offset for technical indicators
        min_offset = 50 if len(df) >= 100 else (26 if len(df) >= 60 else 14)
        start_idx = max(min_offset, 14)
        end_idx = len(df) - horizon_days_int

        logger.debug(
            f"TabPFN training range: idx={start_idx}:{end_idx} "
            f"(df_len={len(df)}, horizon={horizon_days_int})"
        )

        for idx in range(start_idx, end_idx):
            features = engineer.add_features_to_point(df, idx)
            actual_return = forward_returns.iloc[idx]

            if pd.notna(actual_return):
                X_list.append(features)
                y_list.append(actual_return)

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)

        logger.info(
            f"TabPFN training data: {len(X)} samples, "
            f"{len(df)} total bars, range={start_idx}:{end_idx}"
        )

        if len(y) > 0:
            logger.info(
                f"Return distribution: mean={y.mean():.4f}, std={y.std():.4f}, "
                f"min={y.min():.4f}, max={y.max():.4f}"
            )

        return X, y

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        min_samples: Optional[int] = None
    ) -> None:
        """
        Train TabPFN model (actually just preprocessing - TabPFN is zero-shot).

        Args:
            X: Feature DataFrame
            y: Target returns (continuous values)
            min_samples: Minimum samples required (default from settings)
        """
        min_required = min_samples if min_samples is not None else settings.min_bars_for_training

        if len(X) < min_required:
            raise ValueError(
                f"Insufficient training data for TabPFN: {len(X)} < {min_required}"
            )

        # TabPFN has sample limits (typically 10k for pretraining compatibility)
        max_samples = 1000  # Conservative limit for stability
        if len(X) > max_samples:
            logger.warning(
                f"TabPFN works best with <1000 samples. Truncating {len(X)} to {max_samples}"
            )
            X = X.tail(max_samples)
            y = y.tail(max_samples)

        # Keep only numeric columns
        numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        X = X[numeric_cols]
        self.feature_columns = numeric_cols

        # TabPFN prefers standardized features
        X_scaled = self.scaler.fit_transform(X)

        # Initialize TabPFN
        logger.info("Initializing TabPFN regressor...")
        start_time = datetime.now()

        try:
            self.model = TabPFNRegressor(
                device=self.device,
                n_estimators=self.n_estimators,
            )

            # Fit TabPFN (fast - no actual training, just stores data)
            self.model.fit(X_scaled, y.values)

            train_time = (datetime.now() - start_time).total_seconds()

            # Get predictions for training data (for stats)
            y_pred = self.model.predict(X_scaled)

            # Calculate statistics
            mse = np.mean((y.values - y_pred) ** 2)
            mae = np.mean(np.abs(y.values - y_pred))
            r2 = 1 - (mse / np.var(y.values)) if np.var(y.values) > 0 else 0

            # Direction accuracy
            y_direction = np.sign(y.values)
            pred_direction = np.sign(y_pred)
            direction_accuracy = np.mean(y_direction == pred_direction)

            self.training_stats = {
                "timestamp": datetime.now().isoformat(),
                "model_type": "tabpfn",
                "n_samples": len(X),
                "n_features": len(self.feature_columns),
                "n_estimators": self.n_estimators,
                "train_time_sec": train_time,
                "mse": float(mse),
                "mae": float(mae),
                "r2_score": float(r2),
                "direction_accuracy": float(direction_accuracy),
                "return_stats": {
                    "mean": float(y.mean()),
                    "std": float(y.std()),
                    "min": float(y.min()),
                    "max": float(y.max()),
                },
            }

            logger.info(
                f"TabPFN initialized: {len(X)} samples, "
                f"MAE={mae:.4f}, R²={r2:.3f}, "
                f"dir_acc={direction_accuracy:.1%}, "
                f"time={train_time:.2f}s"
            )

            self.is_trained = True

        except Exception as e:
            logger.error(f"TabPFN training failed: {e}")
            raise

    def fit(self, df: pd.DataFrame, horizon_days: int = 1) -> "TabPFNForecaster":
        """
        Fit the model (ensemble-compatible interface).

        Args:
            df: OHLC DataFrame with technical indicators
            horizon_days: Forecast horizon in days

        Returns:
            self (for method chaining)
        """
        self._last_df = df.copy()

        X, y = self.prepare_training_data(df, horizon_days=horizon_days)

        if len(X) >= settings.min_bars_for_training:
            self.train(X, y)
        else:
            logger.warning(
                f"Insufficient data for TabPFN: {len(X)} < {settings.min_bars_for_training}"
            )

        return self

    def predict(
        self,
        X: Optional[pd.DataFrame] = None,
        horizon_days: int = 1,
        return_intervals: bool = True
    ) -> Dict[str, Any]:
        """
        Make prediction with uncertainty quantification.

        Args:
            X: Feature DataFrame OR OHLC DataFrame
            horizon_days: Forecast horizon (if X is OHLC data)
            return_intervals: Whether to compute prediction intervals

        Returns:
            Dict with label, confidence, forecast_return, intervals
        """
        if not self.is_trained:
            raise ValueError("TabPFN model must be trained before prediction")

        # Handle OHLC data input
        if X is not None and 'close' in X.columns:
            df = X
            engineer = TemporalFeatureEngineer()
            last_idx = len(df) - 1
            features = engineer.add_features_to_point(df, last_idx)
            X_features = pd.DataFrame([features])
        else:
            X_features = X if X is not None else self._last_df
            if X_features is None:
                raise ValueError("No features provided and no cached dataframe")

        # Ensure features match training
        X_features = X_features[self.feature_columns]
        X_scaled = self.scaler.transform(X_features)

        # Get prediction
        start_time = datetime.now()
        y_pred = self.model.predict(X_scaled)[0]

        # Get prediction intervals if requested
        # TabPFN's quantiles often return the same value as point prediction (no real UQ).
        # We use training MAE to build a pseudo-interval when quantiles collapse.
        if return_intervals:
            try:
                y_pred_q10 = self.model.predict(X_scaled, quantiles=[0.1])[0]
                y_pred_q90 = self.model.predict(X_scaled, quantiles=[0.9])[0]
            except Exception as e:
                logger.warning(f"Could not compute quantiles: {e}")
                y_pred_q10 = y_pred_q90 = y_pred
            interval_width = abs(y_pred_q90 - y_pred_q10)
            # If quantiles collapsed to point prediction, use training MAE for uncertainty
            training_mae = self.training_stats.get("mae", 0.02)
            if interval_width < 1e-10:
                # ~80% interval: y_pred ± 1.28 * MAE (normal approximation)
                half_width = 1.28 * float(training_mae)
                y_pred_q10 = y_pred - half_width
                y_pred_q90 = y_pred + half_width
                interval_width = 2.0 * half_width
                logger.debug(
                    f"TabPFN quantiles collapsed; using MAE-based interval width={interval_width:.4f}"
                )
        else:
            training_mae = self.training_stats.get("mae", 0.02)
            half_width = 1.28 * float(training_mae)
            y_pred_q10 = y_pred - half_width
            y_pred_q90 = y_pred + half_width
            interval_width = 2.0 * half_width

        inference_time = (datetime.now() - start_time).total_seconds()

        # Convert prediction to direction label
        if y_pred < self._bearish_thresh:
            label = "bearish"
        elif y_pred > self._bullish_thresh:
            label = "bullish"
        else:
            label = "neutral"

        # Confidence from actual prediction uncertainty (interval width), never 100%
        # Reference scale: typical return magnitude so relative_width is comparable
        ref_scale = max(abs(y_pred), 0.005, abs(self._bullish_thresh))
        relative_width = interval_width / ref_scale
        # Tighter interval = higher confidence; cap at 0.95 (never claim 100%)
        confidence = max(0.50, min(0.95, 1.0 - min(2.0, relative_width) * 0.35))
        # Slight boost for strong signals (far from neutral), but keep cap
        distance_from_neutral = max(0, abs(y_pred) - abs(self._bullish_thresh))
        if distance_from_neutral > 0 and ref_scale > 1e-6:
            strength_boost = min(0.10, distance_from_neutral / ref_scale * 0.5)
            confidence = min(0.95, confidence + strength_boost)
        # Neutral predictions are inherently uncertain; cap their confidence
        if label == "neutral":
            confidence = min(0.75, confidence)

        logger.info(
            f"TabPFN prediction: {label} (conf={confidence:.3f}, "
            f"return={y_pred:.4f}, interval=[{y_pred_q10:.4f}, {y_pred_q90:.4f}])"
        )

        # Return ensemble-compatible format
        return {
            "label": label,
            "confidence": float(confidence),
            "forecast_return": float(y_pred),
            "probabilities": {
                "bearish": 1.0 - confidence if label == "bearish" else 0.33,
                "neutral": 1.0 - confidence if label == "neutral" else 0.33,
                "bullish": 1.0 - confidence if label == "bullish" else 0.33,
            },
            "intervals": {
                "q10": float(y_pred_q10),
                "median": float(y_pred),
                "q90": float(y_pred_q90),
                "width": float(interval_width),
            },
            "inference_time_sec": inference_time,
            "model_type": "tabpfn",
        }

    def generate_forecast(
        self,
        df: pd.DataFrame,
        horizon: str,
        calibrator=None,
        validate_data: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate complete forecast (compatible with BaselineForecaster).

        Args:
            df: OHLC DataFrame
            horizon: Horizon string ('1D', '5D', etc.)
            calibrator: Optional confidence calibrator
            validate_data: Whether to validate data first

        Returns:
            Forecast dictionary
        """
        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Fit and predict
        self.fit(df, horizon_days=horizon_days)
        prediction = self.predict(df, horizon_days=horizon_days)

        # Apply calibration if provided
        if calibrator is not None and hasattr(calibrator, 'calibrate'):
            prediction['confidence'] = calibrator.calibrate(prediction['confidence'])

        return prediction

    @staticmethod
    def _parse_horizon(horizon: str) -> int:
        """Parse horizon string to days."""
        horizon = horizon.upper().strip()
        if horizon == '1D':
            return 1
        elif horizon == '5D' or horizon == '1W':
            return 5
        elif horizon == '10D':
            return 10
        elif horizon == '20D' or horizon == '1M':
            return 20
        else:
            # Try to extract number
            import re
            match = re.search(r'(\d+)', horizon)
            if match:
                return int(match.group(1))
            return 1


def is_tabpfn_available() -> bool:
    """Check if TabPFN is available."""
    return TABPFN_AVAILABLE


def create_tabpfn_forecaster(**kwargs) -> Optional[TabPFNForecaster]:
    """
    Factory function to create TabPFN forecaster with error handling.

    Returns:
        TabPFNForecaster if available, None otherwise
    """
    if not TABPFN_AVAILABLE:
        logger.warning("TabPFN not available")
        return None

    try:
        return TabPFNForecaster(**kwargs)
    except Exception as e:
        logger.error(f"Failed to create TabPFN forecaster: {e}")
        return None
