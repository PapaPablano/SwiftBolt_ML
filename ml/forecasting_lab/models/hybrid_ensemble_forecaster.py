"""
Hybrid ensemble: weighted XGBoost + ARIMA. Fallback to XGBoost if ARIMA unavailable.

Gate ARIMA when it diverges from XGB beyond a threshold (confidence-by-agreement).
Lazy-imports sub-models so naive runs never load xgboost/statsmodels.
"""

from __future__ import annotations

import pandas as pd

from forecasting_lab.models.base import BaseForecaster, OHLCStep


class HybridEnsembleForecaster(BaseForecaster):
    """Weighted combination of XGBoost and ARIMA; outputs list[OHLCStep]."""

    name = "hybrid"

    def __init__(
        self,
        xgb_weight: float = 0.6,
        arima_weight: float = 0.4,
        arima_order: tuple[int, int, int] = (2, 0, 2),
        divergence_threshold: float | None = 0.15,
    ):
        self.xgb_weight = xgb_weight
        self.arima_weight = arima_weight
        self.arima_order = arima_order
        self.divergence_threshold = divergence_threshold
        self._xgb = None
        self._arima = None

    def _get_models(self) -> tuple:
        if self._xgb is None:
            from forecasting_lab.models.xgboost_forecaster import XGBoostForecaster
            self._xgb = XGBoostForecaster()
        if self._arima is None:
            from forecasting_lab.models.arima_forecaster import ARIMAForecaster
            self._arima = ARIMAForecaster(order=self.arima_order)
        return self._xgb, self._arima

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "close",
        horizon: int = 1,
    ) -> None:
        xgb, arima = self._get_models()
        xgb.train(df, target_col=target_col, horizon=horizon)
        arima.train(df, target_col=target_col, horizon=horizon)

    def predict(self, df: pd.DataFrame, horizon: int = 1) -> list[OHLCStep]:
        xgb, arima = self._get_models()
        xgb_pred = xgb.predict(df, horizon=horizon)
        arima_pred = arima.predict(df, horizon=horizon)

        out: list[OHLCStep] = []
        for i in range(horizon):
            xc = xgb_pred[i]["close"] if i < len(xgb_pred) else float(df["close"].iloc[-1])
            ac = arima_pred[i]["close"] if i < len(arima_pred) else xc

            w_xgb, w_arima = self.xgb_weight, self.arima_weight
            if self.divergence_threshold is not None:
                denom = max(abs(xc), abs(ac), 1.0)
                rel_diff = abs(xc - ac) / denom
                if rel_diff > self.divergence_threshold:
                    w_arima = 0.0
                    w_xgb = 1.0

            total = w_xgb + w_arima
            if total > 0:
                ensemble_close = (w_xgb * xc + w_arima * ac) / total
            else:
                ensemble_close = xc

            out.append({
                "open": ensemble_close,
                "high": ensemble_close,
                "low": ensemble_close,
                "close": ensemble_close,
                "volume": 0,
            })
        return out
