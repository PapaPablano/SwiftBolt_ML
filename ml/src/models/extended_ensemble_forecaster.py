"""
Extended Ensemble Forecaster: RF + GB + ARIMA-GARCH
====================================================

Extends the base EnsembleForecaster to include ARIMA-GARCH as a third
model component, providing statistical baseline alongside ML models.

Key Benefits:
- ARIMA-GARCH captures mean-reversion and volatility clustering
- Provides uncertainty quantification via volatility forecasts
- Diversifies ensemble with fundamentally different approach
- Graceful degradation if ARIMA-GARCH fails
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.models.arima_garch_forecaster import ArimaGarchForecaster
from src.models.ensemble_forecaster import EnsembleForecaster

logger = logging.getLogger(__name__)


class ExtendedEnsembleForecaster:
    """
    Extended ensemble combining RF + GB + ARIMA-GARCH.

    Strategy:
    - Train RF, GB (via base ensemble) and ARIMA-GARCH
    - Weight probabilities from all three sources
    - Use ARIMA-GARCH volatility for enhanced uncertainty
    - Fallback to base ensemble if ARIMA-GARCH fails

    Default weights: RF=0.35, GB=0.35, ARIMA-GARCH=0.30
    """

    def __init__(
        self,
        horizon: str = "1D",
        symbol_id: Optional[str] = None,
        rf_weight: Optional[float] = None,
        gb_weight: Optional[float] = None,
        ag_weight: Optional[float] = None,
        use_arima_garch: bool = True,
        arima_order: tuple = (1, 0, 1),
        auto_select_order: bool = False,
    ) -> None:
        """
        Initialize Extended Ensemble Forecaster.

        Args:
            horizon: Forecast horizon ("1D", "1W", etc.)
            symbol_id: Optional symbol ID for weight lookup
            rf_weight: Weight for Random Forest (None = auto)
            gb_weight: Weight for Gradient Boosting (None = auto)
            ag_weight: Weight for ARIMA-GARCH (None = auto)
            use_arima_garch: Whether to include ARIMA-GARCH model
            arima_order: ARIMA(p, d, q) order tuple
            auto_select_order: Auto-select optimal ARIMA order
        """
        self.horizon = horizon
        self.symbol_id = symbol_id
        self.use_arima_garch = use_arima_garch

        # Initialize base ensemble (RF + GB)
        # Pass slightly reduced weights to leave room for ARIMA-GARCH
        base_rf = rf_weight if rf_weight else 0.5
        base_gb = gb_weight if gb_weight else 0.5

        self.base_ensemble = EnsembleForecaster(
            horizon=horizon,
            symbol_id=symbol_id,
            rf_weight=base_rf,
            gb_weight=base_gb,
            use_db_weights=rf_weight is None,
        )

        # Initialize ARIMA-GARCH
        if use_arima_garch:
            self.arima_garch = ArimaGarchForecaster(
                arima_order=arima_order,
                auto_select_order=auto_select_order,
                horizon=horizon,
            )
        else:
            self.arima_garch = None

        # Set ensemble weights
        if use_arima_garch:
            # Default: 35% RF, 35% GB, 30% ARIMA-GARCH
            self.rf_weight = rf_weight if rf_weight else 0.35
            self.gb_weight = gb_weight if gb_weight else 0.35
            self.ag_weight = ag_weight if ag_weight else 0.30
        else:
            # Without ARIMA-GARCH, use base ensemble weights
            self.rf_weight = self.base_ensemble.rf_weight
            self.gb_weight = self.base_ensemble.gb_weight
            self.ag_weight = 0.0

        # Normalize weights
        total = self.rf_weight + self.gb_weight + self.ag_weight
        self.rf_weight /= total
        self.gb_weight /= total
        self.ag_weight /= total

        self.is_trained = False
        self.arima_garch_trained = False
        self.training_stats: Dict = {}

        logger.info(
            "Extended Ensemble initialized: RF=%.2f, GB=%.2f, AG=%.2f",
            self.rf_weight,
            self.gb_weight,
            self.ag_weight,
        )

    def train(
        self,
        features_df: pd.DataFrame,
        labels_series: pd.Series,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> "ExtendedEnsembleForecaster":
        """
        Train all ensemble components.

        Args:
            features_df: Technical indicators DataFrame
            labels_series: Direction labels
            ohlc_df: OHLC DataFrame for ARIMA-GARCH (uses close prices)

        Returns:
            self
        """
        logger.info("Training extended ensemble (%s)...", self.horizon)

        # Train base ensemble (RF + GB)
        self.base_ensemble.train(features_df, labels_series)

        # Train ARIMA-GARCH if enabled and OHLC data provided
        if self.use_arima_garch and self.arima_garch and ohlc_df is not None:
            try:
                self.arima_garch.train(ohlc_df)
                self.arima_garch_trained = True
                logger.info("ARIMA-GARCH trained successfully")
            except Exception as e:
                logger.warning("ARIMA-GARCH training failed: %s. Using RF+GB only.", e)
                self.arima_garch_trained = False
                # Redistribute weight to RF and GB
                self._redistribute_weights()

        self.is_trained = True

        # Collect training stats
        self.training_stats = {
            "rf_accuracy": self.base_ensemble.training_stats.get("rf_accuracy", 0),
            "gb_accuracy": self.base_ensemble.training_stats.get("gb_accuracy", 0),
            "ag_accuracy": (
                self.arima_garch.training_stats.get("accuracy", 0)
                if self.arima_garch_trained
                else None
            ),
            "ag_directional_accuracy": (
                self.arima_garch.training_stats.get("directional_accuracy", 0)
                if self.arima_garch_trained
                else None
            ),
            "weights": {
                "rf": self.rf_weight,
                "gb": self.gb_weight,
                "ag": self.ag_weight,
            },
        }

        return self

    def _redistribute_weights(self) -> None:
        """Redistribute ARIMA-GARCH weight to RF and GB."""
        if self.ag_weight > 0:
            # Split AG weight equally between RF and GB
            extra = self.ag_weight / 2
            self.rf_weight += extra
            self.gb_weight += extra
            self.ag_weight = 0.0
            logger.info(
                "Weights redistributed: RF=%.2f, GB=%.2f",
                self.rf_weight,
                self.gb_weight,
            )

    def predict(
        self,
        features_df: pd.DataFrame,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """
        Predict using extended ensemble.

        Args:
            features_df: Technical indicators (1 row)
            ohlc_df: OHLC data for ARIMA-GARCH prediction

        Returns:
            Dict with ensemble prediction and component details
        """
        if not self.is_trained:
            raise RuntimeError("Extended ensemble not trained.")

        # Get base ensemble prediction
        base_pred = self.base_ensemble.predict(features_df)
        rf_probs = {
            "bearish": base_pred["probabilities"].get("bearish", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.rf_weight,
            "neutral": base_pred["probabilities"].get("neutral", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.rf_weight,
            "bullish": base_pred["probabilities"].get("bullish", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.rf_weight,
        }
        gb_probs = {
            "bearish": base_pred["probabilities"].get("bearish", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.gb_weight,
            "neutral": base_pred["probabilities"].get("neutral", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.gb_weight,
            "bullish": base_pred["probabilities"].get("bullish", 0)
            / (self.base_ensemble.rf_weight + self.base_ensemble.gb_weight)
            * self.base_ensemble.gb_weight,
        }

        # Get ARIMA-GARCH prediction if available
        ag_probs = {"bearish": 0, "neutral": 0, "bullish": 0}
        ag_forecast = None
        forecast_volatility = None

        if self.arima_garch_trained and ohlc_df is not None:
            try:
                ag_pred = self.arima_garch.predict(df=ohlc_df)
                ag_probs = ag_pred["probabilities"]
                ag_forecast = ag_pred.get("forecast_return", 0)
                forecast_volatility = ag_pred.get("forecast_volatility", 0)
            except Exception as e:
                logger.warning("ARIMA-GARCH prediction failed: %s", e)
                ag_probs = {"bearish": 0.33, "neutral": 0.34, "bullish": 0.33}

        # Weighted ensemble probabilities
        ensemble_probs = {
            "bearish": (
                rf_probs["bearish"] * self.rf_weight
                + gb_probs["bearish"] * self.gb_weight
                + ag_probs["bearish"] * self.ag_weight
            ),
            "neutral": (
                rf_probs["neutral"] * self.rf_weight
                + gb_probs["neutral"] * self.gb_weight
                + ag_probs["neutral"] * self.ag_weight
            ),
            "bullish": (
                rf_probs["bullish"] * self.rf_weight
                + gb_probs["bullish"] * self.gb_weight
                + ag_probs["bullish"] * self.ag_weight
            ),
        }

        # Normalize
        total_prob = sum(ensemble_probs.values())
        if total_prob > 0:
            ensemble_probs = {k: v / total_prob for k, v in ensemble_probs.items()}

        # Determine final label
        final_label = max(ensemble_probs, key=ensemble_probs.get)
        final_confidence = ensemble_probs[final_label]

        # Check model agreement
        labels = [
            (
                base_pred["rf_prediction"].lower()
                if isinstance(base_pred["rf_prediction"], str)
                else base_pred["rf_prediction"]
            ),
            (
                base_pred["gb_prediction"].lower()
                if isinstance(base_pred["gb_prediction"], str)
                else base_pred["gb_prediction"]
            ),
        ]
        if self.arima_garch_trained and ag_forecast is not None:
            ag_label = (
                "bullish" if ag_forecast > 0.02 else "bearish" if ag_forecast < -0.02 else "neutral"
            )
            labels.append(ag_label)

        # Agreement score (0-1)
        unique_labels = len(set(labels))
        agreement = 1.0 - (unique_labels - 1) / max(len(labels) - 1, 1)

        return {
            "label": final_label.capitalize(),
            "confidence": final_confidence,
            "probabilities": ensemble_probs,
            "rf_prediction": base_pred["rf_prediction"],
            "gb_prediction": base_pred["gb_prediction"],
            "ag_prediction": ag_label if self.arima_garch_trained else None,
            "rf_confidence": base_pred["rf_confidence"],
            "gb_confidence": base_pred["gb_confidence"],
            "ag_forecast_return": ag_forecast,
            "ag_forecast_volatility": forecast_volatility,
            "agreement": agreement,
            "n_models": 3 if self.arima_garch_trained else 2,
            "weights": {
                "rf": self.rf_weight,
                "gb": self.gb_weight,
                "ag": self.ag_weight,
            },
        }

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
            raise RuntimeError("Extended ensemble not trained.")

        # Get prediction
        prediction = self.predict(features_df.tail(1), ohlc_df)

        # Generate forecast points using ARIMA-GARCH if available
        if self.arima_garch_trained:
            ag_forecast = self.arima_garch.generate_forecast(ohlc_df, horizon)
            points = ag_forecast["points"]
            forecast_volatility = ag_forecast["forecast_volatility"]
        else:
            # Fallback to simple point generation
            horizon_days = {"1D": 1, "1W": 5, "1M": 21}.get(horizon, 1)
            last_close = ohlc_df["close"].iloc[-1]
            last_ts = pd.to_datetime(ohlc_df["ts"].iloc[-1])

            points = []
            from datetime import timedelta

            for i in range(1, horizon_days + 1):
                forecast_ts = last_ts + timedelta(days=i)
                # Simple directional projection
                direction = (
                    1
                    if prediction["label"] == "Bullish"
                    else (-1 if prediction["label"] == "Bearish" else 0)
                )
                move = direction * 0.01 * prediction["confidence"] * i
                value = last_close * (1 + move)

                points.append(
                    {
                        "ts": int(forecast_ts.timestamp()),
                        "value": round(value, 2),
                        "lower": round(value * 0.97, 2),
                        "upper": round(value * 1.03, 2),
                    }
                )

            forecast_volatility = None

        return {
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "raw_confidence": prediction["confidence"],
            "horizon": horizon,
            "points": points,
            "probabilities": prediction["probabilities"],
            "model_type": "Extended-Ensemble",
            "n_models": prediction["n_models"],
            "agreement": prediction["agreement"],
            "forecast_volatility": forecast_volatility,
            "component_predictions": {
                "rf": prediction["rf_prediction"],
                "gb": prediction["gb_prediction"],
                "arima_garch": prediction.get("ag_prediction"),
            },
            "weights": prediction["weights"],
        }

    def get_model_diagnostics(self) -> Dict:
        """Get diagnostics for all models."""
        diagnostics = {
            "base_ensemble": {
                "rf_accuracy": self.training_stats.get("rf_accuracy"),
                "gb_accuracy": self.training_stats.get("gb_accuracy"),
            },
            "weights": {
                "rf": self.rf_weight,
                "gb": self.gb_weight,
                "ag": self.ag_weight,
            },
        }

        if self.arima_garch_trained and self.arima_garch:
            diagnostics["arima_garch"] = self.arima_garch.get_model_info()

        return diagnostics


if __name__ == "__main__":
    # Quick test
    import yfinance as yf

    print("Testing Extended Ensemble Forecaster...")

    # Fetch sample data
    data = yf.download("SPY", start="2023-01-01", end="2024-12-31", progress=False)
    df = data.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close", "date": "ts"})

    # Create simple features for testing
    df["return_1d"] = df["close"].pct_change()
    df["return_5d"] = df["close"].pct_change(5)
    df["sma_20"] = df["close"].rolling(20).mean()
    df["vol_20"] = df["return_1d"].rolling(20).std()
    df = df.dropna()

    # Prepare labels
    forward_return = df["close"].pct_change().shift(-1)
    labels = forward_return.apply(
        lambda x: "bullish" if x > 0.02 else "bearish" if x < -0.02 else "neutral"
    ).dropna()

    features = df[["return_1d", "return_5d", "sma_20", "vol_20"]].iloc[:-1]
    labels = labels.iloc[:-1]

    # Initialize and train
    forecaster = ExtendedEnsembleForecaster(
        horizon="1D",
        use_arima_garch=True,
    )

    forecaster.train(features, labels, ohlc_df=df)

    # Generate forecast
    forecast = forecaster.generate_forecast(df, features, horizon="1W")

    print(f"\nForecast: {forecast['label']} (confidence: {forecast['confidence']:.3f})")
    print(f"Agreement: {forecast['agreement']:.2f}")
    print(f"Weights: {forecast['weights']}")
    print(f"Component predictions: {forecast['component_predictions']}")
    print(f"\nDiagnostics: {forecaster.get_model_diagnostics()}")
