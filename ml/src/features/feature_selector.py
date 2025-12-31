"""
Feature selection utilities for the SwiftBolt ML pipeline.

Implements a lightweight wrapper around scikit-learn selectors to keep our
feature set compact and horizon-aware. Defaults to mutual information ranking,
which performs well on non-linear, noisy financial data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, mutual_info_classif, mutual_info_regression


def _sanitize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Replace inf/NaN values to keep sklearn selectors happy."""
    cleaned = df.replace([np.inf, -np.inf], np.nan)
    return cleaned.fillna(0.0)


@dataclass
class FeatureSelector:
    """
    Wrapper around SelectKBest mutual information selector.

    Args:
        max_features: Maximum number of features to keep.
        cv_splits: Placeholder for future CV-based selectors (kept for config parity).
        mode: 'classification' or 'regression'.
    """

    max_features: int = 40
    cv_splits: int = 5
    mode: str = "classification"
    selected_features: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.selector: SelectKBest | None = None

    def fit(self, X: pd.DataFrame, y: Sequence) -> "FeatureSelector":
        """
        Fit selector on provided dataset.

        Returns:
            self
        """
        if X.empty:
            self.selected_features = []
            return self

        sanitized = _sanitize_frame(X)
        k = min(self.max_features, sanitized.shape[1])
        score_func = (
            mutual_info_classif if self.mode == "classification" else mutual_info_regression
        )
        self.selector = SelectKBest(score_func=score_func, k=k)
        self.selector.fit(sanitized, y)
        mask = self.selector.get_support()
        self.selected_features = sanitized.columns[mask].tolist()
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame restricted to previously selected features."""
        if not self.selected_features:
            return X
        transformed = X.copy()
        for feature in self.selected_features:
            if feature not in transformed.columns:
                transformed[feature] = 0.0
        return transformed[self.selected_features]

    def fit_transform(self, X: pd.DataFrame, y: Sequence) -> pd.DataFrame:
        """Convenience helper."""
        return self.fit(X, y).transform(X)

    def get_support(self) -> Iterable[str]:
        """Expose selected feature names."""
        return self.selected_features
