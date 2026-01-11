"""
Multi-Model Ensemble Forecaster: RF + GB + ARIMA-GARCH + Prophet + LSTM
========================================================================

Flexible ensemble combining up to 5 model types:
- Random Forest (ML - captures non-linear patterns)
- Gradient Boosting (ML - captures complex interactions)
- ARIMA-GARCH (Statistical - mean reversion + volatility)
- Prophet (Statistical - seasonality + trend)
- LSTM (Deep Learning - temporal sequences with MC Dropout uncertainty)

Key Features:
- Configurable model inclusion/exclusion
- Dynamic weight optimization
- Graceful degradation on model failures
- Agreement scoring across all models
- Comprehensive uncertainty quantification
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MultiModelEnsemble:
    """
    Multi-model ensemble combining ML, statistical, and deep learning approaches.

    Default weights (when all models enabled):
    - RF: 20%
    - GB: 20%
    - ARIMA-GARCH: 20%
    - Prophet: 20%
    - LSTM: 20%

    Weights are automatically redistributed when models are disabled
    or fail during training.
    """

    # Model type constants
    MODEL_RF = "rf"
    MODEL_GB = "gb"
    MODEL_AG = "arima_garch"
    MODEL_PROPHET = "prophet"
    MODEL_LSTM = "lstm"

    def __init__(
        self,
        horizon: str = "1D",
        symbol_id: Optional[str] = None,
        enable_rf: bool = True,
        enable_gb: bool = True,
        enable_arima_garch: bool = True,
        enable_prophet: bool = True,
        enable_lstm: bool = True,
        weights: Optional[Dict[str, float]] = None,
        arima_order: Tuple[int, int, int] = (1, 0, 1),
        auto_select_arima_order: bool = False,
        lstm_lookback: int = 60,
        lstm_units: int = 64,
        lstm_epochs: int = 50,
    ) -> None:
        """
        Initialize Multi-Model Ensemble.

        Args:
            horizon: Forecast horizon ("1D", "1W", etc.)
            symbol_id: Optional symbol ID for weight lookup
            enable_rf: Enable Random Forest model
            enable_gb: Enable Gradient Boosting model
            enable_arima_garch: Enable ARIMA-GARCH model
            enable_prophet: Enable Prophet model
            enable_lstm: Enable LSTM model
            weights: Optional custom weights {model_type: weight}
            arima_order: ARIMA(p, d, q) order tuple
            auto_select_arima_order: Auto-select optimal ARIMA order
            lstm_lookback: LSTM lookback window
            lstm_units: LSTM hidden units
            lstm_epochs: LSTM training epochs
        """
        self.horizon = horizon
        self.symbol_id = symbol_id

        # Model enablement flags
        self.enable_rf = enable_rf
        self.enable_gb = enable_gb
        self.enable_arima_garch = enable_arima_garch
        self.enable_prophet = enable_prophet
        self.enable_lstm = enable_lstm

        # LSTM config
        self.lstm_lookback = lstm_lookback
        self.lstm_units = lstm_units
        self.lstm_epochs = lstm_epochs

        # Initialize models
        self.models: Dict[str, object] = {}
        self.model_trained: Dict[str, bool] = {}

        self._init_models(arima_order, auto_select_arima_order)

        # Set weights
        if weights:
            self.weights = weights.copy()
        else:
            self.weights = self._calculate_default_weights()

        self._normalize_weights()

        self.is_trained = False
        self.training_stats: Dict = {}

        logger.info(
            "MultiModelEnsemble initialized: %s",
            {k: f"{v:.2f}" for k, v in self.weights.items()},
        )

    def _init_models(
        self,
        arima_order: Tuple[int, int, int],
        auto_select_arima_order: bool,
    ) -> None:
        """Initialize all enabled models."""

        # RF + GB via base ensemble
        if self.enable_rf or self.enable_gb:
            try:
                from src.models.ensemble_forecaster import EnsembleForecaster

                self.base_ensemble = EnsembleForecaster(
                    horizon=self.horizon,
                    symbol_id=self.symbol_id,
                    rf_weight=0.5,
                    gb_weight=0.5,
                    use_db_weights=False,
                )
                if self.enable_rf:
                    self.models[self.MODEL_RF] = self.base_ensemble
                    self.model_trained[self.MODEL_RF] = False
                if self.enable_gb:
                    self.models[self.MODEL_GB] = self.base_ensemble
                    self.model_trained[self.MODEL_GB] = False
            except Exception as e:
                logger.warning("Could not initialize RF/GB: %s", e)
                self.enable_rf = False
                self.enable_gb = False

        # ARIMA-GARCH
        if self.enable_arima_garch:
            try:
                from src.models.arima_garch_forecaster import (
                    ArimaGarchForecaster,
                )

                self.models[self.MODEL_AG] = ArimaGarchForecaster(
                    arima_order=arima_order,
                    auto_select_order=auto_select_arima_order,
                    horizon=self.horizon,
                )
                self.model_trained[self.MODEL_AG] = False
            except Exception as e:
                logger.warning("Could not initialize ARIMA-GARCH: %s", e)
                self.enable_arima_garch = False

        # Prophet
        if self.enable_prophet:
            try:
                from src.models.prophet_forecaster import ProphetForecaster

                self.models[self.MODEL_PROPHET] = ProphetForecaster(
                    weekly_seasonality=True,
                    yearly_seasonality=False,
                    horizon=self.horizon,
                )
                self.model_trained[self.MODEL_PROPHET] = False
            except Exception as e:
                logger.warning("Could not initialize Prophet: %s", e)
                self.enable_prophet = False

        # LSTM
        if self.enable_lstm:
            try:
                from src.models.lstm_forecaster import LSTMForecaster

                self.models[self.MODEL_LSTM] = LSTMForecaster(
                    lookback=self.lstm_lookback,
                    units=self.lstm_units,
                    epochs=self.lstm_epochs,
                    horizon=self.horizon,
                )
                self.model_trained[self.MODEL_LSTM] = False
            except Exception as e:
                logger.warning("Could not initialize LSTM: %s", e)
                self.enable_lstm = False

    def _calculate_default_weights(self) -> Dict[str, float]:
        """Calculate default equal weights for enabled models."""
        enabled_models = []
        if self.enable_rf:
            enabled_models.append(self.MODEL_RF)
        if self.enable_gb:
            enabled_models.append(self.MODEL_GB)
        if self.enable_arima_garch:
            enabled_models.append(self.MODEL_AG)
        if self.enable_prophet:
            enabled_models.append(self.MODEL_PROPHET)
        if self.enable_lstm:
            enabled_models.append(self.MODEL_LSTM)

        if not enabled_models:
            return {}

        weight = 1.0 / len(enabled_models)
        return {model: weight for model in enabled_models}

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def _redistribute_weights(self, failed_model: str) -> None:
        """Redistribute weight from failed model to others."""
        if failed_model not in self.weights:
            return

        failed_weight = self.weights.pop(failed_model, 0)
        if not self.weights:
            return

        # Distribute equally to remaining models
        extra_per_model = failed_weight / len(self.weights)
        for model in self.weights:
            self.weights[model] += extra_per_model

        self._normalize_weights()
        logger.info(
            "Redistributed weights after %s failure: %s",
            failed_model,
            {k: f"{v:.2f}" for k, v in self.weights.items()},
        )

    def train(
        self,
        features_df: pd.DataFrame,
        labels_series: pd.Series,
        ohlc_df: pd.DataFrame,
    ) -> "MultiModelEnsemble":
        """
        Train all enabled models.

        Args:
            features_df: Technical indicators DataFrame
            labels_series: Direction labels
            ohlc_df: OHLC DataFrame for statistical models

        Returns:
            self
        """
        logger.info("Training multi-model ensemble (%s)...", self.horizon)

        # Train RF + GB (via base ensemble)
        if self.enable_rf or self.enable_gb:
            try:
                self.base_ensemble.train(features_df, labels_series)
                if self.enable_rf:
                    self.model_trained[self.MODEL_RF] = True
                if self.enable_gb:
                    self.model_trained[self.MODEL_GB] = self.base_ensemble.gb_model.is_trained
                logger.info("RF/GB trained successfully")
            except Exception as e:
                logger.warning("RF/GB training failed: %s", e)
                if self.enable_rf:
                    self._redistribute_weights(self.MODEL_RF)
                if self.enable_gb:
                    self._redistribute_weights(self.MODEL_GB)

        # Train ARIMA-GARCH
        if self.enable_arima_garch and self.MODEL_AG in self.models:
            try:
                self.models[self.MODEL_AG].train(ohlc_df)
                self.model_trained[self.MODEL_AG] = True
                logger.info("ARIMA-GARCH trained successfully")
            except Exception as e:
                logger.warning("ARIMA-GARCH training failed: %s", e)
                self._redistribute_weights(self.MODEL_AG)

        # Train Prophet
        if self.enable_prophet and self.MODEL_PROPHET in self.models:
            try:
                self.models[self.MODEL_PROPHET].train(ohlc_df)
                self.model_trained[self.MODEL_PROPHET] = True
                logger.info("Prophet trained successfully")
            except Exception as e:
                logger.warning("Prophet training failed: %s", e)
                self._redistribute_weights(self.MODEL_PROPHET)

        # Train LSTM
        if self.enable_lstm and self.MODEL_LSTM in self.models:
            try:
                self.models[self.MODEL_LSTM].train(ohlc_df)
                self.model_trained[self.MODEL_LSTM] = True
                logger.info("LSTM trained successfully")
            except Exception as e:
                logger.warning("LSTM training failed: %s", e)
                self._redistribute_weights(self.MODEL_LSTM)

        # Check if at least one model trained
        trained_count = sum(self.model_trained.values())
        if trained_count == 0:
            raise RuntimeError("All models failed to train")

        self.is_trained = True
        self._collect_training_stats()

        logger.info(
            "Ensemble training complete: %d/%d models trained",
            trained_count,
            len(self.model_trained),
        )

        return self

    def _collect_training_stats(self) -> None:
        """Collect training statistics from all models."""
        self.training_stats = {
            "trained_at": datetime.now().isoformat(),
            "models_trained": sum(self.model_trained.values()),
            "models_total": len(self.model_trained),
            "weights": self.weights.copy(),
        }

        if self.model_trained.get(self.MODEL_RF):
            self.training_stats["rf_accuracy"] = self.base_ensemble.training_stats.get(
                "rf_accuracy", 0
            )

        if self.model_trained.get(self.MODEL_GB):
            self.training_stats["gb_accuracy"] = self.base_ensemble.training_stats.get(
                "gb_accuracy", 0
            )

        if self.model_trained.get(self.MODEL_AG):
            ag_model = self.models[self.MODEL_AG]
            self.training_stats["ag_accuracy"] = ag_model.training_stats.get("accuracy", 0)
            self.training_stats["ag_directional"] = ag_model.training_stats.get(
                "directional_accuracy", 0
            )

        if self.model_trained.get(self.MODEL_PROPHET):
            prophet_model = self.models[self.MODEL_PROPHET]
            self.training_stats["prophet_accuracy"] = prophet_model.training_stats.get(
                "accuracy", 0
            )

        if self.model_trained.get(self.MODEL_LSTM):
            lstm_model = self.models[self.MODEL_LSTM]
            self.training_stats["lstm_accuracy"] = lstm_model.training_stats.get("accuracy", 0)
            self.training_stats["lstm_loss"] = lstm_model.training_stats.get("final_loss", 0)

    def predict(
        self,
        features_df: pd.DataFrame,
        ohlc_df: pd.DataFrame,
    ) -> Dict:
        """
        Generate ensemble prediction.

        Args:
            features_df: Technical indicators (1 row)
            ohlc_df: OHLC data for statistical models

        Returns:
            Dict with ensemble prediction and component details
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained.")

        predictions: Dict[str, Dict] = {}
        probabilities: Dict[str, Dict[str, float]] = {}

        # Get RF/GB predictions
        if self.model_trained.get(self.MODEL_RF) or self.model_trained.get(self.MODEL_GB):
            try:
                base_pred = self.base_ensemble.predict(features_df)

                if self.model_trained.get(self.MODEL_RF):
                    predictions[self.MODEL_RF] = {
                        "label": base_pred["rf_prediction"],
                        "confidence": base_pred["rf_confidence"],
                    }
                    # Extract RF probabilities
                    probabilities[self.MODEL_RF] = {
                        "bearish": base_pred["probabilities"].get("bearish", 0)
                        * self.base_ensemble.rf_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                        "neutral": base_pred["probabilities"].get("neutral", 0)
                        * self.base_ensemble.rf_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                        "bullish": base_pred["probabilities"].get("bullish", 0)
                        * self.base_ensemble.rf_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                    }

                if self.model_trained.get(self.MODEL_GB):
                    predictions[self.MODEL_GB] = {
                        "label": base_pred["gb_prediction"],
                        "confidence": base_pred["gb_confidence"],
                    }
                    probabilities[self.MODEL_GB] = {
                        "bearish": base_pred["probabilities"].get("bearish", 0)
                        * self.base_ensemble.gb_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                        "neutral": base_pred["probabilities"].get("neutral", 0)
                        * self.base_ensemble.gb_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                        "bullish": base_pred["probabilities"].get("bullish", 0)
                        * self.base_ensemble.gb_weight
                        / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight),
                    }
            except Exception as e:
                logger.warning("RF/GB prediction failed: %s", e)

        # Get ARIMA-GARCH prediction
        if self.model_trained.get(self.MODEL_AG):
            try:
                ag_pred = self.models[self.MODEL_AG].predict(df=ohlc_df)
                predictions[self.MODEL_AG] = {
                    "label": ag_pred["label"],
                    "confidence": ag_pred["confidence"],
                    "forecast_return": ag_pred.get("forecast_return", 0),
                    "forecast_volatility": ag_pred.get("forecast_volatility", 0),
                }
                probabilities[self.MODEL_AG] = ag_pred["probabilities"]
            except Exception as e:
                logger.warning("ARIMA-GARCH prediction failed: %s", e)

        # Get Prophet prediction
        if self.model_trained.get(self.MODEL_PROPHET):
            try:
                prophet_pred = self.models[self.MODEL_PROPHET].predict(df=ohlc_df)
                predictions[self.MODEL_PROPHET] = {
                    "label": prophet_pred["label"],
                    "confidence": prophet_pred["confidence"],
                    "forecast_return": prophet_pred.get("forecast_return", 0),
                    "trend": prophet_pred.get("trend"),
                }
                probabilities[self.MODEL_PROPHET] = prophet_pred["probabilities"]
            except Exception as e:
                logger.warning("Prophet prediction failed: %s", e)

        # Get LSTM prediction
        if self.model_trained.get(self.MODEL_LSTM):
            try:
                lstm_pred = self.models[self.MODEL_LSTM].predict(df=ohlc_df)
                predictions[self.MODEL_LSTM] = {
                    "label": lstm_pred["label"],
                    "confidence": lstm_pred["confidence"],
                    "forecast_return": lstm_pred.get("forecast_return", 0),
                    "uncertainty": lstm_pred.get("uncertainty", 0),
                }
                probabilities[self.MODEL_LSTM] = lstm_pred["probabilities"]
            except Exception as e:
                logger.warning("LSTM prediction failed: %s", e)

        # Aggregate probabilities
        ensemble_probs = self._aggregate_probabilities(probabilities)

        # Determine final label
        final_label = max(ensemble_probs, key=ensemble_probs.get)
        final_confidence = ensemble_probs[final_label]

        # Calculate agreement score
        agreement = self._calculate_agreement(predictions)

        # Get volatility estimate (prefer ARIMA-GARCH)
        volatility = None
        if self.MODEL_AG in predictions:
            volatility = predictions[self.MODEL_AG].get("forecast_volatility")

        return {
            "label": final_label.capitalize(),
            "confidence": final_confidence,
            "probabilities": ensemble_probs,
            "component_predictions": predictions,
            "agreement": agreement,
            "n_models_used": len(predictions),
            "n_models_total": len(self.model_trained),
            "weights": self.weights.copy(),
            "forecast_volatility": volatility,
        }

    def _aggregate_probabilities(
        self,
        probabilities: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """Aggregate probabilities from all models."""
        ensemble_probs = {"bearish": 0.0, "neutral": 0.0, "bullish": 0.0}

        total_weight = 0.0
        for model, probs in probabilities.items():
            weight = self.weights.get(model, 0)
            total_weight += weight
            for cls in ensemble_probs:
                ensemble_probs[cls] += probs.get(cls, 0) * weight

        # Normalize
        if total_weight > 0:
            ensemble_probs = {k: v / total_weight for k, v in ensemble_probs.items()}

        # Ensure probabilities sum to 1
        total = sum(ensemble_probs.values())
        if total > 0:
            ensemble_probs = {k: v / total for k, v in ensemble_probs.items()}

        return ensemble_probs

    def _calculate_agreement(
        self,
        predictions: Dict[str, Dict],
    ) -> float:
        """Calculate agreement score across models."""
        if not predictions:
            return 0.0

        labels = []
        for model, pred in predictions.items():
            label = pred.get("label", "")
            if isinstance(label, str):
                labels.append(label.lower())

        if not labels:
            return 0.0

        # Agreement = 1 - (unique_labels - 1) / (n_models - 1)
        unique_count = len(set(labels))
        if len(labels) <= 1:
            return 1.0

        return 1.0 - (unique_count - 1) / (len(labels) - 1)

    def generate_forecast(
        self,
        ohlc_df: pd.DataFrame,
        features_df: pd.DataFrame,
        horizon: str = "1D",
    ) -> Dict:
        """
        Generate complete forecast compatible with pipeline.

        Args:
            ohlc_df: DataFrame with OHLC data
            features_df: DataFrame with technical indicators
            horizon: Forecast horizon

        Returns:
            Forecast dict with label, confidence, points, etc.
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained.")

        # Get prediction
        prediction = self.predict(features_df.tail(1), ohlc_df)

        # Generate forecast points
        horizon_days = self._parse_horizon(horizon)
        last_close = ohlc_df["close"].iloc[-1]
        last_ts = pd.to_datetime(ohlc_df["ts"].iloc[-1])

        # Prefer statistical/DL model points if available
        points = None
        if self.model_trained.get(self.MODEL_PROPHET):
            try:
                prophet_model = self.models[self.MODEL_PROPHET]
                prophet_forecast = prophet_model.generate_forecast(ohlc_df, horizon)
                points = prophet_forecast["points"]
            except Exception:
                pass

        if points is None and self.model_trained.get(self.MODEL_AG):
            try:
                ag_forecast = self.models[self.MODEL_AG].generate_forecast(ohlc_df, horizon)
                points = ag_forecast["points"]
            except Exception:
                pass

        if points is None and self.model_trained.get(self.MODEL_LSTM):
            try:
                lstm_forecast = self.models[self.MODEL_LSTM].generate_forecast(ohlc_df, horizon)
                points = lstm_forecast["points"]
            except Exception:
                pass

        if points is None:
            points = self._generate_simple_points(last_ts, last_close, prediction, horizon_days)

        return {
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "raw_confidence": prediction["confidence"],
            "horizon": horizon,
            "points": points,
            "probabilities": prediction["probabilities"],
            "model_type": "MultiModelEnsemble",
            "n_models": prediction["n_models_used"],
            "agreement": prediction["agreement"],
            "forecast_volatility": prediction.get("forecast_volatility"),
            "component_predictions": prediction["component_predictions"],
            "weights": prediction["weights"],
        }

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of trading days."""
        return {"1D": 1, "1W": 5, "2W": 10, "1M": 21, "2M": 42, "3M": 63}.get(horizon, 1)

    def _generate_simple_points(
        self,
        last_ts: datetime,
        last_close: float,
        prediction: Dict,
        horizon_days: int,
    ) -> List[Dict]:
        """Generate simple forecast points."""
        points = []
        direction = (
            1 if prediction["label"] == "Bullish" else -1 if prediction["label"] == "Bearish" else 0
        )
        confidence = prediction["confidence"]

        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            move = direction * 0.01 * confidence * i
            value = last_close * (1 + move)
            volatility = prediction.get("forecast_volatility", 0.02) or 0.02

            points.append(
                {
                    "ts": int(forecast_ts.timestamp()),
                    "value": round(value, 2),
                    "lower": round(value * (1 - 1.96 * volatility * np.sqrt(i)), 2),
                    "upper": round(value * (1 + 1.96 * volatility * np.sqrt(i)), 2),
                }
            )

        return points

    def get_model_diagnostics(self) -> Dict:
        """Get diagnostics for all models."""
        diagnostics = {
            "ensemble": {
                "models_trained": sum(self.model_trained.values()),
                "models_total": len(self.model_trained),
                "weights": self.weights.copy(),
            },
            "models": {},
        }

        if self.model_trained.get(self.MODEL_RF):
            diagnostics["models"]["rf"] = {"status": "trained"}

        if self.model_trained.get(self.MODEL_GB):
            diagnostics["models"]["gb"] = {"status": "trained"}

        if self.model_trained.get(self.MODEL_AG):
            diagnostics["models"]["arima_garch"] = self.models[self.MODEL_AG].get_model_info()

        if self.model_trained.get(self.MODEL_PROPHET):
            diagnostics["models"]["prophet"] = self.models[self.MODEL_PROPHET].get_model_info()

        if self.model_trained.get(self.MODEL_LSTM):
            diagnostics["models"]["lstm"] = self.models[self.MODEL_LSTM].get_model_info()

        diagnostics["training_stats"] = self.training_stats

        return diagnostics


if __name__ == "__main__":
    # Quick test
    print("Testing MultiModelEnsemble...")

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

    # Create features
    df["return_1d"] = df["close"].pct_change()
    df["return_5d"] = df["close"].pct_change(5)
    df["sma_20"] = df["close"].rolling(20).mean()
    df["vol_20"] = df["return_1d"].rolling(20).std()
    df = df.dropna()

    # Labels
    fwd = df["close"].pct_change().shift(-1)
    labels = fwd.apply(
        lambda x: "bullish" if x > 0.02 else "bearish" if x < -0.02 else "neutral"
    ).dropna()
    features = df[["return_1d", "return_5d", "sma_20", "vol_20"]].iloc[:-1]
    labels = labels.iloc[:-1]

    # Initialize and train
    ensemble = MultiModelEnsemble(
        horizon="1D",
        enable_rf=True,
        enable_gb=True,
        enable_arima_garch=True,
        enable_prophet=True,
        enable_lstm=True,
    )

    ensemble.train(features, labels, ohlc_df=df)

    # Generate forecast
    forecast = ensemble.generate_forecast(df, features, horizon="1W")

    print(f"\nForecast: {forecast['label']}")
    print(f"Confidence: {forecast['confidence']:.3f}")
    print(f"Models used: {forecast['n_models']}")
    print(f"Agreement: {forecast['agreement']:.2f}")
    print(f"Weights: {forecast['weights']}")
    print(f"\nDiagnostics: {ensemble.get_model_diagnostics()}")
