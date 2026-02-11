"""
XGBoost forecaster: regression on close with KDJ + directional features.

Feature pipeline: indicator_bundle (drop kdj_k/d/j) + calculate_kdj + directional_patterns.
Lazy-imports xgboost so naive runs never load heavy deps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting_lab.models.base import BaseForecaster, OHLCStep


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build feature matrix: indicator_bundle minus KDJ + production KDJ + directional patterns."""
    from forecasting_lab.features.indicators import compute_indicator_bundle
    from forecasting_lab.features.kdj_indicators import calculate_kdj
    from forecasting_lab.features.directional_patterns import (
        detect_engulfing_patterns,
        detect_higher_highs_lows,
        detect_volume_patterns,
    )

    c = df["close"] if "close" in df.columns else pd.Series(dtype=float)
    h = df["high"] if "high" in df.columns else c
    l = df["low"] if "low" in df.columns else c

    bundle = compute_indicator_bundle(c, high=h, low=l)
    bundle = bundle.drop(columns=["kdj_k", "kdj_d", "kdj_j"], errors="ignore")

    kdj = calculate_kdj(df, period=9, k_smooth=3, d_smooth=3)
    eng = detect_engulfing_patterns(df)
    hh = detect_higher_highs_lows(df, lookback=5)
    vol = detect_volume_patterns(df)

    out = pd.concat([bundle, kdj, eng, hh, vol], axis=1)
    return out


class XGBoostForecaster(BaseForecaster):
    """XGBoost regression on close; iterative 1-step prediction for horizon."""

    name = "xgboost"

    def __init__(self):
        self._model = None
        self._feature_cols: list[str] | None = None

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "close",
        horizon: int = 1,
    ) -> None:
        import xgboost as xgb

        X = _build_features(df)
        y = df[target_col]

        valid = X.dropna().index.intersection(y.dropna().index)
        if len(valid) < 20:
            self._model = None
            return

        X_fit = X.loc[valid].astype(float)
        y_fit = y.loc[valid].astype(float)

        self._feature_cols = list(X_fit.columns)
        self._model = xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42)
        self._model.fit(X_fit, y_fit)

    def predict(self, df: pd.DataFrame, horizon: int = 1) -> list[OHLCStep]:
        if self._model is None or self._feature_cols is None:
            last = float(df["close"].iloc[-1]) if len(df) > 0 else 100.0
            return [{"open": last, "high": last, "low": last, "close": last, "volume": 0} for _ in range(horizon)]

        steps: list[OHLCStep] = []
        hist = df.copy()

        for _ in range(horizon):
            X_pred = _build_features(hist)
            X_pred = X_pred[self._feature_cols] if self._feature_cols else X_pred
            row = X_pred.iloc[-1:]

            if row.isna().any().any():
                last = float(hist["close"].iloc[-1])
                steps.append({"open": last, "high": last, "low": last, "close": last, "volume": 0})
                continue

            try:
                c = float(self._model.predict(row)[0])
            except Exception:
                c = float(hist["close"].iloc[-1])

            steps.append({"open": c, "high": c, "low": c, "close": c, "volume": 0})
            new_row = pd.DataFrame(
                [{"open": c, "high": c, "low": c, "close": c, "volume": 0}],
                index=[len(hist)],
            )
            hist = pd.concat([hist, new_row], axis=0)

        return steps
