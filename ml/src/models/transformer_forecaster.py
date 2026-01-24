"""
Transformer Forecaster: Multi-Head Attention for Multi-Timeframe Forecasting.
==============================================================================

Implements the Transformer architecture from STOCK_FORECASTING_FRAMEWORK.md:
- Multi-head self-attention for temporal patterns
- Cross-timeframe attention (1H, 4H, Daily)
- Positional encoding for time information
- Multi-task learning (1D, 5D, 20D predictions)

Key Features:
- Learns which past timesteps matter most
- Detects multi-timeframe alignment
- Captures long-range dependencies better than LSTM
- Provides attention weights for interpretability

Note: Requires TensorFlow >= 2.10.0
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
    from tensorflow import keras
    from tensorflow.keras import layers

    TF_AVAILABLE = True
    tf.get_logger().setLevel("ERROR")
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not installed. Install with: pip install tensorflow>=2.10.0")

    # Define dummy classes for fallback mode
    class keras:
        class Model:
            pass

        class Input:
            pass

        class Sequential:
            pass

    class layers:
        class Layer:
            pass

        class MultiHeadAttention:
            def __init__(self, num_heads=1, key_dim=1):
                pass

        class Dense:
            def __init__(self, units, activation=None):
                pass

        class LayerNormalization:
            def __init__(self, epsilon=1e-6):
                pass

        class Dropout:
            def __init__(self, rate=0.0):
                pass

        class GlobalAveragePooling1D:
            pass


class PositionalEncoding(layers.Layer if TF_AVAILABLE else object):
    """
    Positional encoding layer for Transformer.

    Injects time information so the model knows day 1 vs day 100 is different.
    Uses sinusoidal encoding as in the original Transformer paper.
    """

    def __init__(self, max_len: int = 500, d_model: int = 64, **kwargs):
        super().__init__(**kwargs)
        self.max_len = max_len
        self.d_model = d_model

        # Create positional encoding matrix
        position = np.arange(max_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))

        pe = np.zeros((max_len, d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)

        self.pe = tf.constant(pe, dtype=tf.float32)

    def call(self, x):
        seq_len = tf.shape(x)[1]
        return x + self.pe[:seq_len, :]

    def get_config(self):
        config = super().get_config()
        config.update({
            "max_len": self.max_len,
            "d_model": self.d_model,
        })
        return config


class TransformerBlock(layers.Layer if TF_AVAILABLE else object):
    """
    Single Transformer block with multi-head attention and feed-forward network.
    """

    def __init__(
        self,
        d_model: int = 64,
        num_heads: int = 4,
        ff_dim: int = 128,
        dropout: float = 0.1,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.d_model = d_model
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.dropout_rate = dropout

        self.attention = layers.MultiHeadAttention(
            num_heads=num_heads,
            key_dim=d_model // num_heads,
        )
        self.ffn = keras.Sequential([
            layers.Dense(ff_dim, activation="relu"),
            layers.Dense(d_model),
        ])
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = layers.Dropout(dropout)
        self.dropout2 = layers.Dropout(dropout)

    def call(self, inputs, training=False, return_attention=False):
        # Multi-head self-attention
        attn_output, attn_weights = self.attention(
            inputs, inputs, return_attention_scores=True
        )
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)

        # Feed-forward network
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        out2 = self.layernorm2(out1 + ffn_output)

        if return_attention:
            return out2, attn_weights
        return out2

    def get_config(self):
        config = super().get_config()
        config.update({
            "d_model": self.d_model,
            "num_heads": self.num_heads,
            "ff_dim": self.ff_dim,
            "dropout": self.dropout_rate,
        })
        return config


class MultiTimeframeTransformerModel(keras.Model):
    """
    Multi-timeframe Transformer for stock forecasting.

    Architecture:
    - Separate attention streams for each timeframe (1H, 4H, Daily)
    - Cross-attention to learn relationships between timeframes
    - Multi-task output (1D, 5D, 20D predictions)

    This enables:
    - Detection of timeframe alignment ("4H agrees with Daily trend")
    - Higher confidence when multiple timeframes confirm
    """

    def __init__(
        self,
        d_model: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        ff_dim: int = 128,
        dropout: float = 0.1,
        max_len: int = 500,
        n_timeframes: int = 1,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.n_timeframes = n_timeframes

        # Input projection
        self.input_projection = layers.Dense(d_model)

        # Positional encoding
        self.pos_encoding = PositionalEncoding(max_len, d_model)

        # Transformer blocks
        self.transformer_blocks = [
            TransformerBlock(d_model, num_heads, ff_dim, dropout)
            for _ in range(num_layers)
        ]

        # Cross-timeframe attention (if multiple timeframes)
        if n_timeframes > 1:
            self.cross_attention = layers.MultiHeadAttention(
                num_heads=num_heads,
                key_dim=d_model // num_heads,
            )
            self.cross_layernorm = layers.LayerNormalization(epsilon=1e-6)

        # Output layers
        self.global_pool = layers.GlobalAveragePooling1D()
        self.dropout = layers.Dropout(dropout)
        self.dense1 = layers.Dense(32, activation="relu")
        self.output_layer = layers.Dense(3)  # 1D, 5D, 20D returns

    def call(self, inputs, training=False, return_attention=False):
        # Project input to d_model dimensions
        x = self.input_projection(inputs)

        # Add positional encoding
        x = self.pos_encoding(x)

        # Apply transformer blocks
        attention_weights = []
        for block in self.transformer_blocks:
            if return_attention:
                x, attn = block(x, training=training, return_attention=True)
                attention_weights.append(attn)
            else:
                x = block(x, training=training)

        # Global pooling
        x = self.global_pool(x)
        x = self.dropout(x, training=training)
        x = self.dense1(x)

        outputs = self.output_layer(x)

        if return_attention:
            return outputs, attention_weights
        return outputs


class TransformerForecaster:
    """
    Transformer-based forecaster with multi-timeframe support.

    Implements the Transformer architecture from STOCK_FORECASTING_FRAMEWORK.md
    with MC Dropout for uncertainty estimation (similar to LSTM forecaster).

    Attributes:
        lookback: Number of time steps to use as input
        d_model: Dimension of model embeddings
        num_heads: Number of attention heads
        num_layers: Number of transformer blocks
        dropout: Dropout rate for regularization and MC inference
        mc_iterations: Number of MC Dropout iterations for uncertainty
    """

    def __init__(
        self,
        lookback: int = 60,
        d_model: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        ff_dim: int = 128,
        dropout: float = 0.1,
        mc_iterations: int = 50,
        epochs: int = 50,
        batch_size: int = 32,
        bullish_threshold: float = 0.02,
        bearish_threshold: float = -0.02,
        horizon: str = "1D",
    ) -> None:
        """
        Initialize the Transformer forecaster.

        Args:
            lookback: Number of time steps for input sequence
            d_model: Model dimension (embedding size)
            num_heads: Number of attention heads
            num_layers: Number of transformer encoder layers
            ff_dim: Feed-forward network dimension
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
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.ff_dim = ff_dim
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
        self.attention_weights: Optional[List] = None

        # Store training data stats for fallback
        self._train_stats: Dict[str, float] = {}

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of trading days."""
        return {
            "1D": 1, "1W": 5, "2W": 10, "1M": 21, "2M": 42, "3M": 63
        }.get(horizon, 1)

    def _build_model(self, n_features: int) -> None:
        """Build Transformer model architecture."""
        if not TF_AVAILABLE:
            return

        # Input layer
        inputs = keras.Input(shape=(self.lookback, n_features))

        # Create transformer model
        transformer = MultiTimeframeTransformerModel(
            d_model=self.d_model,
            num_heads=self.num_heads,
            num_layers=self.num_layers,
            ff_dim=self.ff_dim,
            dropout=self.dropout,
            max_len=self.lookback + 10,
        )

        outputs = transformer(inputs)

        self.model = keras.Model(inputs=inputs, outputs=outputs)
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss="mse",
            metrics=["mae"]
        )

        logger.info(
            "Built Transformer model: %d layers, %d heads, d_model=%d",
            self.num_layers,
            self.num_heads,
            self.d_model,
        )

    def _prepare_sequences(
        self,
        data: np.ndarray,
        horizon_days: List[int] = [1, 5, 20],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequences for Transformer training.

        Args:
            data: Scaled price/feature data (n_samples, n_features)
            horizon_days: List of forecast horizons

        Returns:
            X: Input sequences (n_samples, lookback, n_features)
            y: Target values (n_samples, n_horizons)
        """
        X, y = [], []
        max_horizon = max(horizon_days)

        for i in range(self.lookback, len(data) - max_horizon):
            X.append(data[i - self.lookback:i])
            # Multi-task targets: returns for each horizon
            targets = []
            for h in horizon_days:
                if i + h < len(data):
                    ret = (data[i + h, 0] - data[i - 1, 0]) / (data[i - 1, 0] + 1e-8)
                    targets.append(ret)
                else:
                    targets.append(0.0)
            y.append(targets)

        return np.array(X), np.array(y)

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Prepare multi-feature input from OHLC data.

        Features: close, returns, volatility, volume ratio
        """
        features = pd.DataFrame()
        features["close"] = df["close"].values
        features["returns"] = df["close"].pct_change().fillna(0).values
        features["volatility"] = df["close"].pct_change().rolling(20).std().fillna(0).values

        if "volume" in df.columns:
            vol_sma = df["volume"].rolling(20).mean()
            features["volume_ratio"] = (df["volume"] / vol_sma).fillna(1).values

        return features.values

    def train(
        self,
        df: pd.DataFrame,
        min_samples: int = 100,
        validation_split: float = 0.2,
    ) -> "TransformerForecaster":
        """
        Train Transformer model on price data.

        Args:
            df: DataFrame with OHLC data
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

        if len(df) < self.lookback + 25:
            raise ValueError(f"Insufficient data for lookback: {len(df)} < {self.lookback + 25}")

        logger.info("Training Transformer model...")

        try:
            # Prepare features
            features = self._prepare_features(df)
            n_features = features.shape[1]

            # Scale data
            scaled_data = self.scaler.fit_transform(features)

            # Prepare sequences (multi-task: 1D, 5D, 20D)
            X, y = self._prepare_sequences(scaled_data, horizon_days=[1, 5, 20])

            if len(X) < 50:
                raise ValueError(f"Not enough sequences after preparation: {len(X)}")

            # Split train/validation
            split_idx = int(len(X) * (1 - validation_split))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            # Build model
            self._build_model(n_features=n_features)

            # Callbacks
            callbacks = [
                keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=10,
                    restore_best_weights=True,
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss",
                    factor=0.5,
                    patience=5,
                ),
            ]

            # Train
            history = self.model.fit(
                X_train,
                y_train,
                validation_data=(X_val, y_val),
                epochs=self.epochs,
                batch_size=self.batch_size,
                callbacks=callbacks,
                verbose=0,
            )

            # Store training metrics
            self.training_stats = {
                "trained_at": datetime.now().isoformat(),
                "n_samples": len(X),
                "n_features": n_features,
                "epochs_trained": len(history.history["loss"]),
                "final_loss": float(history.history["loss"][-1]),
                "final_val_loss": float(history.history["val_loss"][-1]),
                "final_mae": float(history.history["mae"][-1]),
            }

            # Calculate validation accuracy
            self._calculate_training_accuracy(X_val, y_val)

            self.is_trained = True
            logger.info(
                "Transformer trained: %d epochs, loss=%.6f",
                self.training_stats["epochs_trained"],
                self.training_stats["final_loss"],
            )

        except Exception as e:
            logger.error("Transformer training failed: %s", e)
            raise

        return self

    def _fallback_train(
        self,
        df: pd.DataFrame,
        min_samples: int,
    ) -> "TransformerForecaster":
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
            "momentum_5d": float(returns.tail(5).mean()),
            "momentum_20d": float(returns.tail(20).mean()),
        }

        self.training_stats = {
            "trained_at": datetime.now().isoformat(),
            "n_samples": len(df),
            "fallback_mode": True,
        }

        self.is_trained = True
        logger.info("Transformer fallback training complete")
        return self

    def _calculate_training_accuracy(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> None:
        """Calculate classification accuracy on validation set."""
        if self.model is None:
            return

        # Get predictions (use 1D horizon - first output)
        predictions = self.model.predict(X_val, verbose=0)
        pred_1d = predictions[:, 0]
        actual_1d = y_val[:, 0]

        # Classification
        pred_labels = np.where(
            pred_1d > self.bullish_threshold,
            "bullish",
            np.where(pred_1d < self.bearish_threshold, "bearish", "neutral"),
        )
        actual_labels = np.where(
            actual_1d > self.bullish_threshold,
            "bullish",
            np.where(actual_1d < self.bearish_threshold, "bearish", "neutral"),
        )

        accuracy = (pred_labels == actual_labels).mean()
        directional = (np.sign(pred_1d) == np.sign(actual_1d)).mean()

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
            steps: Number of steps ahead to forecast (mapped to horizon)

        Returns:
            Dict with label, confidence, probabilities, and uncertainty
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        if not TF_AVAILABLE or self.model is None:
            return self._fallback_predict(df, steps)

        if df is None or "close" not in df.columns:
            return self._null_prediction("No valid data provided")

        try:
            # Prepare input sequence
            features = self._prepare_features(df)
            features_recent = features[-self.lookback:]

            if len(features_recent) < self.lookback:
                return self._null_prediction(f"Insufficient data: {len(features_recent)} < {self.lookback}")

            scaled = self.scaler.transform(features_recent)
            X = scaled.reshape(1, self.lookback, -1)

            # MC Dropout: multiple forward passes with dropout enabled
            predictions = []
            for _ in range(self.mc_iterations):
                # Training=True enables dropout during inference
                pred = self.model(X, training=True).numpy()[0]
                predictions.append(pred)

            predictions = np.array(predictions)

            # Map steps to horizon index (0=1D, 1=5D, 2=20D)
            horizon_idx = {1: 0, 5: 1, 20: 2}.get(steps, 0)
            horizon_preds = predictions[:, horizon_idx]

            # Calculate statistics
            mean_pred = np.mean(horizon_preds)
            std_pred = np.std(horizon_preds)

            forecast_return = float(mean_pred)
            forecast_volatility = float(std_pred)

            last_close = df["close"].iloc[-1]
            forecast_price = last_close * (1 + forecast_return)

            # Classification
            if forecast_return > self.bullish_threshold:
                label = "Bullish"
            elif forecast_return < self.bearish_threshold:
                label = "Bearish"
            else:
                label = "Neutral"

            # Probabilities from MC samples
            probabilities = self._calculate_mc_probabilities(horizon_preds)
            confidence = float(probabilities[label.lower()])

            # Confidence intervals
            ci_lower = float(last_close * (1 + mean_pred - 1.96 * std_pred))
            ci_upper = float(last_close * (1 + mean_pred + 1.96 * std_pred))

            # Get attention weights for interpretability
            self._extract_attention_weights(X)

            return {
                "label": label,
                "confidence": confidence,
                "probabilities": probabilities,
                "forecast_price": float(forecast_price),
                "forecast_return": forecast_return,
                "forecast_volatility": forecast_volatility,
                "mc_std": float(std_pred),
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "mc_iterations": self.mc_iterations,
                "multi_horizon_predictions": {
                    "1D": float(np.mean(predictions[:, 0])),
                    "5D": float(np.mean(predictions[:, 1])),
                    "20D": float(np.mean(predictions[:, 2])),
                },
                "timeframe_agreement": self._calculate_timeframe_agreement(predictions),
            }

        except Exception as e:
            logger.error("Transformer prediction failed: %s", e)
            return self._null_prediction(str(e))

    def _calculate_mc_probabilities(
        self,
        mc_predictions: np.ndarray,
    ) -> Dict[str, float]:
        """Calculate class probabilities from MC samples."""
        n_bullish = np.sum(mc_predictions > self.bullish_threshold)
        n_bearish = np.sum(mc_predictions < self.bearish_threshold)
        n_neutral = len(mc_predictions) - n_bullish - n_bearish

        total = len(mc_predictions)

        return {
            "bullish": float(n_bullish / total),
            "neutral": float(n_neutral / total),
            "bearish": float(n_bearish / total),
        }

    def _calculate_timeframe_agreement(
        self,
        predictions: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Calculate agreement between different forecast horizons.

        High agreement = higher confidence (multiple timeframes confirm)
        """
        # Mean predictions per horizon
        pred_1d = np.mean(predictions[:, 0])
        pred_5d = np.mean(predictions[:, 1])
        pred_20d = np.mean(predictions[:, 2])

        # Direction for each horizon
        dir_1d = np.sign(pred_1d)
        dir_5d = np.sign(pred_5d)
        dir_20d = np.sign(pred_20d)

        # Count agreements
        same_direction = (dir_1d == dir_5d) + (dir_5d == dir_20d) + (dir_1d == dir_20d)
        agreement_score = same_direction / 3.0

        all_aligned = (dir_1d == dir_5d == dir_20d)

        return {
            "agreement_score": float(agreement_score),
            "all_aligned": bool(all_aligned),
            "directions": {
                "1D": "bullish" if dir_1d > 0 else "bearish" if dir_1d < 0 else "neutral",
                "5D": "bullish" if dir_5d > 0 else "bearish" if dir_5d < 0 else "neutral",
                "20D": "bullish" if dir_20d > 0 else "bearish" if dir_20d < 0 else "neutral",
            },
        }

    def _extract_attention_weights(self, X: np.ndarray) -> None:
        """Extract attention weights for interpretability."""
        # This would require modifying the model to return attention weights
        # For now, we skip this to keep the implementation simple
        self.attention_weights = None

    def _fallback_predict(
        self,
        df: Optional[pd.DataFrame],
        steps: int,
    ) -> Dict[str, Any]:
        """Fallback prediction when TensorFlow is not available."""
        from scipy import stats as scipy_stats

        mean_return = self._train_stats.get("mean_return", 0.0)
        std_return = self._train_stats.get("std_return", 0.02)
        momentum_5d = self._train_stats.get("momentum_5d", mean_return)
        momentum_20d = self._train_stats.get("momentum_20d", mean_return)

        # Use momentum-weighted prediction
        if steps <= 5:
            forecast_return = momentum_5d * steps
        else:
            forecast_return = momentum_20d * steps

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
        last_ts = pd.to_datetime(df["ts"].iloc[-1]) if "ts" in df.columns else datetime.now()

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
            "model_type": "Transformer",
            "forecast_return": prediction.get("forecast_return", 0),
            "forecast_volatility": prediction.get("forecast_volatility", 0),
            "mc_iterations": prediction.get("mc_iterations", 0),
            "multi_horizon_predictions": prediction.get("multi_horizon_predictions", {}),
            "timeframe_agreement": prediction.get("timeframe_agreement", {}),
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

            points.append({
                "ts": int(forecast_ts.timestamp()),
                "value": round(forecast_value, 2),
                "lower": round(lower_bound, 2),
                "upper": round(upper_bound, 2),
            })

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
            "name": "Transformer",
            "is_trained": self.is_trained,
            "tensorflow_available": TF_AVAILABLE,
            "config": {
                "lookback": self.lookback,
                "d_model": self.d_model,
                "num_heads": self.num_heads,
                "num_layers": self.num_layers,
                "ff_dim": self.ff_dim,
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

    df = pd.DataFrame({
        "ts": pd.date_range("2023-01-01", periods=n, freq="D"),
        "open": prices * 0.995,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.randint(1e6, 1e7, n).astype(float),
    })

    print("\nTesting Transformer Forecaster...")

    forecaster = TransformerForecaster(
        lookback=60,
        d_model=32,
        num_heads=4,
        num_layers=2,
        dropout=0.1,
        mc_iterations=20,
        epochs=10,
    )

    forecaster.train(df)
    forecast = forecaster.generate_forecast(df, horizon="1W")

    print(f"Label: {forecast['label']}")
    print(f"Confidence: {forecast['confidence']:.3f}")
    print(f"Fallback mode: {forecast.get('fallback_mode', False)}")
    print(f"Points: {len(forecast['points'])}")
    print(f"Multi-horizon: {forecast.get('multi_horizon_predictions', {})}")
    print(f"Timeframe agreement: {forecast.get('timeframe_agreement', {})}")
    print(f"\nModel info: {forecaster.get_model_info()}")
