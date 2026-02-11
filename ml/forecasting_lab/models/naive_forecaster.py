"""
Naive forecaster: repeats last observed OHLC bar for horizon steps.

Implements BaseForecaster so the pipeline is runnable end-to-end without external models.
Option A: predict() returns list of OHLC dicts (same bar repeated).
"""

import pandas as pd

from forecasting_lab.models.base import BaseForecaster, OHLCStep


class NaiveForecaster(BaseForecaster):
    """Predict horizon steps as the last bar's OHLC repeated (no training needed)."""

    name = "naive"

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "close",
        horizon: int = 1,
    ) -> None:
        """No-op; last bar is used at predict time."""
        pass

    def predict(self, df: pd.DataFrame, horizon: int = 1) -> list[OHLCStep]:
        """Return horizon copies of the last bar's OHLC."""
        if df is None or len(df) == 0:
            return [{"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0} for _ in range(horizon)]
        row = df.iloc[-1]
        o = float(row.get("open", row["close"]))
        h = float(row.get("high", row["close"]))
        l_ = float(row.get("low", row["close"]))
        c = float(row["close"])
        v = float(row.get("volume", 0))
        return [{"open": o, "high": h, "low": l_, "close": c, "volume": v} for _ in range(horizon)]
