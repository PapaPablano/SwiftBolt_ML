"""
Volatility regime features using GARCH(1,1) variance estimation.
Produces conditional variance and percentile-based regime buckets.
"""

import logging

import numpy as np
import pandas as pd
from arch import arch_model

logger = logging.getLogger(__name__)


class GarchVolatility:
    """
    Fits a simple GARCH(1,1) on returns to estimate conditional variance.
    """

    def __init__(self, dist: str = "normal") -> None:
        self.dist = dist
        self.model = None
        self.res = None

    def fit(self, returns: pd.Series) -> None:
        clean = returns.dropna()
        if len(clean) < 100:
            raise ValueError("Not enough data for GARCH fit (need >=100)")
        self.model = arch_model(
            clean * 100,
            p=1,
            q=1,
            mean="Zero",
            vol="GARCH",
            dist=self.dist,
        )
        self.res = self.model.fit(disp="off")
        logger.info("Fitted GARCH on %s samples", len(clean))

    def predict_variance(self, steps: int = 1) -> float:
        if self.res is None:
            raise RuntimeError("GARCH model not fitted")
        forecast = self.res.forecast(horizon=steps)
        # Return next-step variance (convert back from percentage space)
        variance = forecast.variance.values[-1, -1] / (100 ** 2)
        return variance

    def in_sample_variance(self) -> pd.Series:
        if self.res is None:
            raise RuntimeError("GARCH model not fitted")
        var = self.res.conditional_volatility ** 2 / (100 ** 2)
        var.index = self.res.model._y.index
        return var


def add_garch_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds GARCH-based conditional variance and simple regime labels.
    Adds columns:
      - garch_variance
      - garch_vol_regime (0=low,1=mid,2=high)
    """
    returns = df["close"].pct_change()
    out = df.copy()
    try:
        garch = GarchVolatility()
        garch.fit(returns)
        var_series = garch.in_sample_variance()
        out["garch_variance"] = var_series.reindex(out.index).bfill()
        p33 = out["garch_variance"].quantile(0.33)
        p67 = out["garch_variance"].quantile(0.67)
        regime = pd.Series(index=out.index, dtype="Int64")
        regime[out["garch_variance"] < p33] = 0
        regime[
            (out["garch_variance"] >= p33) & (out["garch_variance"] <= p67)
        ] = 1
        regime[out["garch_variance"] > p67] = 2
        out["garch_vol_regime"] = regime
    except Exception as exc:  # noqa: BLE001
        logger.warning("GARCH features failed: %s", exc)
        out["garch_variance"] = np.nan
        out["garch_vol_regime"] = pd.Series(index=out.index, dtype="Int64")
    return out
