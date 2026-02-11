"""
Walk-forward splits for Forecasting Lab.

Self-contained; no production imports. Time-ordered train/test splits only.
"""

from typing import Iterator

import pandas as pd


def walk_forward_splits(
    X: pd.DataFrame,
    y: pd.Series,
    train_size: int = 252,
    test_size: int = 21,
    step_size: int = 21,
) -> Iterator[tuple[slice, slice]]:
    """
    Yield (train_slice, test_slice) in time order. No shuffling.

    Args:
        X: Feature DataFrame (rows ordered by time).
        y: Target Series (same index as X).
        train_size: Number of samples in each training window.
        test_size: Number of samples in each test window.
        step_size: Advance by this many samples for the next fold.

    Yields:
        (train_slice, test_slice) where train_slice and test_slice are
        slice objects for indexing X/y (e.g. X.iloc[train_slice]).
    """
    n = len(X)
    if n < train_size + test_size:
        return
    start = 0
    while start + train_size + test_size <= n:
        train_slice = slice(start, start + train_size)
        test_slice = slice(start + train_size, start + train_size + test_size)
        yield train_slice, test_slice
        start += step_size
