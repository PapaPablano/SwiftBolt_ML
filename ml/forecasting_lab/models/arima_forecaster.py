"""
ARIMA forecaster: models returns, then reconstructs price path.

Lazy-imports statsmodels so naive runs never load heavy deps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting_lab.models.base import BaseForecaster, OHLCStep


class ARIMAForecaster(BaseForecaster):
    """ARIMA on returns; reconstruct close path via cumprod."""

    name = "arima"

    def __init__(self, order: tuple[int, int, int] = (2, 0, 2)):
        self.order = order
        self._model = None
        self._last_close: float | None = None

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "close",
        horizon: int = 1,
    ) -> None:
        from statsmodels.tsa.arima.model import ARIMA

        close = df[target_col].astype(float).dropna()
        if len(close) < 10:
            self._model = None
            self._last_close = float(close.iloc[-1]) if len(close) > 0 else None
            return

        returns = close.pct_change().dropna()
        if len(returns) < 5:
            self._model = None
            self._last_close = float(close.iloc[-1])
            return

        try:
            self._model = ARIMA(returns, order=self.order).fit()
        except Exception:
            self._model = None
        self._last_close = float(close.iloc[-1])

    def predict(self, df: pd.DataFrame, horizon: int = 1) -> list[OHLCStep]:
        if self._model is None:
            last = float(df["close"].iloc[-1]) if len(df) > 0 else 100.0
            return [{"open": last, "high": last, "low": last, "close": last, "volume": 0} for _ in range(horizon)]

        last_close = self._last_close if self._last_close is not None else float(df["close"].iloc[-1])

        try:
            fc = self._model.forecast(steps=horizon)
            rets = np.asarray(fc).ravel()
        except Exception:
            rets = np.zeros(horizon)

        closes = last_close * np.cumprod(1.0 + np.clip(rets, -0.5, 0.5))
        return [
            {"open": c, "high": c, "low": c, "close": c, "volume": 0}
            for c in closes
        ]
