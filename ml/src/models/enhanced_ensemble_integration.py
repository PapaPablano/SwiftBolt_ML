"""
Enhanced Ensemble Integration
=============================

Bridges the new 5-model ensemble architecture with the production
forecast pipeline. Provides backward-compatible interface while
enabling advanced features:

- 5 models: RF, GB, ARIMA-GARCH, Prophet, LSTM
- Dynamic weight optimization
- Uncertainty quantification
- Performance monitoring
- Options integration

Usage:
    from src.models.enhanced_ensemble_integration import (
        EnhancedEnsembleForecaster,
        get_production_ensemble,
    )

    # Create production ensemble
    ensemble = get_production_ensemble(
        horizon="1D",
        symbol_id="AAPL",
        enable_advanced_models=True,
    )

    # Train and predict (same interface as EnsembleForecaster)
    ensemble.train(features_df, labels)
    result = ensemble.predict(features_df.tail(1))
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.models.performance_monitor import PerformanceMonitor

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


class EnhancedEnsembleForecaster:
    """
    Enhanced ensemble forecaster with 6-model support.

    Wraps the new EnsembleManager and provides backward-compatible
    interface with the existing EnsembleForecaster used in forecast_job.py.

    Supports:
    - RF, GB (ML models)
    - ARIMA-GARCH, Prophet (Statistical models)
    - LSTM, Transformer (Deep Learning models)
    """

    def __init__(
        self,
        horizon: str = "1D",
        symbol_id: Optional[str] = None,
        enable_arima_garch: bool = True,
        enable_prophet: bool = True,
        enable_lstm: bool = False,
        enable_transformer: bool = False,
        confidence_level: float = 0.95,
        optimization_method: str = "ridge",
        enable_monitoring: bool = True,
    ) -> None:
        """
        Initialize Enhanced Ensemble Forecaster.

        Args:
            horizon: Forecast horizon ("1D" or "1W")
            symbol_id: Optional symbol ID for per-symbol weights
            enable_arima_garch: Enable ARIMA-GARCH model
            enable_prophet: Enable Prophet model
            enable_lstm: Enable LSTM model (slower)
            enable_transformer: Enable Transformer model (multi-timeframe attention)
            confidence_level: Confidence level for intervals
            optimization_method: Weight optimization method
            enable_monitoring: Enable performance monitoring
        """
        self.horizon = horizon
        self.symbol_id = symbol_id

        # Model flags
        self.enable_arima_garch = enable_arima_garch
        self.enable_prophet = enable_prophet
        self.enable_lstm = enable_lstm
        self.enable_transformer = enable_transformer

        # Import and initialize components
        from src.models.ensemble_manager import EnsembleManager
        from src.models.performance_monitor import PerformanceMonitor

        self.ensemble_manager = EnsembleManager(
            horizon=horizon,
            enable_rf=True,
            enable_gb=True,
            enable_arima_garch=enable_arima_garch,
            enable_prophet=enable_prophet,
            enable_lstm=enable_lstm,
            enable_transformer=enable_transformer,
            confidence_level=confidence_level,
            optimization_method=optimization_method,
        )

        # Performance monitoring
        self.monitor = PerformanceMonitor() if enable_monitoring else None

        # State
        self.is_trained = False
        self.training_stats: Dict = {}
        self.rf_weight: Optional[float] = None
        self.gb_weight: Optional[float] = None

        # Track model count
        self.n_models = sum(
            [
                True,  # RF always enabled
                True,  # GB always enabled
                enable_arima_garch,
                enable_prophet,
                enable_lstm,
                enable_transformer,
            ]
        )

        logger.info(
            "EnhancedEnsembleForecaster initialized: " "horizon=%s, n_models=%d, monitoring=%s",
            horizon,
            self.n_models,
            "enabled" if enable_monitoring else "disabled",
        )

    def train(
        self,
        features_df: pd.DataFrame,
        labels_series: pd.Series,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> "EnhancedEnsembleForecaster":
        """
        Train ensemble on data.

        Args:
            features_df: Technical indicators DataFrame
            labels_series: Direction labels
            ohlc_df: Optional OHLC data for time-series models

        Returns:
            self
        """
        logger.info("Training enhanced ensemble (%s)...", self.horizon)
        start_time = datetime.now()

        # Prepare OHLC if not provided (create from features)
        if ohlc_df is None:
            ohlc_df = self._create_ohlc_from_features(features_df)

        # Train ensemble manager
        train_status = self.ensemble_manager.train(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels_series,
        )

        # Extract weights for backward compatibility
        weights = self.ensemble_manager.ensemble.weights
        self.rf_weight = weights.get("rf", 0.5)
        self.gb_weight = weights.get("gb", 0.5)

        # Collect training stats
        training_time = (datetime.now() - start_time).total_seconds()
        self.training_stats = {
            "training_time_seconds": training_time,
            "n_samples": len(features_df),
            "n_features": len(features_df.columns),
            "models_trained": train_status,
            "n_models_active": sum(train_status.values()),
            "weights": weights,
            "rf_weight": self.rf_weight,
            "gb_weight": self.gb_weight,
        }

        # Add per-model stats
        diagnostics = self.ensemble_manager.get_diagnostics()
        models_diag = diagnostics.get("models", {})
        for model, diag in models_diag.items():
            if isinstance(diag, dict) and "accuracy" in diag:
                self.training_stats[f"{model}_accuracy"] = diag["accuracy"]

        self.is_trained = True

        # Log summary
        trained_models = [m for m, s in train_status.items() if s]
        logger.info(
            "Enhanced ensemble trained: %d models in %.1fs",
            len(trained_models),
            training_time,
        )
        logger.info("  Models: %s", trained_models)
        logger.info("  Weights: %s", weights)

        return self

    def predict(
        self,
        features_df: pd.DataFrame,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Generate ensemble prediction.

        Args:
            features_df: Technical indicators (typically 1 row)
            ohlc_df: Optional OHLC data

        Returns:
            Dict with prediction, confidence, probabilities, etc.
        """
        if not self.is_trained:
            raise RuntimeError("Ensemble not trained.")

        # Prepare OHLC if not provided
        if ohlc_df is None:
            ohlc_df = self._create_ohlc_from_features(features_df)

        # Generate forecast using EnsembleManager
        forecast_result = self.ensemble_manager.predict(
            ohlc_df=ohlc_df,
            features_df=features_df,
        )

        # Convert to backward-compatible format
        result = {
            "label": forecast_result.label,
            "confidence": forecast_result.confidence,
            "probabilities": forecast_result.probabilities,
            "agreement": forecast_result.agreement,
            "n_models": forecast_result.n_models,
            # Backward compatibility fields
            "rf_prediction": self._extract_model_prediction("rf"),
            "gb_prediction": self._extract_model_prediction("gb"),
            "rf_confidence": forecast_result.confidence,
            "gb_confidence": forecast_result.confidence,
            # Enhanced fields
            "weights": forecast_result.weights,
            "forecast_return": forecast_result.forecast_return,
            "forecast_volatility": forecast_result.forecast_volatility,
            "ci_lower": forecast_result.ci_lower,
            "ci_upper": forecast_result.ci_upper,
            "component_predictions": forecast_result.component_predictions,
        }

        # Record in monitor if enabled
        if self.monitor and hasattr(self, "_last_actual"):
            self.monitor.record_prediction(
                prediction=result["label"],
                actual=self._last_actual,
                confidence=result["confidence"],
                agreement=result["agreement"],
                probabilities=result["probabilities"],
                weights=self.ensemble_manager.get_current_weights(),
                model_predictions=result.get("model_predictions", {}),
            )

        return result

    def predict_batch(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Batch prediction for multiple rows.

        Args:
            features_df: Technical indicators (multiple rows)

        Returns:
            DataFrame with ensemble predictions
        """
        results = []
        for i in range(len(features_df)):
            row = features_df.iloc[[i]]
            pred = self.predict(row)
            results.append(
                {
                    "ensemble_label": pred["label"],
                    "ensemble_confidence": pred["confidence"],
                    "rf_label": pred.get("rf_prediction", pred["label"]),
                    "gb_label": pred.get("gb_prediction", pred["label"]),
                    "agreement": pred["agreement"],
                }
            )

        return pd.DataFrame(results)

    def optimize_weights(
        self,
        features_df: pd.DataFrame,
        labels: pd.Series,
        ohlc_df: Optional[pd.DataFrame] = None,
        method: str = "ridge",
    ) -> Dict[str, float]:
        """
        Optimize model weights based on validation data.

        Args:
            features_df: Validation features
            labels: Validation labels
            ohlc_df: Optional OHLC data
            method: Optimization method

        Returns:
            Optimized weights
        """
        if ohlc_df is None:
            ohlc_df = self._create_ohlc_from_features(features_df)

        weights = self.ensemble_manager.optimize_weights(
            ohlc_df=ohlc_df,
            features_df=features_df,
            labels=labels,
            method=method,
        )

        # Update local state
        self.rf_weight = weights.get("rf", 0.5)
        self.gb_weight = weights.get("gb", 0.5)

        return weights

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get performance monitoring summary."""
        if not self.monitor:
            return {"monitoring_enabled": False}

        return self.monitor.get_dashboard_summary()

    def get_model_diagnostics(self) -> Dict[str, Dict]:
        """Get diagnostics for all models."""
        diagnostics = self.ensemble_manager.get_diagnostics()
        return diagnostics.get("models", {})

    def get_forecast_signal(
        self,
        forecast: Dict,
        ohlc_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Convert forecast to options-compatible signal.

        Args:
            forecast: Forecast result from predict()
            ohlc_df: Optional OHLC data

        Returns:
            Signal dict compatible with EnhancedOptionsRanker
        """
        try:
            from src.models.forecast_options_integration import (
                ForecastOptionsIntegration,
            )

            integration = ForecastOptionsIntegration()
            signal = integration.convert_forecast_to_signal(forecast, ohlc_df)

            return integration.create_trend_analysis_dict(signal)

        except ImportError:
            logger.warning("ForecastOptionsIntegration not available")
            return {}

    def _extract_model_prediction(self, model_name: str) -> str:
        """Extract individual model prediction."""
        if not hasattr(self.ensemble_manager, "ensemble"):
            return "Unknown"

        ensemble = self.ensemble_manager.ensemble
        if hasattr(ensemble, "last_predictions"):
            preds = ensemble.last_predictions or {}
            pred = preds.get(model_name, {})
            if isinstance(pred, dict):
                return pred.get("label", "Unknown")
        return "Unknown"

    def _create_ohlc_from_features(
        self,
        features_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Create minimal OHLC DataFrame from features."""
        n = len(features_df)

        # Try to extract price columns if they exist
        if "close" in features_df.columns:
            close = features_df["close"].values
        else:
            close = np.ones(n) * 100  # Default

        if "ts" in features_df.columns:
            ts = features_df["ts"]
        else:
            ts = pd.date_range(end=datetime.now(), periods=n, freq="D")

        return pd.DataFrame(
            {
                "ts": ts,
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.ones(n) * 1e6,
            }
        )


def get_production_ensemble(
    horizon: str = "1D",
    symbol_id: Optional[str] = None,
    enable_advanced_models: Optional[bool] = None,
) -> EnhancedEnsembleForecaster:
    """
    Factory function to create production ensemble with env-based config.

    Reads environment variables:
    - ENABLE_ADVANCED_ENSEMBLE: Enable 6-model ensemble (default: True)
    - ENABLE_ARIMA_GARCH: Enable ARIMA-GARCH (default: True)
    - ENABLE_PROPHET: Enable Prophet (default: True)
    - ENABLE_LSTM: Enable LSTM (default: False, slower)
    - ENABLE_TRANSFORMER: Enable Transformer (default: False, multi-timeframe attention)
    - ENSEMBLE_OPTIMIZATION_METHOD: Weight optimization method (default: ridge)

    Args:
        horizon: Forecast horizon
        symbol_id: Optional symbol ID
        enable_advanced_models: Override for advanced models (None = use env)

    Returns:
        Configured EnhancedEnsembleForecaster
    """
    # Check if advanced ensemble is enabled
    if enable_advanced_models is None:
        enable_advanced = _bool_env("ENABLE_ADVANCED_ENSEMBLE", default=True)
    else:
        enable_advanced = enable_advanced_models

    if not enable_advanced:
        # Return basic ensemble (RF + GB only)
        return EnhancedEnsembleForecaster(
            horizon=horizon,
            symbol_id=symbol_id,
            enable_arima_garch=False,
            enable_prophet=False,
            enable_lstm=False,
            enable_transformer=False,
            enable_monitoring=False,
        )

    # Configure advanced ensemble from environment
    return EnhancedEnsembleForecaster(
        horizon=horizon,
        symbol_id=symbol_id,
        enable_arima_garch=_bool_env("ENABLE_ARIMA_GARCH", default=True),
        enable_prophet=_bool_env("ENABLE_PROPHET", default=True),
        enable_lstm=_bool_env("ENABLE_LSTM", default=False),
        enable_transformer=_bool_env("ENABLE_TRANSFORMER", default=False),
        optimization_method=os.getenv("ENSEMBLE_OPTIMIZATION_METHOD", "ridge"),
        enable_monitoring=_bool_env("ENABLE_MONITORING", default=True),
    )


# Global performance monitor instance (singleton)
_global_monitor: Optional["PerformanceMonitor"] = None


def get_global_monitor() -> "PerformanceMonitor":
    """Get or create global performance monitor."""
    global _global_monitor

    if _global_monitor is None:
        from src.models.performance_monitor import PerformanceMonitor

        _global_monitor = PerformanceMonitor()

    return _global_monitor


def record_forecast_outcome(
    symbol: str,
    horizon: str,
    prediction: str,
    actual: str,
    confidence: float,
    agreement: float,
    probabilities: Dict[str, float],
    weights: Dict[str, float],
    model_predictions: Dict[str, str],
) -> None:
    """
    Record forecast outcome for monitoring.

    Called by evaluation_job.py when actual outcomes are known.
    """
    monitor = get_global_monitor()
    monitor.record_prediction(
        prediction=prediction,
        actual=actual,
        confidence=confidence,
        agreement=agreement,
        probabilities=probabilities,
        weights=weights,
        model_predictions=model_predictions,
    )


def export_monitoring_metrics() -> Dict[str, Any]:
    """Export current monitoring metrics for dashboard."""
    monitor = get_global_monitor()
    return monitor.get_dashboard_summary()


if __name__ == "__main__":
    # Quick test
    print("Testing EnhancedEnsembleForecaster...")

    # Create sample data
    np.random.seed(42)
    n = 200

    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    ohlc_df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": prices * 0.998,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.randint(1e6, 1e7, n).astype(float),
        }
    )

    # Create features (simplified)
    features_df = pd.DataFrame(
        {
            "ts": ohlc_df["ts"],
            "close": ohlc_df["close"],
            "return_1d": ohlc_df["close"].pct_change(),
            "return_5d": ohlc_df["close"].pct_change(5),
            "sma_20": ohlc_df["close"].rolling(20).mean(),
            "vol_20": ohlc_df["close"].pct_change().rolling(20).std(),
        }
    ).dropna()

    # Create labels
    fwd_return = ohlc_df["close"].pct_change().shift(-1)
    labels = fwd_return.apply(
        lambda x: "bullish" if x > 0.01 else "bearish" if x < -0.01 else "neutral"
    ).iloc[:-1]

    # Align data
    features_df = features_df.iloc[:-1]
    ohlc_df = ohlc_df.iloc[:-1]
    labels = labels.loc[features_df.index]

    # Test with minimal models for speed
    ensemble = EnhancedEnsembleForecaster(
        horizon="1D",
        enable_arima_garch=False,
        enable_prophet=False,
        enable_lstm=False,
        enable_monitoring=True,
    )

    # Train
    ensemble.train(features_df, labels, ohlc_df)
    print(f"\nTraining stats: {ensemble.training_stats}")

    # Predict
    result = ensemble.predict(features_df.tail(1), ohlc_df.tail(1))
    print(f"\nPrediction: {result['label']} ({result['confidence']:.1%})")
    print(f"Agreement: {result['agreement']:.1%}")
    print(f"Probabilities: {result['probabilities']}")

    # Check monitoring
    summary = ensemble.get_monitoring_summary()
    print(f"\nMonitoring: {summary.get('n_predictions', 0)} predictions")

    print("\n\nSUCCESS: EnhancedEnsembleForecaster working!")
