"""
LSTM Forecaster: Neural network with MC Dropout for uncertainty estimation.
============================================================================

Uses LSTM (Long Short-Term Memory) networks for sequence-based forecasting:
- Captures temporal dependencies in price series
- MC Dropout for uncertainty quantification
- Automatic sequence preparation

Key Features:
- Configurable architecture (layers, units, dropout)
- Monte Carlo Dropout for prediction intervals
- MinMax scaling for stable training
- Compatible with existing ensemble framework

Note: Requires TensorFlow. Install with:
    pip install tensorflow>=2.10.0
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

# Try to import TensorFlow/Keras
try:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.models import Sequential

    TF_AVAILABLE = True
    # Suppress TensorFlow warnings
    tf.get_logger().setLevel("ERROR")
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not installed. Install with: pip install tensorflow>=2.10.0")


class LSTMForecaster:
    """
    LSTM-based forecaster with Monte Carlo Dropout uncertainty.

    Uses stacked LSTM layers to capture temporal patterns in price data.
    MC Dropout provides uncertainty estimates by running multiple forward
    passes with dropout enabled at inference time.

    Attributes:
        lookback: Number of time steps to use as input
        units: Number of LSTM units per layer
        n_layers: Number of LSTM layers
        dropout: Dropout rate for regularization and MC inference
        mc_iterations: Number of MC Dropout iterations for uncertainty
    """

    def __init__(
        self,
        lookback: int = 60,
        units: int = 64,
        n_layers: int = 2,
        dropout: float = 0.2,
        mc_iterations: int = 100,
        epochs: int = 50,
        batch_size: int = 32,
        bullish_threshold: float = 0.02,
        bearish_threshold: float = -0.02,
        horizon: str = "1D",
    ) -> None:
        """
        Initialize the LSTM forecaster.

        Args:
            lookback: Number of time steps for input sequence
            units: LSTM units per layer
            n_layers: Number of LSTM layers
            dropout: Dropout rate (used for both training and MC inference)
            mc_iterations: Number of forward passes for MC Dropout
            epochs: Training epochs
            batch_size: Training batch size
            bullish_threshold: Return above this = bullish
            bearish_threshold: Return below this = bearish
            horizon: Forecast horizon ("1D", "1W", etc.)
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow not available. Forecaster will use fallback mode.")

        self.lookback = lookback
        self.units = units
        self.n_layers = n_layers
        self.dropout = dropout
        self.mc_iterations = mc_iterations
        self.epochs = epochs
        self.batch_size = batch_size
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.horizon = horizon

        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
        self.diagnostics: Dict[str, Any] = {}

        # Store training data stats for fallback
        self._train_stats: Dict[str, float] = {}

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of trading days."""
        return {"1D": 1, "1W": 5, "2W": 10, "1M": 21, "2M": 42, "3M": 63}.get(horizon, 1)

    def _build_model(self, input_shape: Tuple[int, int]) -> None:
        """Build LSTM model architecture."""
        if not TF_AVAILABLE:
            return

        self.model = Sequential()

        # First LSTM layer
        self.model.add(
            LSTM(
                self.units,
                return_sequences=(self.n_layers > 1),
                input_shape=input_shape,
            )
        )
        self.model.add(Dropout(self.dropout))

        # Additional LSTM layers
        for i in range(1, self.n_layers):
            return_sequences = i < self.n_layers - 1
            self.model.add(LSTM(self.units // (2**i), return_sequences=return_sequences))
            self.model.add(Dropout(self.dropout))

        # Dense output layers
        self.model.add(Dense(16, activation="relu"))
        self.model.add(Dense(1))

        self.model.compile(optimizer="adam", loss="mse", metrics=["mae"])

        logger.info(
            "Built LSTM model: %d layers, %d units, %.1f%% dropout",
            self.n_layers,
            self.units,
            self.dropout * 100,
        )

    def _prepare_sequences(
        self,
        data: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequences for LSTM training.

        Args:
            data: Scaled price data (1D array)

        Returns:
            X: Input sequences (n_samples, lookback, 1)
            y: Target values (n_samples,)
        """
        X, y = [], []

        for i in range(self.lookback, len(data)):
            X.append(data[i - self.lookback : i])
            y.append(data[i])

        X = np.array(X)
        y = np.array(y)

        # Reshape X to (samples, timesteps, features)
        X = X.reshape((X.shape[0], X.shape[1], 1))

        return X, y

    def train(
        self,
        df: pd.DataFrame,
        min_samples: int = 100,
        validation_split: float = 0.2,
    ) -> "LSTMForecaster":
        """
        Train LSTM model on price data.

        Args:
            df: DataFrame with 'close' column
            min_samples: Minimum samples required for training
            validation_split: Fraction of data for validation

        Returns:
            self
        """
        if not TF_AVAILABLE:
            logger.warning("TensorFlow not available. Using fallback training.")
            return self._fallback_train(df, min_samples)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        if len(df) < min_samples:
            raise ValueError(f"Insufficient data: {len(df)} < {min_samples}")

        if len(df) < self.lookback + 10:
            raise ValueError(f"Insufficient data for lookback: {len(df)} < {self.lookback + 10}")

        logger.info("Training LSTM model...")

        try:
            # Scale data
            prices = df["close"].values.reshape(-1, 1)
            scaled_data = self.scaler.fit_transform(prices).flatten()

            # Prepare sequences
            X, y = self._prepare_sequences(scaled_data)

            # Split train/validation
            split_idx = int(len(X) * (1 - validation_split))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            # Build model
            self._build_model(input_shape=(self.lookback, 1))

            # Early stopping
            early_stop = EarlyStopping(
                monitor="val_loss",
                patience=10,
                restore_best_weights=True,
            )

            # Train
            history = self.model.fit(
                X_train,
                y_train,
                validation_data=(X_val, y_val),
                epochs=self.epochs,
                batch_size=self.batch_size,
                callbacks=[early_stop],
                verbose=0,
            )

            # Store training metrics
            self.training_stats = {
                "trained_at": datetime.now().isoformat(),
                "n_samples": len(X),
                "epochs_trained": len(history.history["loss"]),
                "final_loss": float(history.history["loss"][-1]),
                "final_val_loss": float(history.history["val_loss"][-1]),
                "final_mae": float(history.history["mae"][-1]),
            }

            # Calculate classification accuracy on validation set
            self._calculate_training_accuracy(X_val, y_val, df)

            self.is_trained = True
            logger.info(
                "LSTM trained: %d epochs, loss=%.6f",
                self.training_stats["epochs_trained"],
                self.training_stats["final_loss"],
            )

        except Exception as e:
            logger.error("LSTM training failed: %s", e)
            raise

        return self

    def _fallback_train(
        self,
        df: pd.DataFrame,
        min_samples: int,
    ) -> "LSTMForecaster":
        """Fallback training when TensorFlow is not available."""
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        if len(df) < min_samples:
            raise ValueError(f"Insufficient data: {len(df)} < {min_samples}")

        # Store statistics for fallback predictions
        returns = df["close"].pct_change().dropna()
        self._train_stats = {
            "mean_return": float(returns.mean()),
            "std_return": float(returns.std()),
            "last_close": float(df["close"].iloc[-1]),
            "lookback_returns": returns.tail(self.lookback).tolist(),
        }

        self.training_stats = {
            "trained_at": datetime.now().isoformat(),
            "n_samples": len(df),
            "fallback_mode": True,
        }

        self.is_trained = True
        logger.info("LSTM fallback training complete")
        return self

    def _calculate_training_accuracy(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        df: pd.DataFrame,
    ) -> None:
        """Calculate classification accuracy on validation set."""
        if self.model is None:
            return

        # Get predictions
        predictions = self.model.predict(X_val, verbose=0).flatten()

        # Inverse transform
        predictions_price = self.scaler.inverse_transform(predictions.reshape(-1, 1)).flatten()
        actual_price = self.scaler.inverse_transform(y_val.reshape(-1, 1)).flatten()

        # Calculate returns
        # We need the previous prices to calculate returns
        start_idx = len(df) - len(y_val) - 1
        prev_prices = df["close"].iloc[start_idx:-1].values

        if len(prev_prices) == len(predictions_price):
            pred_returns = (predictions_price - prev_prices) / prev_prices
            actual_returns = (actual_price - prev_prices) / prev_prices

            # Classification
            pred_labels = np.where(
                pred_returns > self.bullish_threshold,
                "bullish",
                np.where(pred_returns < self.bearish_threshold, "bearish", "neutral"),
            )
            actual_labels = np.where(
                actual_returns > self.bullish_threshold,
                "bullish",
                np.where(actual_returns < self.bearish_threshold, "bearish", "neutral"),
            )

            accuracy = (pred_labels == actual_labels).mean()
            directional = (np.sign(pred_returns) == np.sign(actual_returns)).mean()

            self.training_stats["accuracy"] = float(accuracy)
            self.training_stats["directional_accuracy"] = float(directional)

            logger.info(
                "Validation accuracy: %.3f, directional: %.3f",
                accuracy,
                directional,
            )

    def predict(
        self,
        df: Optional[pd.DataFrame] = None,
        steps: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate forecast with MC Dropout uncertainty.

        Args:
            df: DataFrame with price data
            steps: Number of steps ahead to forecast

        Returns:
            Dict with label, confidence, probabilities, and uncertainty
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        if not TF_AVAILABLE or self.model is None:
            return self._fallback_predict(df, steps)

        if df is None or "close" not in df.columns:
            return self._null_prediction("No valid data provided")
        if len(df) < self.lookback:
            return self._null_prediction(
                f"Insufficient data: {len(df)} < {self.lookback}"
            )

        try:
            # Prepare input sequence
            prices = df["close"].values[-self.lookback :].reshape(-1, 1)
            scaled = self.scaler.transform(prices).flatten()
            X = scaled.reshape(1, self.lookback, 1)

            # MC Dropout: multiple forward passes with dropout enabled
            predictions = []
            for _ in range(self.mc_iterations):
                # Training=True enables dropout during inference
                pred = self.model(X, training=True).numpy()
                predictions.append(float(np.squeeze(pred)))

            predictions = np.asarray(predictions, dtype=float)

            # Inverse transform
            mean_pred = float(np.mean(predictions))
            std_pred = float(np.std(predictions))

            forecast_price = float(self.scaler.inverse_transform([[mean_pred]])[0, 0])
            last_close = float(df["close"].iloc[-1])

            # Calculate return and volatility
            forecast_return = (forecast_price - last_close) / last_close

            # Uncertainty from MC Dropout (in price space)
            price_range = float(np.squeeze(self.scaler.data_max_ - self.scaler.data_min_))
            price_std = std_pred * price_range
            forecast_volatility = float(price_std / last_close)

            # Classification
            if forecast_return > self.bullish_threshold:
                label = "Bullish"
            elif forecast_return < self.bearish_threshold:
                label = "Bearish"
            else:
                label = "Neutral"

            # Probabilities from MC samples
            probabilities = self._calculate_mc_probabilities(
                predictions,
                last_close,
            )

            confidence = float(probabilities[label.lower()])

            return {
                "label": label,
                "confidence": confidence,
                "probabilities": probabilities,
                "forecast_price": float(forecast_price),
                "forecast_return": float(forecast_return),
                "forecast_volatility": forecast_volatility,
                "mc_std": float(std_pred),
                "ci_lower": float(forecast_price - 1.96 * price_std),
                "ci_upper": float(forecast_price + 1.96 * price_std),
                "mc_iterations": self.mc_iterations,
            }

        except Exception as e:
            logger.error("LSTM prediction failed: %s", e)
            return self._null_prediction(str(e))

    def _calculate_mc_probabilities(
        self,
        mc_predictions: np.ndarray,
        last_close: float,
    ) -> Dict[str, float]:
        """Calculate class probabilities from MC samples."""
        # Inverse transform all MC predictions
        mc_predictions = np.asarray(mc_predictions, dtype=float).reshape(-1, 1)
        prices = self.scaler.inverse_transform(mc_predictions).flatten()

        # Calculate returns for each MC sample
        returns = (prices - last_close) / last_close

        # Count classifications
        n_bullish = np.sum(returns > self.bullish_threshold)
        n_bearish = np.sum(returns < self.bearish_threshold)
        n_neutral = len(returns) - n_bullish - n_bearish

        total = len(returns)

        return {
            "bullish": float(n_bullish / total),
            "neutral": float(n_neutral / total),
            "bearish": float(n_bearish / total),
        }

    def _fallback_predict(
        self,
        df: Optional[pd.DataFrame],
        steps: int,
    ) -> Dict[str, Any]:
        """Fallback prediction when TensorFlow is not available."""
        from scipy import stats as scipy_stats

        mean_return = self._train_stats.get("mean_return", 0.0)
        std_return = self._train_stats.get("std_return", 0.02)

        # Simple momentum-based prediction using recent returns
        recent_returns = self._train_stats.get("lookback_returns", [0])
        if recent_returns:
            momentum = np.mean(recent_returns[-5:]) if len(recent_returns) >= 5 else mean_return
        else:
            momentum = mean_return

        forecast_return = momentum * steps
        forecast_volatility = std_return * np.sqrt(steps)

        if forecast_return > self.bullish_threshold:
            label = "Bullish"
        elif forecast_return < self.bearish_threshold:
            label = "Bearish"
        else:
            label = "Neutral"

        # Calculate probabilities
        prob_bearish = scipy_stats.norm.cdf(
            self.bearish_threshold, loc=forecast_return, scale=forecast_volatility
        )
        prob_bullish = 1 - scipy_stats.norm.cdf(
            self.bullish_threshold, loc=forecast_return, scale=forecast_volatility
        )
        prob_neutral = 1 - prob_bearish - prob_bullish

        total = prob_bearish + prob_neutral + prob_bullish
        probabilities = {
            "bearish": float(prob_bearish / total),
            "neutral": float(prob_neutral / total),
            "bullish": float(prob_bullish / total),
        }

        return {
            "label": label,
            "confidence": float(probabilities[label.lower()]),
            "probabilities": probabilities,
            "forecast_return": float(forecast_return),
            "forecast_volatility": float(forecast_volatility),
            "fallback_mode": True,
        }

    def generate_forecast(
        self,
        df: pd.DataFrame,
        horizon: str = "1D",
    ) -> Dict[str, Any]:
        """
        Generate complete forecast compatible with ensemble framework.

        Args:
            df: DataFrame with OHLC data
            horizon: Forecast horizon ("1D", "1W", etc.)

        Returns:
            Forecast dict with label, confidence, points, etc.
        """
        horizon_days = self._parse_horizon(horizon)

        if not self.is_trained:
            self.train(df)

        prediction = self.predict(df=df, steps=horizon_days)

        # Generate forecast points
        last_close = df["close"].iloc[-1]
        last_ts = pd.to_datetime(df["ts"].iloc[-1])

        points = self._generate_forecast_points(
            last_ts,
            last_close,
            prediction["forecast_return"],
            prediction.get("forecast_volatility", 0.02),
            horizon_days,
        )

        return {
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "raw_confidence": prediction["confidence"],
            "horizon": horizon,
            "points": points,
            "probabilities": prediction["probabilities"],
            "model_type": "LSTM",
            "forecast_return": prediction.get("forecast_return", 0),
            "forecast_volatility": prediction.get("forecast_volatility", 0),
            "mc_iterations": prediction.get("mc_iterations", 0),
            "diagnostics": self.diagnostics,
            "fallback_mode": prediction.get("fallback_mode", False),
        }

    def _generate_forecast_points(
        self,
        last_ts: datetime,
        last_close: float,
        forecast_return: float,
        forecast_volatility: float,
        horizon_days: int,
    ) -> List[Dict[str, Any]]:
        """Generate forecast points for visualization."""
        points = []

        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            progress = i / horizon_days

            cumulative_return = forecast_return * progress
            cumulative_volatility = forecast_volatility * np.sqrt(i)

            forecast_value = float(last_close) * (1 + cumulative_return)

            z_score = 1.96
            lower_bound = forecast_value * (1 - z_score * cumulative_volatility)
            upper_bound = forecast_value * (1 + z_score * cumulative_volatility)

            points.append(
                {
                    "ts": int(forecast_ts.timestamp()),
                    "value": round(forecast_value, 2),
                    "lower": round(lower_bound, 2),
                    "upper": round(upper_bound, 2),
                }
            )

        return points

    def _null_prediction(self, error_msg: str) -> Dict[str, Any]:
        """Return null prediction when model fails."""
        return {
            "label": "Neutral",
            "confidence": 0.33,
            "probabilities": {
                "bearish": 0.33,
                "neutral": 0.34,
                "bullish": 0.33,
            },
            "forecast_return": 0.0,
            "forecast_volatility": 0.0,
            "error": error_msg,
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        info = {
            "name": "LSTM",
            "is_trained": self.is_trained,
            "tensorflow_available": TF_AVAILABLE,
            "config": {
                "lookback": self.lookback,
                "units": self.units,
                "n_layers": self.n_layers,
                "dropout": self.dropout,
                "mc_iterations": self.mc_iterations,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
            },
            "thresholds": {
                "bullish": self.bullish_threshold,
                "bearish": self.bearish_threshold,
            },
            "training_stats": self.training_stats,
        }

        if self.model is not None:
            info["model_params"] = self.model.count_params()

        return info


def is_tensorflow_available() -> bool:
    """Check if TensorFlow is installed."""
    return TF_AVAILABLE


if __name__ == "__main__":
    print(f"TensorFlow available: {TF_AVAILABLE}")

    # Create test data
    np.random.seed(42)
    n = 300
    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    df = pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        }
    )

    print("\nTesting LSTM Forecaster...")

    forecaster = LSTMForecaster(
        lookback=60,
        units=64,
        n_layers=2,
        dropout=0.2,
        mc_iterations=50,
        epochs=10,
    )

    forecaster.train(df)
    forecast = forecaster.generate_forecast(df, horizon="1W")

    print(f"Label: {forecast['label']}")
    print(f"Confidence: {forecast['confidence']:.3f}")
    print(f"Fallback mode: {forecast.get('fallback_mode', False)}")
    print(f"Points: {len(forecast['points'])}")
    print(f"\nModel info: {forecaster.get_model_info()}")
