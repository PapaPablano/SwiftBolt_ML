"""
State-Space Kalman Forecaster: SARIMAX with exogenous regressors.
========================================================================

Uses statsmodels SARIMAX (Kalman filter) for intraday turn capture.
Regression coefficients are updated via the filter when time_varying_regression=True.

Key Features:
- Endogenous: returns (stationary)
- Exogenous: kdj_j_divergence, supertrend_trend, garch_vol_regime (robust-scaled)
- Probabilities from forecast variance (CDF over thresholds)
- Drift/coeff extraction from filtered state for audit
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default exog columns (must exist in df after add_technical_features)
DEFAULT_EXOG_COLS = ["kdj_j_divergence", "supertrend_trend", "garch_vol_regime"]


def _build_volatility_regime_fallback(df: pd.DataFrame) -> pd.Series:
    """Build 0/1/2 regime from atr_normalized when garch_vol_regime missing."""
    if "atr_normalized" not in df.columns:
        return pd.Series(1, index=df.index)
    s = df["atr_normalized"].dropna()
    if len(s) < 10:
        return pd.Series(1, index=df.index)
    p33 = s.quantile(0.33)
    p67 = s.quantile(0.67)
    regime = pd.Series(1, index=df.index, dtype=float)
    regime[df["atr_normalized"] < p33] = 0
    regime[df["atr_normalized"] > p67] = 2
    return regime


def _build_exog(
    df: pd.DataFrame, exog_cols: List[str], return_missing_rate: bool = False
) -> Union[Optional[pd.DataFrame], Tuple[Optional[pd.DataFrame], float]]:
    """Build exogenous DataFrame, with fallbacks for missing columns.
    If return_missing_rate=True, returns (exog, exog_missing_rate) with rate computed
    before ffill/bfill for audit."""
    df = df.copy()
    rows = []
    for col in exog_cols:
        use_col = col
        if col not in df.columns:
            if col == "garch_vol_regime":
                df["volatility_regime"] = _build_volatility_regime_fallback(df)
                use_col = "volatility_regime"
            else:
                logger.warning("StateSpaceKalman: exog column %s missing, skipping", col)
                return (None, 0.0) if return_missing_rate else None
        rows.append(df[use_col])
    exog_raw = pd.concat(rows, axis=1)
    exog_missing_rate = float(exog_raw.isna().sum().sum() / (exog_raw.size or 1))
    exog = exog_raw.ffill().bfill().fillna(0)
    if return_missing_rate:
        return exog, exog_missing_rate
    return exog


def _robust_scale_exog(exog: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Tuple[float, float]]]:
    """Robust-scale exog (median, IQR) per column. Returns (scaled_df, scale_params)."""
    scale_params: Dict[str, Tuple[float, float]] = {}
    out = exog.copy()
    for col in exog.columns:
        s = exog[col].astype(float)
        med = s.median()
        q75, q25 = s.quantile(0.75), s.quantile(0.25)
        iqr = float(q75 - q25) if q75 != q25 else 1.0
        if iqr < 1e-8:
            iqr = 1.0
        scale_params[col] = (float(med), iqr)
        out[col] = (s - med) / iqr
    return out, scale_params


def _apply_scale(exog: pd.DataFrame, scale_params: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
    """Apply stored scale params to new exog (inference)."""
    out = exog.copy()
    for col in exog.columns:
        if col in scale_params:
            med, iqr = scale_params[col]
            out[col] = (out[col].astype(float) - med) / max(iqr, 1e-8)
    return out


def _norm_cdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Standard normal CDF via math.erf (no scipy dependency)."""
    if sigma <= 0:
        sigma = 0.01
    z = (x - mu) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _probabilities_from_forecast(
    forecast_mean: float,
    forecast_std: float,
    bull_thresh: float,
    bear_thresh: float,
) -> Dict[str, float]:
    """Compute P(bearish/neutral/bullish) from SARIMAX predictive distribution (mean, variance)."""
    if forecast_std <= 0:
        forecast_std = 0.01
    prob_bearish = float(_norm_cdf(bear_thresh, mu=forecast_mean, sigma=forecast_std))
    prob_bullish = float(1 - _norm_cdf(bull_thresh, mu=forecast_mean, sigma=forecast_std))
    prob_neutral = 1 - prob_bearish - prob_bullish
    # Clamp to [0,1] before normalization (handles fp edge cases: tiny std, extreme thresholds)
    prob_bearish = max(0.0, min(1.0, prob_bearish))
    prob_bullish = max(0.0, min(1.0, prob_bullish))
    prob_neutral = max(0.0, min(1.0, prob_neutral))
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


