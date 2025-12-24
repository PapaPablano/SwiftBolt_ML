"""
Market regime detection using HMM on returns/vol features.
Produces discrete regimes and smoothed probabilities for feature use.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Fit a Gaussian HMM on returns and volatility proxy to infer regimes.
    Regimes are encoded as integers [0..n_states-1]; we also return
    smoothed probabilities per state.
    """

    def __init__(
        self,
        n_states: int = 3,
        covariance_type: str = "full",
        random_state: int = 42,
    ) -> None:
        self.n_states = n_states
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type=covariance_type,
            random_state=random_state,
            n_iter=200,
        )
        self.is_fitted = False

    def _build_features(self, df: pd.DataFrame) -> np.ndarray:
        # Daily returns and rolling volatility as proxies
        returns = df["close"].pct_change().fillna(0.0)
        vol = (
            returns.rolling(window=20, min_periods=5)
            .std()
            .bfill()
        )
        feats = np.column_stack([returns.values, vol.values])
        return feats

    def fit(self, df: pd.DataFrame) -> None:
        feats = self._build_features(df)
        try:
            self.model.fit(feats)
            self.is_fitted = True
            logger.info("HMM fitted on %s samples", len(df))
        except Exception as exc:  # noqa: BLE001
            logger.warning("HMM fitting failed: %s", exc)
            self.is_fitted = False

    def transform(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns:
            regimes: array of most likely regime per row
            probs: array of shape (len, n_states) with regime probabilities
        """
        if not self.is_fitted:
            self.fit(df)
        feats = self._build_features(df)
        regimes = self.model.predict(feats)
        probs = self.model.predict_proba(feats)
        return regimes, probs


def add_market_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append HMM regime features to the OHLC dataframe.
    Adds:
      - hmm_regime (int)
      - hmm_regime_prob_{k} for each state
    """
    detector = MarketRegimeDetector()
    regimes, probs = detector.transform(df)

    out = df.copy()
    out["hmm_regime"] = regimes
    for k in range(detector.n_states):
        out[f"hmm_regime_prob_{k}"] = probs[:, k]
    return out
