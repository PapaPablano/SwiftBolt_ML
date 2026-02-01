"""
ARIMA-GARCH Forecaster: Statistical baseline for price movement prediction.
============================================================================

Combines ARIMA for mean forecasting with GARCH for volatility estimation.
Provides a complementary statistical approach to the ML-based forecasters.

Key Features:
- ARIMA(p,d,q) for capturing autocorrelation and trends
- GARCH(1,1) for volatility clustering and conditional variance
- Automatic order selection via AIC/BIC
- Diagnostic tests (Ljung-Box) for residual validation
- Compatible with existing ensemble framework
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA

from src.features.volatility_regime import GarchVolatility

logger = logging.getLogger(__name__)


class ArimaGarchForecaster:
    """
    ARIMA-GARCH model for price return forecasting.

    Uses ARIMA for mean prediction and GARCH for volatility estimation.
    Outputs 3-class predictions (bullish/neutral/bearish) compatible with
    the existing ensemble framework.

    Attributes:
        arima_order: Tuple of (p, d, q) for ARIMA model
        garch_p: GARCH p parameter (default 1)
        garch_q: GARCH q parameter (default 1)
        bullish_threshold: Return threshold for bullish classification
        bearish_threshold: Return threshold for bearish classification
    """

    def __init__(
        self,
        arima_order: Tuple[int, int, int] = (1, 0, 1),
        garch_p: int = 1,
        garch_q: int = 1,
        bullish_threshold: float = 0.02,
        bearish_threshold: float = -0.02,
        auto_select_order: bool = False,
        horizon: str = "1D",
    ) -> None:
        """
        Initialize the ARIMA-GARCH forecaster.

        Args:
            arima_order: ARIMA(p, d, q) order tuple
            garch_p: GARCH p parameter
            garch_q: GARCH q parameter
            bullish_threshold: Return above this = bullish
            bearish_threshold: Return below this = bearish
            auto_select_order: If True, select ARIMA order via AIC
            horizon: Forecast horizon ("1D", "1W", etc.)
        """
        self.arima_order = arima_order
        self.garch_p = garch_p
        self.garch_q = garch_q
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.auto_select_order = auto_select_order
        self.horizon = horizon

        self.fitted_arima = None
        self.garch_model = GarchVolatility()
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
        self.diagnostics: Dict[str, Any] = {}

        # Store training data for refitting
        self._train_returns: Optional[pd.Series] = None

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

    def _ensure_datetime_index(self, series: pd.Series) -> pd.Series:
        """Ensure series uses a DatetimeIndex with a frequency."""
        if not isinstance(series.index, pd.DatetimeIndex):
            series = series.copy()
            series.index = pd.date_range(
                end=pd.Timestamp.now(),
                periods=len(series),
                freq="B",
            )
            return series

        freq = series.index.freq or pd.infer_freq(series.index)
        series = series.copy()
        if freq is None:
            series.index = pd.DatetimeIndex(series.index)
            return series
        series.index = pd.DatetimeIndex(series.index, freq=freq)
        return series

    def _build_returns_series(self, df: pd.DataFrame) -> pd.Series:
        """Build returns series with a supported datetime index."""
        returns = df["close"].pct_change().dropna()

        if "ts" in df.columns:
            ts = pd.to_datetime(df.loc[returns.index, "ts"], errors="coerce")
            returns = returns.copy()
            returns.index = ts

        return self._ensure_datetime_index(returns)

    def _select_arima_order(
        self,
        returns: pd.Series,
        max_p: int = 3,
        max_q: int = 3,
    ) -> Tuple[int, int, int]:
        """
        Select optimal ARIMA order using AIC.

        Args:
            returns: Return series
            max_p: Maximum AR order to try
            max_q: Maximum MA order to try

        Returns:
            Optimal (p, d, q) tuple
        """
        best_aic = np.inf
        best_order = (1, 0, 1)

        # Test stationarity - if non-stationary, use d=1
        from statsmodels.tsa.stattools import adfuller

        try:
            adf_result = adfuller(returns.dropna())
            d = 0 if adf_result[1] < 0.05 else 1
        except Exception:
            d = 0

        for p in range(max_p + 1):
            for q in range(max_q + 1):
                if p == 0 and q == 0:
                    continue
                try:
                    model = ARIMA(returns, order=(p, d, q))
                    fitted = model.fit()
                    if fitted.aic < best_aic:
                        best_aic = fitted.aic
                        best_order = (p, d, q)
                except Exception:
                    continue

        logger.info(
            "Auto-selected ARIMA order: %s (AIC=%.2f)",
            best_order,
            best_aic,
        )
        return best_order

    def train(
        self,
        df: pd.DataFrame,
        min_samples: int = 100,
    ) -> "ArimaGarchForecaster":
        """
        Train ARIMA-GARCH model on price data.

        Args:
            df: DataFrame with 'close' column
            min_samples: Minimum samples required for training

        Returns:
            self
        """
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        # Calculate returns with a supported datetime index
        returns = self._build_returns_series(df)

        if len(returns) < min_samples:
            raise ValueError(f"Insufficient data: {len(returns)} < {min_samples}")

        self._train_returns = returns.copy()

        # Auto-select ARIMA order if requested
        if self.auto_select_order:
            self.arima_order = self._select_arima_order(returns)

        # Fit ARIMA
        logger.info("Fitting ARIMA%s model...", self.arima_order)
        try:
            arima_model = ARIMA(returns, order=self.arima_order)
            self.fitted_arima = arima_model.fit()

            arima_aic = self.fitted_arima.aic
            arima_bic = self.fitted_arima.bic

            logger.info(
                "ARIMA fitted: AIC=%.2f, BIC=%.2f",
                arima_aic,
                arima_bic,
            )
        except Exception as e:
            logger.error("ARIMA fitting failed: %s", e)
            raise

        # Fit GARCH on ARIMA residuals
        logger.info("Fitting GARCH(1,1) on residuals...")
        try:
            residuals = pd.Series(
                self.fitted_arima.resid,
                index=returns.index[-len(self.fitted_arima.resid) :],
            )
            self.garch_model.fit(residuals)
        except Exception as e:
            logger.warning("GARCH fitting failed: %s. Using simple volatility.", e)

        # Run diagnostics
        self._run_diagnostics()

        # Calculate training accuracy (in-sample)
        self._calculate_training_accuracy(returns)

        self.is_trained = True
        self.training_stats["trained_at"] = datetime.now().isoformat()
        self.training_stats["n_samples"] = len(returns)
        self.training_stats["arima_order"] = self.arima_order

        return self

    def _run_diagnostics(self) -> None:
        """Run diagnostic tests on fitted model."""
        if self.fitted_arima is None:
            return

        residuals = self.fitted_arima.resid

        # Ljung-Box test for residual autocorrelation
        try:
            lb_result = acorr_ljungbox(residuals, lags=10, return_df=True)
            lb_pvalue = float(lb_result["lb_pvalue"].iloc[-1])
            has_autocorrelation = lb_pvalue < 0.05
        except Exception:
            lb_pvalue = None
            has_autocorrelation = None

        # Normality test (Jarque-Bera)
        try:
            jb_stat, jb_pvalue = stats.jarque_bera(residuals)
        except Exception:
            jb_stat, jb_pvalue = None, None

        self.diagnostics = {
            "ljung_box_pvalue": lb_pvalue,
            "has_autocorrelation": has_autocorrelation,
            "jarque_bera_stat": float(jb_stat) if jb_stat else None,
            "jarque_bera_pvalue": float(jb_pvalue) if jb_pvalue else None,
            "residual_mean": float(residuals.mean()),
            "residual_std": float(residuals.std()),
            "arima_aic": float(self.fitted_arima.aic),
            "arima_bic": float(self.fitted_arima.bic),
        }

        logger.info(
            "Diagnostics: LB p-value=%.4f, autocorr=%s",
            lb_pvalue or 0,
            has_autocorrelation,
        )

    def _calculate_training_accuracy(self, returns: pd.Series) -> None:
        """Calculate in-sample classification accuracy."""
        if self.fitted_arima is None:
            return

        # Get in-sample predictions
        fitted_values = self.fitted_arima.fittedvalues

        # Classify predictions and actuals
        pred_labels = self._classify_returns(fitted_values)
        actual_labels = self._classify_returns(returns.iloc[-len(fitted_values) :])

        # Calculate accuracy
        correct = (pred_labels == actual_labels).sum()
        accuracy = correct / len(pred_labels)

        # Calculate directional accuracy
        pred_direction = np.sign(fitted_values)
        actual_direction = np.sign(returns.iloc[-len(fitted_values) :])
        directional_accuracy = (pred_direction == actual_direction).mean()

        self.training_stats["accuracy"] = float(accuracy)
        self.training_stats["directional_accuracy"] = float(directional_accuracy)

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
            df: Optional new data to refit on (uses training data if None)
            steps: Number of steps ahead to forecast

        Returns:
            Dict with label, confidence, probabilities, and forecast details
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Refit on new data if provided
        if df is not None and "close" in df.columns:
            returns = self._build_returns_series(df)
            try:
                arima_model = ARIMA(returns, order=self.arima_order)
                self.fitted_arima = arima_model.fit()
            except Exception as e:
                logger.warning("Refit failed: %s. Using original model.", e)

        # Generate ARIMA forecast
        try:
            forecast_result = self.fitted_arima.get_forecast(steps=steps)
            # Use cumulative return over all steps (ARIMA predicts step-by-step returns)
            forecast_means = forecast_result.predicted_mean.values
            forecast_mean_cumulative = float(np.sum(forecast_means))
            forecast_ci = forecast_result.conf_int(alpha=0.05)
            # Use last step CI (uncertainty at horizon endpoint)
            ci_lower = float(forecast_ci.iloc[-1, 0])
            ci_upper = float(forecast_ci.iloc[-1, 1])
        except Exception as e:
            logger.error("Forecast failed: %s", e)
            return self._null_prediction(str(e), steps=steps)

        # Get GARCH volatility forecast; scale by sqrt(steps) for multi-period
        try:
            garch_variance = self.garch_model.predict_variance(steps=steps)
            if isinstance(garch_variance, (list, np.ndarray)):
                avg_variance = np.mean(garch_variance)
                garch_volatility = np.sqrt(avg_variance * steps)
            else:
                garch_volatility = np.sqrt(float(garch_variance) * steps)
        except Exception:
            # Fallback to simple volatility, scaled by sqrt(steps)
            base_vol = (
                float(self._train_returns.std()) if self._train_returns is not None else 0.02
            )
            garch_volatility = base_vol * np.sqrt(steps)

        # Classify using horizon-scaled thresholds (e.g. 2% per day -> 10% for 5D)
        bull_thresh = self.bullish_threshold * steps
        bear_thresh = self.bearish_threshold * steps
        if forecast_mean_cumulative > bull_thresh:
            label = "Bullish"
        elif forecast_mean_cumulative < bear_thresh:
            label = "Bearish"
        else:
            label = "Neutral"

        # Calculate probabilities using cumulative forecast and scaled volatility
        probabilities = self._calculate_probabilities(
            forecast_mean_cumulative,
            float(garch_volatility),
            steps=steps,
        )

        confidence = float(probabilities[label.lower()])

        return {
            "label": label,
            "confidence": confidence,
            "probabilities": probabilities,
            "forecast_return": forecast_mean_cumulative,
            "forecast_volatility": float(garch_volatility),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "arima_order": self.arima_order,
            "diagnostics": self.diagnostics,
            "steps": steps,
        }

    def _calculate_probabilities(
        self,
        forecast_mean: float,
        forecast_std: float,
        steps: int = 1,
    ) -> Dict[str, float]:
        """
        Calculate class probabilities using normal distribution.

        Args:
            forecast_mean: Predicted return (cumulative over steps when steps > 1)
            forecast_std: Forecast standard deviation (scaled for horizon)
            steps: Number of forecast steps (used to scale thresholds when > 1)

        Returns:
            Dict with probabilities for each class
        """
        if forecast_std <= 0:
            forecast_std = 0.01

        # Scale thresholds for multi-step (consistent with classification)
        bear_thresh = self.bearish_threshold * steps
        bull_thresh = self.bullish_threshold * steps

        # Calculate probabilities using CDF
        prob_bearish = stats.norm.cdf(
            bear_thresh,
            loc=forecast_mean,
            scale=forecast_std,
        )
        prob_bullish = 1 - stats.norm.cdf(
            bull_thresh,
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
        else:
            # Refit on new data
            returns = df["close"].pct_change().dropna()
            try:
                arima_model = ARIMA(returns, order=self.arima_order)
                self.fitted_arima = arima_model.fit()
                self.garch_model.fit(pd.Series(self.fitted_arima.resid))
            except Exception as e:
                logger.warning("Refit failed: %s", e)

        # Get prediction
        prediction = self.predict(steps=horizon_days)

        # Generate forecast points
        last_close = df["close"].iloc[-1]
        last_ts = pd.to_datetime(df["ts"].iloc[-1]).to_pydatetime()

        points = self._generate_forecast_points(
            last_ts=last_ts,
            last_close=last_close,
            forecast_return=prediction["forecast_return"],
            forecast_volatility=prediction["forecast_volatility"],
            horizon_days=horizon_days,
            confidence=prediction["confidence"],
        )

        return {
            "label": prediction["label"],
            "confidence": prediction["confidence"],
            "raw_confidence": prediction["confidence"],
            "horizon": horizon,
            "points": points,
            "probabilities": prediction["probabilities"],
            "model_type": "ARIMA-GARCH",
            "arima_order": self.arima_order,
            "forecast_return": prediction["forecast_return"],
            "forecast_volatility": prediction["forecast_volatility"],
            "diagnostics": prediction["diagnostics"],
        }

    def _generate_forecast_points(
        self,
        last_ts: datetime,
        last_close: float,
        forecast_return: float,
        forecast_volatility: float,
        horizon_days: int,
        confidence: float,
    ) -> list[Dict[str, Any]]:
        """Generate forecast points for visualization."""
        points = []

        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)

            # forecast_return is cumulative over horizon_days; scale to day i
            cumulative_return = forecast_return * (i / horizon_days) if horizon_days else 0
            # Volatility scales with sqrt(time)
            cumulative_volatility = forecast_volatility * (np.sqrt(i) / np.sqrt(horizon_days)) if horizon_days else 0

            forecast_value = float(last_close) * (1 + cumulative_return)

            # Confidence bands based on volatility
            z_score = 1.96  # 95% CI
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

    def _null_prediction(self, error_msg: str, steps: int = 1) -> Dict[str, Any]:
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
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "steps": steps,
            "error": error_msg,
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "name": "ARIMA-GARCH",
            "is_trained": self.is_trained,
            "arima_order": self.arima_order,
            "garch_params": {"p": self.garch_p, "q": self.garch_q},
            "thresholds": {
                "bullish": self.bullish_threshold,
                "bearish": self.bearish_threshold,
            },
            "training_stats": self.training_stats,
            "diagnostics": self.diagnostics,
        }


if __name__ == "__main__":
    # Quick test
    import yfinance as yf

    print("Testing ARIMA-GARCH Forecaster...")

    # Fetch sample data
    data = yf.download("SPY", start="2023-01-01", end="2024-12-31", progress=False)
    df = data.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close", "date": "ts"})

    # Initialize and train
    forecaster = ArimaGarchForecaster(
        arima_order=(1, 0, 1),
        auto_select_order=False,
    )
    forecaster.train(df)

    # Generate forecast
    forecast = forecaster.generate_forecast(df, horizon="1W")

    print(f"\nForecast: {forecast['label']} (confidence: {forecast['confidence']:.3f})")
    print(f"Expected return: {forecast['forecast_return']:.4f}")
    print(f"Volatility: {forecast['forecast_volatility']:.4f}")
    print(f"Probabilities: {forecast['probabilities']}")
    print(f"\nModel info: {forecaster.get_model_info()}")
