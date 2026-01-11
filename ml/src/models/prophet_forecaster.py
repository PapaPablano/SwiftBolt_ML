"""
Prophet Forecaster: Seasonality and trend decomposition for price forecasting.
===============================================================================

Uses Facebook Prophet for capturing:
- Weekly seasonality (day-of-week effects)
- Trend changes with automatic changepoint detection
- Holiday effects (optional)

Key Features:
- Automatic seasonality detection
- Robust to missing data and outliers
- Provides uncertainty intervals natively
- Compatible with existing ensemble framework

Note: Requires 'prophet' package. Install with:
    pip install prophet
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import Prophet
try:
    from prophet import Prophet

    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not installed. Install with: pip install prophet")


class ProphetForecaster:
    """
    Prophet-based forecaster for price prediction.

    Uses Facebook Prophet's additive model for:
    - Trend estimation with changepoints
    - Weekly seasonality
    - Uncertainty quantification

    Outputs 3-class predictions (bullish/neutral/bearish) compatible with
    the existing ensemble framework.

    Attributes:
        weekly_seasonality: Enable weekly seasonality
        yearly_seasonality: Enable yearly seasonality
        daily_seasonality: Enable daily seasonality
        changepoint_prior_scale: Flexibility of trend changes (0.001-0.5)
        seasonality_prior_scale: Strength of seasonality (0.01-10)
        interval_width: Width of uncertainty interval (0.8-0.99)
    """

    def __init__(
        self,
        weekly_seasonality: bool = True,
        yearly_seasonality: bool = False,
        daily_seasonality: bool = False,
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
        interval_width: float = 0.95,
        bullish_threshold: float = 0.02,
        bearish_threshold: float = -0.02,
        horizon: str = "1D",
        growth: str = "linear",
    ) -> None:
        """
        Initialize the Prophet forecaster.

        Args:
            weekly_seasonality: Enable weekly seasonality
            yearly_seasonality: Enable yearly seasonality
            daily_seasonality: Enable daily seasonality
            changepoint_prior_scale: Flexibility of trend (higher = more flexible)
            seasonality_prior_scale: Strength of seasonality
            interval_width: Confidence interval width (0.95 = 95%)
            bullish_threshold: Return above this = bullish
            bearish_threshold: Return below this = bearish
            horizon: Forecast horizon ("1D", "1W", etc.)
            growth: Growth model ("linear" or "logistic")
        """
        if not PROPHET_AVAILABLE:
            logger.warning("Prophet not available. Forecaster will use fallback mode.")

        self.weekly_seasonality = weekly_seasonality
        self.yearly_seasonality = yearly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_prior_scale = seasonality_prior_scale
        self.interval_width = interval_width
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.horizon = horizon
        self.growth = growth

        self.model = None
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
        self.diagnostics: Dict[str, Any] = {}

        # Store last training data for diagnostics
        self._last_train_df: Optional[pd.DataFrame] = None

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of trading days."""
        horizon_map = {
            "1D": 1,
            "1W": 5,
            "2W": 10,
            "1M": 21,
            "2M": 42,
            "3M": 63,
        }
        return horizon_map.get(horizon, 1)

    def _prepare_prophet_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare DataFrame in Prophet's required format.

        Args:
            df: DataFrame with 'ts' and 'close' columns

        Returns:
            DataFrame with 'ds' (datetime) and 'y' (target) columns
        """
        prophet_df = pd.DataFrame()
        prophet_df["ds"] = pd.to_datetime(df["ts"])
        prophet_df["y"] = df["close"].values
        return prophet_df

    def train(
        self,
        df: pd.DataFrame,
        min_samples: int = 100,
    ) -> "ProphetForecaster":
        """
        Train Prophet model on price data.

        Args:
            df: DataFrame with 'ts' and 'close' columns
            min_samples: Minimum samples required for training

        Returns:
            self
        """
        if not PROPHET_AVAILABLE:
            logger.warning("Prophet not available. Using fallback training.")
            return self._fallback_train(df, min_samples)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        if "ts" not in df.columns:
            raise ValueError("DataFrame must contain 'ts' column")

        if len(df) < min_samples:
            raise ValueError(f"Insufficient data: {len(df)} < {min_samples}")

        # Prepare data for Prophet
        prophet_df = self._prepare_prophet_df(df)
        self._last_train_df = prophet_df.copy()

        logger.info("Training Prophet model...")

        try:
            # Suppress Prophet's verbose output
            import logging as py_logging

            py_logging.getLogger("cmdstanpy").setLevel(py_logging.WARNING)
            py_logging.getLogger("prophet").setLevel(py_logging.WARNING)

            # Initialize Prophet model
            self.model = Prophet(
                growth=self.growth,
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_prior_scale=self.seasonality_prior_scale,
                interval_width=self.interval_width,
                uncertainty_samples=1000,
            )

            # Fit the model
            self.model.fit(prophet_df)

            # Calculate training metrics
            self._calculate_training_metrics(prophet_df)

            self.is_trained = True
            self.training_stats["trained_at"] = datetime.now().isoformat()
            self.training_stats["n_samples"] = len(df)

            logger.info("Prophet model trained successfully")

        except Exception as e:
            logger.error("Prophet training failed: %s", e)
            raise

        return self

    def _fallback_train(
        self,
        df: pd.DataFrame,
        min_samples: int,
    ) -> "ProphetForecaster":
        """Fallback training when Prophet is not available."""
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        if "ts" not in df.columns:
            raise ValueError("DataFrame must contain 'ts' column")

        if len(df) < min_samples:
            raise ValueError(f"Insufficient data: {len(df)} < {min_samples}")

        # Store basic statistics for fallback predictions
        returns = df["close"].pct_change().dropna()
        self.training_stats = {
            "trained_at": datetime.now().isoformat(),
            "n_samples": len(df),
            "mean_return": float(returns.mean()),
            "std_return": float(returns.std()),
            "last_close": float(df["close"].iloc[-1]),
            "fallback_mode": True,
        }
        self.is_trained = True
        logger.info("Prophet fallback training complete")
        return self

    def _calculate_training_metrics(self, prophet_df: pd.DataFrame) -> None:
        """Calculate in-sample training metrics."""
        if self.model is None:
            return

        # Get in-sample predictions
        fitted = self.model.predict(prophet_df)

        # Calculate residuals
        residuals = prophet_df["y"].values - fitted["yhat"].values
        returns = prophet_df["y"].pct_change().dropna()
        predicted_returns = fitted["yhat"].pct_change().dropna()

        # Classification accuracy
        if len(returns) > 1 and len(predicted_returns) > 1:
            actual_labels = self._classify_returns(returns)
            pred_labels = self._classify_returns(predicted_returns)
            accuracy = (actual_labels == pred_labels).mean()
        else:
            accuracy = 0.0

        # Directional accuracy
        actual_direction = np.sign(returns)
        pred_direction = np.sign(predicted_returns)
        if len(actual_direction) > 0:
            directional_accuracy = (actual_direction == pred_direction).mean()
        else:
            directional_accuracy = 0.0

        self.training_stats["accuracy"] = float(accuracy)
        self.training_stats["directional_accuracy"] = float(directional_accuracy)
        self.training_stats["mape"] = float(np.abs(residuals / prophet_df["y"].values).mean())
        self.training_stats["rmse"] = float(np.sqrt((residuals**2).mean()))

        # Extract changepoints info
        if hasattr(self.model, "changepoints"):
            self.diagnostics["n_changepoints"] = len(self.model.changepoints)
            self.diagnostics["changepoint_dates"] = [str(cp) for cp in self.model.changepoints[:5]]

        logger.info(
            "Training accuracy: %.3f, directional: %.3f",
            accuracy,
            directional_accuracy,
        )

    def _classify_returns(self, returns: pd.Series) -> pd.Series:
        """Classify returns into bullish/neutral/bearish."""
        labels = pd.Series(index=returns.index, dtype=str)
        labels[returns > self.bullish_threshold] = "bullish"
        labels[returns < self.bearish_threshold] = "bearish"
        labels[(returns >= self.bearish_threshold) & (returns <= self.bullish_threshold)] = (
            "neutral"
        )
        return labels

    def predict(
        self,
        df: Optional[pd.DataFrame] = None,
        steps: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate forecast with classification and confidence.

        Args:
            df: Optional new data to use for forecasting
            steps: Number of steps ahead to forecast

        Returns:
            Dict with label, confidence, probabilities, and forecast details
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        if not PROPHET_AVAILABLE or self.model is None:
            return self._fallback_predict(df, steps)

        try:
            # Create future dataframe
            if df is not None:
                prophet_df = self._prepare_prophet_df(df)
                # Refit model on new data for better predictions
                self.model.fit(prophet_df)
            else:
                prophet_df = self._last_train_df

            if prophet_df is None:
                return self._null_prediction("No training data available")

            future = self.model.make_future_dataframe(periods=steps)
            forecast = self.model.predict(future)

            # Get the forecasted values
            last_actual = prophet_df["y"].iloc[-1]
            forecast_value = forecast["yhat"].iloc[-1]
            forecast_lower = forecast["yhat_lower"].iloc[-1]
            forecast_upper = forecast["yhat_upper"].iloc[-1]

            # Calculate expected return
            forecast_return = (forecast_value - last_actual) / last_actual

            # Calculate volatility from prediction interval
            forecast_volatility = (forecast_upper - forecast_lower) / (2 * 1.96 * last_actual)

            # Classify the forecast
            if forecast_return > self.bullish_threshold:
                label = "Bullish"
            elif forecast_return < self.bearish_threshold:
                label = "Bearish"
            else:
                label = "Neutral"

            # Calculate probabilities using forecast uncertainty
            probabilities = self._calculate_probabilities(
                forecast_return,
                forecast_volatility,
            )

            confidence = float(probabilities[label.lower()])

            return {
                "label": label,
                "confidence": confidence,
                "probabilities": probabilities,
                "forecast_value": float(forecast_value),
                "forecast_return": float(forecast_return),
                "forecast_volatility": float(forecast_volatility),
                "ci_lower": float(forecast_lower),
                "ci_upper": float(forecast_upper),
                "trend": float(forecast["trend"].iloc[-1]),
                "seasonality": {
                    "weekly": float(forecast.get("weekly", pd.Series([0])).iloc[-1]),
                },
                "diagnostics": self.diagnostics,
            }

        except Exception as e:
            logger.error("Prophet prediction failed: %s", e)
            return self._null_prediction(str(e))

    def _fallback_predict(
        self,
        df: Optional[pd.DataFrame],
        steps: int,
    ) -> Dict[str, Any]:
        """Fallback prediction when Prophet is not available."""
        stats = self.training_stats

        # Use stored statistics for naive prediction
        mean_return = stats.get("mean_return", 0.0)
        std_return = stats.get("std_return", 0.02)

        # Simple random walk prediction
        forecast_return = mean_return * steps
        forecast_volatility = std_return * np.sqrt(steps)

        if forecast_return > self.bullish_threshold:
            label = "Bullish"
        elif forecast_return < self.bearish_threshold:
            label = "Bearish"
        else:
            label = "Neutral"

        probabilities = self._calculate_probabilities(
            forecast_return,
            forecast_volatility,
        )

        return {
            "label": label,
            "confidence": float(probabilities[label.lower()]),
            "probabilities": probabilities,
            "forecast_return": float(forecast_return),
            "forecast_volatility": float(forecast_volatility),
            "fallback_mode": True,
        }

    def _calculate_probabilities(
        self,
        forecast_mean: float,
        forecast_std: float,
    ) -> Dict[str, float]:
        """Calculate class probabilities using normal distribution."""
        from scipy import stats as scipy_stats

        if forecast_std <= 0:
            forecast_std = 0.01

        prob_bearish = scipy_stats.norm.cdf(
            self.bearish_threshold,
            loc=forecast_mean,
            scale=forecast_std,
        )
        prob_bullish = 1 - scipy_stats.norm.cdf(
            self.bullish_threshold,
            loc=forecast_mean,
            scale=forecast_std,
        )
        prob_neutral = 1 - prob_bearish - prob_bullish

        # Ensure valid probabilities
        total = prob_bearish + prob_neutral + prob_bullish
        if total > 0:
            prob_bearish /= total
            prob_neutral /= total
            prob_bullish /= total
        else:
            prob_bearish = prob_neutral = prob_bullish = 1 / 3

        return {
            "bearish": float(prob_bearish),
            "neutral": float(prob_neutral),
            "bullish": float(prob_bullish),
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

        # Train/refit on provided data
        if not self.is_trained:
            self.train(df)

        # Get prediction
        prediction = self.predict(df=df, steps=horizon_days)

        # Generate forecast points
        last_close = df["close"].iloc[-1]
        last_ts = pd.to_datetime(df["ts"].iloc[-1])

        if PROPHET_AVAILABLE and self.model is not None:
            points = self._generate_prophet_points(df, last_ts, last_close, horizon_days)
        else:
            points = self._generate_fallback_points(
                last_ts,
                last_close,
                prediction["forecast_return"],
                prediction["forecast_volatility"],
                horizon_days,
            )

        return {
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "raw_confidence": prediction["confidence"],
            "horizon": horizon,
            "points": points,
            "probabilities": prediction["probabilities"],
            "model_type": "Prophet",
            "forecast_return": prediction.get("forecast_return", 0),
            "forecast_volatility": prediction.get("forecast_volatility", 0),
            "trend": prediction.get("trend"),
            "seasonality": prediction.get("seasonality"),
            "diagnostics": self.diagnostics,
            "fallback_mode": prediction.get("fallback_mode", False),
        }

    def _generate_prophet_points(
        self,
        df: pd.DataFrame,
        last_ts: datetime,
        last_close: float,
        horizon_days: int,
    ) -> List[Dict[str, Any]]:
        """Generate forecast points using Prophet predictions."""
        prophet_df = self._prepare_prophet_df(df)
        future = self.model.make_future_dataframe(periods=horizon_days)
        forecast = self.model.predict(future)

        points = []
        for i in range(1, horizon_days + 1):
            idx = len(prophet_df) - 1 + i
            if idx < len(forecast):
                row = forecast.iloc[idx]
                points.append(
                    {
                        "ts": int(row["ds"].timestamp()),
                        "value": round(float(row["yhat"]), 2),
                        "lower": round(float(row["yhat_lower"]), 2),
                        "upper": round(float(row["yhat_upper"]), 2),
                    }
                )
            else:
                # Extrapolate if needed
                forecast_ts = last_ts + timedelta(days=i)
                points.append(
                    {
                        "ts": int(forecast_ts.timestamp()),
                        "value": round(float(last_close), 2),
                        "lower": round(float(last_close * 0.95), 2),
                        "upper": round(float(last_close * 1.05), 2),
                    }
                )

        return points

    def _generate_fallback_points(
        self,
        last_ts: datetime,
        last_close: float,
        forecast_return: float,
        forecast_volatility: float,
        horizon_days: int,
    ) -> List[Dict[str, Any]]:
        """Generate forecast points without Prophet."""
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
            "name": "Prophet",
            "is_trained": self.is_trained,
            "prophet_available": PROPHET_AVAILABLE,
            "config": {
                "weekly_seasonality": self.weekly_seasonality,
                "yearly_seasonality": self.yearly_seasonality,
                "daily_seasonality": self.daily_seasonality,
                "changepoint_prior_scale": self.changepoint_prior_scale,
                "seasonality_prior_scale": self.seasonality_prior_scale,
                "interval_width": self.interval_width,
                "growth": self.growth,
            },
            "thresholds": {
                "bullish": self.bullish_threshold,
                "bearish": self.bearish_threshold,
            },
            "training_stats": self.training_stats,
            "diagnostics": self.diagnostics,
        }

        if self.model is not None and hasattr(self.model, "params"):
            info["model_params"] = {
                "k": float(self.model.params.get("k", 0)),
                "m": float(self.model.params.get("m", 0)),
            }

        return info


# Convenience function to check if Prophet is available
def is_prophet_available() -> bool:
    """Check if Prophet package is installed."""
    return PROPHET_AVAILABLE


if __name__ == "__main__":
    # Quick test
    print(f"Prophet available: {PROPHET_AVAILABLE}")

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

    print("\nTesting Prophet Forecaster...")

    forecaster = ProphetForecaster(
        weekly_seasonality=True,
        yearly_seasonality=False,
    )

    forecaster.train(df)
    forecast = forecaster.generate_forecast(df, horizon="1W")

    print(f"Label: {forecast['label']}")
    print(f"Confidence: {forecast['confidence']:.3f}")
    print(f"Fallback mode: {forecast.get('fallback_mode', False)}")
    print(f"Points: {len(forecast['points'])}")
    print(f"\nModel info: {forecaster.get_model_info()}")
