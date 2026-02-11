from __future__ import annotations

from typing import Iterator
import pandas as pd


def purged_walk_forward_splits(
    X: pd.DataFrame,
    y: pd.Series,
    train_size: int = 252,
    test_size: int = 21,
    step_size: int = 21,
    embargo_pct: float = 0.05,
) -> Iterator[tuple[slice, slice]]:
    """
    Drop-in replacement for walk_forward_splits (same signature + embargo_pct). [cite:187]
    """
    n = len(X)
    if n < train_size + test_size:
        return

    embargo = max(0, int(test_size * embargo_pct))
    start = 0
    while start + train_size + test_size <= n:
        train_slice = slice(start, start + train_size)
        test_slice = slice(start + train_size, start + train_size + test_size)
        yield train_slice, test_slice

        next_start = start + step_size
        min_start = (test_slice.stop or 0) + embargo
        start = max(next_start, min_start)
