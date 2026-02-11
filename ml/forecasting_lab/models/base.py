"""
Abstract forecaster interface for Forecasting Lab.

Any forecaster used in the lab implements train + predict so the runner stays model-agnostic.
Option A: predict() returns predicted OHLC for horizon steps (list of OHLC dicts).
"""

from abc import ABC, abstractmethod
import pandas as pd

# Option A OHLC: each step is {"open", "high", "low", "close", "volume?"}.
# Extra keys allowed: indicator forecast bundle (rsi_14, macd, bb_mid, kdj_k, ...), and optionally
# lower, upper, confidence, components, weights for ensembles. Convert to canonical ForecastPoint
# via forecasting_lab.schema.points.ohlc_steps_to_points() for ml_forecasts.points / ml_forecasts_intraday.points.
OHLCStep = dict[str, float]


class BaseForecaster(ABC):
    """Abstract forecaster: train(df, target_col, horizon), predict(df, horizon) -> list of OHLC steps."""

    name: str = "base"

    @abstractmethod
    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "close",
        horizon: int = 1,
    ) -> None:
        """
        Train the model on historical OHLC (and optional features).

        Args:
            df: DataFrame with at least target_col and optionally open, high, low, volume.
            target_col: Column to predict (e.g. 'close').
            horizon: Number of steps to predict (e.g. 1 or 5).
        """
        pass

    @abstractmethod
    def predict(self, df: pd.DataFrame, horizon: int = 1) -> list[OHLCStep]:
        """
        Produce predicted OHLC for the next horizon steps.

        Args:
            df: DataFrame with same columns as used in train (e.g. recent history).
            horizon: Number of steps to predict.

        Returns:
            List of length horizon; each element is a dict with keys:
            open, high, low, close, and optionally volume (default 0).
            e.g. [{"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 0}, ...]
        """
        pass
