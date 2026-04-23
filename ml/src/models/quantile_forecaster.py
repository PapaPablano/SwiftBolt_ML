"""
Quantile regression forecaster using XGBoost with pinball loss.

Produces prediction intervals (e.g. q10..q90) rather than point forecasts,
enabling calibration evaluation and uncertainty quantification.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from xgboost import XGBRegressor

from src.features.temporal_indicators import compute_simplified_features

logger = logging.getLogger(__name__)

# Minimum training samples required for reliable quantile regression
MIN_TRAINING_SAMPLES = 50

# Lookback rows consumed by feature engineering (lags, supertrend, etc.)
_FEATURE_LOOKBACK = 50


class QuantileForecaster:
    """
    XGBoost quantile regression forecaster.

    Trains one XGBRegressor per quantile using ``reg:quantileerror`` objective,
    then enforces monotonicity across quantiles at prediction time.

    Parameters
    ----------
    horizon : str
        Forecast horizon label, e.g. ``"5D"``.
    quantiles : list[float] | None
        Quantile levels to model. Defaults to ``[0.1, 0.25, 0.5, 0.75, 0.9]``.
    """

    # Maps quantile float to human-readable key used in output dicts
    _Q_LABELS = {0.1: "q10", 0.25: "q25", 0.5: "q50", 0.75: "q75", 0.9: "q90"}

    def __init__(
        self,
        horizon: str = "5D",
        quantiles: Optional[list[float]] = None,
    ) -> None:
        self.horizon = horizon
        self.quantiles = quantiles or [0.1, 0.25, 0.5, 0.75, 0.9]
        self.quantiles.sort()

        self.models: dict[float, XGBRegressor] = {}
        self.scaler = RobustScaler()
        self.feature_columns: list[str] = []
        self.is_trained = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        df: pd.DataFrame,
        horizon_days: int = 5,
    ) -> bool:
        """
        Train one XGBoost model per quantile on *return* targets.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame with at least ``close`` column, sorted by date ascending.
        horizon_days : int
            Number of trading days ahead for the target return.

        Returns
        -------
        bool
            ``True`` if training succeeded, ``False`` otherwise.
        """
        try:
            X, y = self._prepare_data(df, horizon_days)
        except ValueError as exc:
            logger.warning("QuantileForecaster.train skipped: %s", exc)
            return False

        if X is None or y is None:
            return False

        if len(X) < MIN_TRAINING_SAMPLES:
            logger.warning(
                "QuantileForecaster.train: insufficient data (%d < %d)",
                len(X),
                MIN_TRAINING_SAMPLES,
            )
            return False

        # Store feature columns for prediction alignment
        self.feature_columns = X.columns.tolist()

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Temporal train/val split (80/20) for early stopping — no shuffle
        split_idx = max(1, min(int(len(X_scaled) * 0.8), len(X_scaled) - 1))
        X_tr, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        y_tr, y_val = y.values[:split_idx], y.values[split_idx:]

        for q in self.quantiles:
            model = XGBRegressor(
                n_estimators=500,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                gamma=0.1,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                objective="reg:quantileerror",
                quantile_alpha=q,
            )
            model.fit(
                X_tr,
                y_tr,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            self.models[q] = model
            label = self._q_label(q)
            logger.info(
                "QuantileForecaster(%s) trained %s (best_iter=%s)",
                self.horizon,
                label,
                getattr(model, "best_iteration", "N/A"),
            )

        self.is_trained = True
        return True

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, df: pd.DataFrame) -> Optional[dict[str, float]]:
        """
        Predict quantile values for the most recent row of *df*.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame (same schema as training input). Features are
            computed internally; the prediction is for the **last** row.

        Returns
        -------
        dict[str, float] | None
            Mapping like ``{"q10": 145.2, "q25": 147.0, ...}`` with one
            entry per quantile, or ``None`` if prediction fails.
        """
        if not self.is_trained:
            logger.error("QuantileForecaster.predict called before training.")
            return None

        try:
            X = self._prepare_features(df)
        except ValueError as exc:
            logger.warning("QuantileForecaster.predict skipped: %s", exc)
            return None

        if X is None or X.empty:
            return None

        # Use last row for the forecast
        X_last = X.iloc[[-1]]

        # Align to training columns, fill missing with 0
        X_aligned = X_last.reindex(columns=self.feature_columns, fill_value=0)

        # Check for NaN — bail if the feature row is entirely NaN
        if X_aligned.isna().all(axis=1).iloc[0]:
            logger.warning("QuantileForecaster.predict: all features NaN, returning None")
            return None

        X_aligned = X_aligned.fillna(0)
        X_scaled = self.scaler.transform(X_aligned)

        raw: dict[float, float] = {}
        for q, model in self.models.items():
            raw[q] = float(model.predict(X_scaled)[0])

        # Enforce monotonicity via post-hoc sort
        sorted_vals = sorted(raw.values())
        result: dict[str, float] = {}
        for q_float, val in zip(sorted(raw.keys()), sorted_vals):
            result[self._q_label(q_float)] = val

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prepare_data(
        self,
        df: pd.DataFrame,
        horizon_days: int,
    ) -> tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """Compute features and forward-return target. Returns (X, y) or raises ValueError."""
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column")

        df = df.copy().sort_index()

        # Target: forward percentage return over horizon_days
        df["_target_return"] = df["close"].pct_change(periods=horizon_days).shift(-horizon_days)

        # Compute technical features
        df = compute_simplified_features(df)

        # Drop rows consumed by lookback and forward target
        df = df.iloc[_FEATURE_LOOKBACK:]
        df = df.dropna(subset=["_target_return"])

        if df.empty:
            raise ValueError("No valid rows after feature engineering + target creation")

        y = df["_target_return"]
        X = df.select_dtypes(include=["number"]).drop(columns=["_target_return"], errors="ignore")

        # Drop any remaining infinite values
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

        return X, y

    def _prepare_features(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Compute features for prediction (no target needed)."""
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column")

        df = df.copy().sort_index()
        df = compute_simplified_features(df)
        df = df.iloc[_FEATURE_LOOKBACK:]

        if df.empty:
            return None

        X = df.select_dtypes(include=["number"])
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        return X

    def _q_label(self, q: float) -> str:
        """Return human-readable label for a quantile, e.g. 0.1 -> 'q10'."""
        if q in self._Q_LABELS:
            return self._Q_LABELS[q]
        return f"q{int(q * 100)}"
