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

# Lower bound on std dev to avoid division by zero when features are flat.
# Tuned small to preserve scale while still preventing singular covariances.
_MIN_STD = 1e-6
# Tiny jitter keeps covariance matrices positive-definite without materially
# altering the signal; deterministic via class RNG for reproducibility.
_JITTER_SCALE = 1e-6


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
        self.random_state = random_state
        self._rng = np.random.default_rng(random_state)
        self._feature_mean = None
        self._feature_std = None
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type=covariance_type,
            random_state=random_state,
            n_iter=200,
        )
        self.is_fitted = False

    def _build_features(
        self,
        df: pd.DataFrame,
        mean: np.ndarray | None = None,
        std: np.ndarray | None = None,
        apply_jitter: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Daily returns and rolling volatility as proxies
        returns = df["close"].pct_change().fillna(0.0)
        vol = returns.rolling(window=20, min_periods=5).std().bfill()
        feats = np.column_stack([returns.values, vol.values])

        # Replace non-finite values and standardize to avoid near-singular covariances
        feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
        if mean is None:
            mean = feats.mean(axis=0)
        if std is None:
            std = np.clip(feats.std(axis=0), _MIN_STD, None)
        feats = (feats - mean) / std

        # Small jitter to ensure positive-definite covariance (required by HMM);
        # flat features produce singular matrices without this.
        if apply_jitter:
            feats = feats + self._rng.normal(scale=_JITTER_SCALE, size=feats.shape)
        return feats.astype(float), mean, std

    def fit(self, df: pd.DataFrame) -> None:
        feats, mean, std = self._build_features(df, apply_jitter=True)
        self._feature_mean = mean
        self._feature_std = std
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
        if not self.is_fitted:
            # Fit failed; return stable defaults to keep pipeline running.
            # All samples get regime 0 with uniform probabilities so downstream
            # code can still proceed deterministically.
            return self._fallback_predictions(len(df))

        feats, _, _ = self._build_features(df, mean=self._feature_mean, std=self._feature_std)
        regimes = self.model.predict(feats)
        probs = self.model.predict_proba(feats)
        return regimes, probs

    def _fallback_predictions(self, length: int) -> Tuple[np.ndarray, np.ndarray]:
        logger.info("Using fallback HMM regimes for length=%s", length)
        regimes = np.zeros(length, dtype=int)
        uniform_prob = 1.0 / self.n_states
        probs = np.full((length, self.n_states), uniform_prob)
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
