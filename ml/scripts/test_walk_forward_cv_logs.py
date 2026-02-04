#!/usr/bin/env python3
"""One-off script to verify TimeSeriesSplit CV logs from WalkForwardOptimizer."""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.training.walk_forward_optimizer import WalkForwardOptimizer

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SimpleRidgeEnsemble:
    def __init__(self, n_lags: int = 5, alpha: float = 1.0):
        self.n_lags = n_lags
        self.alpha = alpha
        self.model = None
        self._feature_cols = None

    def set_hyperparameters(self, params: dict) -> None:
        if not params:
            return
        self.alpha = params.get("alpha", self.alpha)
        self.n_lags = params.get("n_lags", self.n_lags)

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        ret = df["close"].astype(float).pct_change()
        out = pd.DataFrame(index=df.index)
        for i in range(1, self.n_lags + 1):
            out[f"lag_{i}"] = ret.shift(i)
        return out

    def train(self, data: pd.DataFrame) -> None:
        from sklearn.linear_model import Ridge

        if "actual" not in data.columns and "close" in data.columns:
            data = data.copy()
            data["actual"] = data["close"].astype(float).pct_change().shift(-1)
        y = data["actual"].dropna()
        if len(y) < 50:
            self.model = None
            return
        X = self._features(data).loc[y.index].dropna(how="any")
        y = y.loc[X.index]
        if len(X) < 30:
            self.model = None
            return
        self.model = Ridge(alpha=self.alpha, random_state=42)
        self.model.fit(X.astype(float), y.astype(float))
        self._feature_cols = list(X.columns)

    def predict(self, data: pd.DataFrame):
        if self.model is None:
            return np.full(len(data), np.nan)
        X = self._features(data).astype(float)
        if self._feature_cols:
            X = X.reindex(columns=self._feature_cols).fillna(0)
        return self.model.predict(X)


def main():
    np.random.seed(42)
    n = 500
    dates = pd.date_range(start="2020-01-01", periods=n, freq="B")
    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))
    df = pd.DataFrame({"close": prices}, index=dates)
    df["actual"] = df["close"].astype(float).pct_change().shift(-1)
    df = df.dropna(subset=["actual"])

    optimizer = WalkForwardOptimizer(
        train_days=200,
        val_days=50,
        test_days=50,
        step_size=50,
    )
    windows = optimizer.create_windows(df)
    if not windows:
        logger.error("No windows created")
        return 1

    ensemble = SimpleRidgeEnsemble(n_lags=5, alpha=1.0)
    param_grid = {"alpha": [0.1, 1.0, 10.0]}

    logger.info("Calling optimize_window with param_grid=%s (expect CV logs below)", param_grid)
    result = optimizer.optimize_window(windows[0], df, ensemble, param_grid=param_grid)
    logger.info("Result: val_rmse=%.4f test_rmse=%.4f best_params=%s", result.val_rmse, result.test_rmse, result.best_params)
    return 0


if __name__ == "__main__":
    sys.exit(main())
