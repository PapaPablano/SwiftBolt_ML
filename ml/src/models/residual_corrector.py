import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResidualCorrectionResult:
    correction_factor: float
    log_residual_pred: float
    method: str
    n_samples: int
    ewma_sigma: float | None = None


class ResidualCorrector:
    def __init__(
        self,
        min_samples: int = 20,
        arma_order: tuple[int, int, int] = (1, 0, 1),
        max_abs_log_residual: float = 0.20,
        ewma_alpha: float = 0.25,
    ) -> None:
        self.min_samples = min_samples
        self.arma_order = arma_order
        self.max_abs_log_residual = max_abs_log_residual
        self.ewma_alpha = ewma_alpha

    def compute_log_residuals(self, evals: pd.DataFrame) -> np.ndarray:
        if evals.empty:
            return np.array([])

        if (
            "predicted_value" not in evals.columns
            or "realized_price" not in evals.columns
        ):
            return np.array([])

        pred = pd.to_numeric(evals["predicted_value"], errors="coerce")
        real = pd.to_numeric(evals["realized_price"], errors="coerce")

        mask = (pred > 0) & (real > 0)
        pred = pred[mask]
        real = real[mask]

        if len(pred) == 0:
            return np.array([])

        resid = np.log(real.values / pred.values)
        resid = resid[np.isfinite(resid)]
        resid = np.clip(
            resid,
            -self.max_abs_log_residual,
            self.max_abs_log_residual,
        )
        return resid

    def _ewma_mean(self, x: np.ndarray) -> float:
        m = 0.0
        for v in x:
            m = (1.0 - self.ewma_alpha) * m + self.ewma_alpha * float(v)
        return float(m)

    def _ewma_sigma(self, x: np.ndarray) -> float:
        m = 0.0
        v = 0.0
        for val in x:
            x_t = float(val)
            m_prev = m
            m = (1.0 - self.ewma_alpha) * m + self.ewma_alpha * x_t
            err = x_t - m_prev
            v = (1.0 - self.ewma_alpha) * v + self.ewma_alpha * (err * err)
        return float(math.sqrt(max(0.0, v)))

    def fit_predict(
        self,
        log_residuals: np.ndarray,
    ) -> ResidualCorrectionResult:
        x = np.asarray(log_residuals, dtype=float)
        x = x[np.isfinite(x)]

        sigma = self._ewma_sigma(x) if x.size > 0 else None

        if x.size == 0:
            return ResidualCorrectionResult(
                correction_factor=1.0,
                log_residual_pred=0.0,
                method="none",
                n_samples=0,
                ewma_sigma=sigma,
            )

        if x.size < self.min_samples:
            pred = self._ewma_mean(x)
            return ResidualCorrectionResult(
                correction_factor=float(math.exp(pred)),
                log_residual_pred=float(pred),
                method="ewma",
                n_samples=int(x.size),
                ewma_sigma=sigma,
            )

        try:
            from statsmodels.tsa.arima.model import ARIMA

            model = ARIMA(x, order=self.arma_order)
            res = model.fit()
            pred = float(res.forecast(steps=1)[0])
            pred = float(
                np.clip(
                    pred,
                    -self.max_abs_log_residual,
                    self.max_abs_log_residual,
                )
            )
            return ResidualCorrectionResult(
                correction_factor=float(math.exp(pred)),
                log_residual_pred=float(pred),
                method="arma_101",
                n_samples=int(x.size),
                ewma_sigma=sigma,
            )
        except Exception:
            pred = self._ewma_mean(x)
            return ResidualCorrectionResult(
                correction_factor=float(math.exp(pred)),
                log_residual_pred=float(pred),
                method="ewma_fallback",
                n_samples=int(x.size),
                ewma_sigma=sigma,
            )