class StateSpaceKalmanForecaster:
    """
    SARIMAX-based forecaster with exogenous regressors for intraday turn capture.

    Uses Kalman filter for state estimation; regression coefficients can be
    time-varying when time_varying_regression=True.
    """

    def __init__(
        self,
        horizon: str = "15m",
        arima_order: Tuple[int, int, int] = (1, 0, 1),
        bullish_threshold: float = 0.002,
        bearish_threshold: float = -0.002,
        min_bars: int = 50,
    ) -> None:
        self.horizon = horizon
        self.arima_order = arima_order
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.min_bars = min_bars
        self._model = None
        self._results = None
        self._exog_cols: List[str] = []
        self._scale_params: Dict[str, Tuple[float, float]] = {}
        self._last_state: Optional[np.ndarray] = None
        self._last_state_cov: Optional[np.ndarray] = None
        self.is_trained = False
        self._fit_converged = False
        self._fit_nobs = 0
        self._exog_missing_rate = 0.0

    def train(
        self,
        df: pd.DataFrame,
        exog_cols: Optional[List[str]] = None,
    ) -> "StateSpaceKalmanForecaster":
        """Fit SARIMAX on returns with robust-scaled exogenous regressors."""
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        exog_cols = exog_cols or DEFAULT_EXOG_COLS
        self._exog_cols = exog_cols

        returns = df["close"].pct_change().dropna()
        if len(returns) < self.min_bars:
            raise ValueError(
                f"StateSpaceKalman: need >= {self.min_bars} bars, got {len(returns)}"
            )

        built = _build_exog(df.loc[returns.index], exog_cols, return_missing_rate=True)
        exog_raw, self._exog_missing_rate = built
        if exog_raw is None:
            raise ValueError("StateSpaceKalman: could not build exog")

        exog_scaled, self._scale_params = _robust_scale_exog(exog_raw)

        common = returns.index.intersection(exog_scaled.index)
        if len(common) < self.min_bars:
            raise ValueError(
                f"StateSpaceKalman: aligned data too short ({len(common)} bars)"
            )
        endog = returns.loc[common]
        exog_aligned = exog_scaled.loc[common]

        try:
            model = SARIMAX(
                endog,
                exog=exog_aligned,
                order=self.arima_order,
                seasonal_order=(0, 0, 0, 0),
                time_varying_regression=True,
                mle_regression=False,
            )
            self._results = model.fit(disp=False)
            self._model = model
            self.is_trained = True
            mle = getattr(self._results, "mle_retvals", None)
            self._fit_converged = bool(mle.get("converged", False)) if isinstance(mle, dict) else False
            self._fit_nobs = len(endog)

            if hasattr(self._results, "predicted_state") and self._results.predicted_state is not None:
                self._last_state = np.array(self._results.predicted_state[:, -1])
            if hasattr(self._results, "predicted_state_covariance") and self._results.predicted_state_covariance is not None:
                cov = self._results.predicted_state_covariance
                self._last_state_cov = cov[:, :, -1] if cov.ndim == 3 else cov

            logger.info(
                "StateSpaceKalman fitted: %d bars, order=%s",
                len(endog),
                self.arima_order,
            )
        except Exception as e:
            logger.warning("StateSpaceKalman fit failed: %s", e)
            raise

        return self

    def predict(
        self,
        df: pd.DataFrame,
        exog_cols: Optional[List[str]] = None,
        steps: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Generate forecast with classification and Kalman diagnostics."""
        if not self.is_trained:
            return None

        exog_cols = exog_cols or self._exog_cols
        exog_raw = _build_exog(df, exog_cols)
        if exog_raw is None:
            return None

        exog = _apply_scale(exog_raw, self._scale_params) if self._scale_params else exog_raw

        try:
            exog_future = exog.tail(1)
            if steps > 1:
                exog_future = pd.concat([exog_future] * steps, ignore_index=True)
            forecast = self._results.get_forecast(steps=steps, exog=exog_future)
            forecast_mean = forecast.predicted_mean
            if hasattr(forecast_mean, "values"):
                forecast_mean = float(np.sum(forecast_mean.values))
            else:
                forecast_mean = float(np.sum(forecast_mean))

            ci = forecast.conf_int(alpha=0.05)
            if hasattr(ci, "values") and ci.values.size > 0:
                lo, hi = float(ci.values[-1, 0]), float(ci.values[-1, 1])
                forecast_std = (hi - lo) / (2 * 1.96) if hi > lo else 0.01
            else:
                forecast_std = 0.01
        except Exception as e:
            logger.warning("StateSpaceKalman forecast failed: %s", e)
            return None

        bull_thresh = self.bullish_threshold * steps
        bear_thresh = self.bearish_threshold * steps
        probabilities = _probabilities_from_forecast(
            forecast_mean, forecast_std, bull_thresh, bear_thresh
        )
        label = max(probabilities, key=probabilities.get)
        label = label.capitalize()
        confidence = float(probabilities[label.lower()])

        drift = forecast_mean
        try:
            params = self._results.params
            if "const" in params.index:
                drift = float(params["const"])
        except Exception:
            pass

        exog_coeffs = {}
        exog_coeffs_source = "static_params"
        try:
            if hasattr(self._results, "filtered_regression_coefficients"):
                coeffs = self._results.filtered_regression_coefficients
                if coeffs is not None and coeffs.size > 0:
                    last = coeffs[:, -1] if coeffs.ndim > 1 else coeffs
                    for i, col in enumerate(exog_cols):
                        if i < len(last):
                            exog_coeffs[col] = float(last[i])
                    if exog_coeffs:
                        exog_coeffs_source = "filtered"
            if not exog_coeffs:
                for col in exog_cols:
                    for key in (f"beta.{col}", col):
                        if key in self._results.params.index:
                            exog_coeffs[col] = float(self._results.params[key])
                            break
        except Exception:
            pass

        kalman_health = {
            "converged": self._fit_converged,
            "nobs": self._fit_nobs,
            "exog_missing_rate": round(self._exog_missing_rate, 4),
            "exog_coeffs_source": exog_coeffs_source,
        }

        return {
            "label": label,
            "confidence": confidence,
            "probabilities": probabilities,
            "forecast_return": forecast_mean,
            "kalman_drift": drift,
            "kalman_exog_coeffs": exog_coeffs,
            "kalman_health": kalman_health,
        }

    def get_filter_state(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Return last predicted state and covariance for incremental filtering."""
        if self._last_state is not None and self._last_state_cov is not None:
            return (self._last_state.copy(), self._last_state_cov.copy())
        return None

    def filter_incremental(
        self,
        new_bars: pd.DataFrame,
        exog_cols: Optional[List[str]] = None,
        prev_state: Optional[np.ndarray] = None,
        prev_cov: Optional[np.ndarray] = None,
        steps: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Filter-only update (no MLE refit) using prior state.
        Use when ENABLE_KALMAN_INCREMENTAL=true for low latency.
        Falls back to predict() when incremental path not available.
        """
        # Full incremental filter-with-state-reuse requires statsmodels filter API
        # that accepts initial_state; for now fall back to predict (refit path).
        _ = (prev_state, prev_cov)  # reserved for future use
        return self.predict(new_bars, exog_cols=exog_cols, steps=steps)
