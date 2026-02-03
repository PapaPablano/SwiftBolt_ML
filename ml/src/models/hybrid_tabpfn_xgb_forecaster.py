"""
Hybrid TabPFN + XGBoost forecaster: meta-model ensemble for binary (bullish/bearish) prediction.

Same API as XGBoostForecaster: prepare_training_data_binary, train(X,y), predict_batch(X).
Combines XGBoost and TabPFN probabilities: p_hybrid = alpha * p_xgb + (1 - alpha) * p_tab.
"""

import logging
import os
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.models.xgboost_forecaster import XGBoostForecaster

logger = logging.getLogger(__name__)

try:
    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion
    TABPFN_AVAILABLE = True
except ImportError:
    TABPFN_AVAILABLE = False
    TabPFNClassifier = None
    ModelVersion = None


def _create_tabpfn_classifier(n_estimators: int = 8):
    """Use V2 (non-gated) when HF_TOKEN is unset so Docker works without HuggingFace login."""
    if os.environ.get("HF_TOKEN"):
        return TabPFNClassifier(device="cpu", n_estimators=n_estimators)
    return TabPFNClassifier.create_default_for_version(ModelVersion.V2)


# TabPFN has a ~1000 training sample limit
TABPFN_MAX_TRAIN = 1000


class HybridTabPFN_XGBForecaster:
    """
    Hybrid ensemble: XGBoost + TabPFN on the same features.
    Uses alpha in [0,1] to blend probabilities; default alpha=0.5.
    """

    def __init__(self, alpha: float = 0.5, tabpfn_ensemble: int = 8) -> None:
        if not TABPFN_AVAILABLE:
            raise ImportError(
                "TabPFN not installed. Install with: pip install tabpfn"
            )
        self.alpha = alpha
        self.tabpfn_ensemble = tabpfn_ensemble
        self.xgb = XGBoostForecaster()
        self.tabpfn: Optional[TabPFNClassifier] = None
        self.feature_columns: list[str] = []
        self.is_trained = False

    def prepare_training_data_binary(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
        sentiment_series: Optional[Any] = None,
        threshold_pct: float = 0.005,
        add_simple_regime: bool = False,
    ) -> tuple:
        """Same signature as XGBoostForecaster; delegates to XGBoost feature pipeline."""
        return self.xgb.prepare_training_data_binary(
            df,
            horizon_days=horizon_days,
            sentiment_series=sentiment_series,
            threshold_pct=threshold_pct,
            add_simple_regime=add_simple_regime,
        )

    def train(
        self,
        X: pd.DataFrame,
        y: Any,
        min_samples: Optional[int] = None,
        feature_names: Any = None,
    ) -> None:
        """Train both XGBoost and TabPFN on the same (X, y)."""
        if min_samples is not None and len(X) < min_samples:
            raise ValueError(
                f"Insufficient training data: {len(X)} < {min_samples}"
            )
        # Train XGBoost (sets xgb.feature_columns)
        self.xgb.train(X, y, min_samples=min_samples, feature_names=feature_names)
        self.feature_columns = self.xgb.feature_columns

        # TabPFN: convert y to 0/1, cap training size
        y_num = np.where(np.asarray(y).ravel() == "bullish", 1, 0)
        X_num = X[self.feature_columns].fillna(0).to_numpy(dtype=np.float32)
        if len(X_num) > TABPFN_MAX_TRAIN:
            X_num = X_num[-TABPFN_MAX_TRAIN:]
            y_num = y_num[-TABPFN_MAX_TRAIN:]
            logger.info(
                "TabPFN: using last %d samples (limit %d)",
                TABPFN_MAX_TRAIN,
                TABPFN_MAX_TRAIN,
            )
        self.tabpfn = _create_tabpfn_classifier(n_estimators=self.tabpfn_ensemble)
        self.tabpfn.fit(X_num, y_num)
        self.is_trained = True

    def predict_proba(self, X: Any) -> np.ndarray:
        """Combined probability of class 1 (bullish)."""
        if not self.is_trained or self.tabpfn is None:
            raise RuntimeError("Model not trained. Call train() first.")
        p_xgb = self.xgb.predict_proba(X)
        if isinstance(X, pd.DataFrame):
            X_num = X.reindex(columns=self.feature_columns).fillna(0).to_numpy(dtype=np.float32)
        else:
            X_num = np.asarray(X, dtype=np.float32)
            if X_num.ndim == 1:
                X_num = X_num.reshape(1, -1)
        p_tab = self.tabpfn.predict_proba(X_num)[:, 1]
        return self.alpha * p_xgb + (1.0 - self.alpha) * p_tab

    def predict_batch(self, X: Any) -> np.ndarray:
        """Predict labels (bullish/bearish) from hybrid probability."""
        proba = self.predict_proba(X)
        return np.where(proba >= 0.5, "bullish", "bearish")
