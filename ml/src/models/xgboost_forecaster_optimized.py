"""
XGBoost forecaster with automatic top-k feature selection to reduce overfitting.

Same API as XGBoostForecaster; uses a quick initial fit to select top features
by importance, then trains the final model on selected features only.
"""

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.models.xgboost_forecaster import XGBoostForecaster
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

# Default number of features to keep (avoids 68 features on 200+ samples)
TOP_K_FEATURES = 30


class XGBoostForecasterOptimized(XGBoostForecaster):
    """XGBoost with automatic feature selection (top-k by importance)."""

    def __init__(self, top_k: int = TOP_K_FEATURES) -> None:
        super().__init__()
        self.top_k = top_k
        self._selected_idx: Optional[np.ndarray] = None

    def train(
        self,
        X: pd.DataFrame,
        y: Any,
        min_samples: Optional[int] = None,
        feature_names: Any = None,
    ) -> None:
        """Train with feature selection: quick model -> select top-k -> train final model."""
        if min_samples is not None and len(X) < min_samples:
            raise ValueError(
                f"Insufficient training data: {len(X)} < {min_samples}"
            )
        numeric_cols = [
            c for c in X.columns
            if X[c].dtype in ("float64", "float32", "int64", "int32")
        ]
        if not numeric_cols:
            numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        self.feature_columns = numeric_cols
        X_num = X[numeric_cols].fillna(0)
        X_scaled = self.scaler.fit_transform(X_num)
        y_arr = np.asarray(y).ravel()
        y_bin = np.where(np.asarray(y_arr) == "bullish", 1, 0)

        # Step 1: Quick model to get feature importance
        temp_model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
            eval_metric="logloss",
        )
        temp_model.fit(X_scaled, y_bin)
        importances = temp_model.feature_importances_
        n_keep = min(self.top_k, len(numeric_cols))
        # Indices of top n_keep features (descending importance)
        self._selected_idx = np.argsort(importances)[::-1][:n_keep]

        # Step 2: Train final model on selected features (keep full feature_columns for scaler at predict)
        X_selected = X_scaled[:, self._selected_idx]
        logger.info(
            "Selected %s features from %s",
            X_selected.shape[1],
            len(numeric_cols),
        )
        self.model.fit(X_selected, y_bin)
        self.is_trained = True

    def predict_batch(self, X: Any) -> np.ndarray:
        """Predict using selected features only."""
        if not self.is_trained or self._selected_idx is None:
            raise RuntimeError("Model not trained. Call train() first.")
        if isinstance(X, pd.DataFrame):
            cols = [c for c in self.feature_columns if c in X.columns]
            X_num = X[cols].reindex(columns=self.feature_columns).fillna(0)
        else:
            X_num = np.asarray(X)
            if X_num.ndim == 1:
                X_num = X_num.reshape(1, -1)
        X_scaled = self.scaler.transform(X_num)
        X_selected = X_scaled[:, self._selected_idx]
        pred_bin = self.model.predict(X_selected)
        return np.where(pred_bin == 1, "bullish", "bearish")
