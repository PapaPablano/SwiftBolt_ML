import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ConformalIntervalResult:
    enabled: bool
    method: str
    n_samples: int
    coverage: float
    q_abs_log_residual: float


class ConformalIntervalCalibrator:
    def __init__(
        self,
        min_samples: int = 30,
        max_abs_log_residual: float = 0.40,
        default_q: float = 0.05,
    ) -> None:
        self.min_samples = min_samples
        self.max_abs_log_residual = max_abs_log_residual
        self.default_q = default_q

    def _abs_log_residuals(self, evals: pd.DataFrame) -> np.ndarray:
        if evals.empty:
            return np.array([])

        if "predicted_value" not in evals.columns or "realized_price" not in evals.columns:
            return np.array([])

        pred = pd.to_numeric(evals["predicted_value"], errors="coerce")
        real = pd.to_numeric(evals["realized_price"], errors="coerce")
        mask = (pred > 0) & (real > 0)
        pred = pred[mask]
        real = real[mask]
        if len(pred) == 0:
            return np.array([])

        r = np.log(real.values / pred.values)
        r = r[np.isfinite(r)]
        r = np.clip(r, -self.max_abs_log_residual, self.max_abs_log_residual)
        return np.abs(r)

    def fit(
        self,
        evals: pd.DataFrame,
        coverage: float = 0.90,
    ) -> ConformalIntervalResult:
        cov = float(np.clip(coverage, 0.50, 0.99))
        abs_r = self._abs_log_residuals(evals)

        if abs_r.size < self.min_samples:
            return ConformalIntervalResult(
                enabled=False,
                method="abs_log_residual",
                n_samples=int(abs_r.size),
                coverage=cov,
                q_abs_log_residual=float(self.default_q),
            )

        q = float(np.quantile(abs_r, cov))
        q = float(np.clip(q, 0.0, self.max_abs_log_residual))
        return ConformalIntervalResult(
            enabled=True,
            method="abs_log_residual",
            n_samples=int(abs_r.size),
            coverage=cov,
            q_abs_log_residual=q,
        )


def conformal_bounds(price: float, q_abs_log: float) -> tuple[float, float]:
    if price <= 0:
        return (price, price)
    q = max(0.0, float(q_abs_log))
    lo = price * math.exp(-q)
    hi = price * math.exp(q)
    return (lo, hi)
