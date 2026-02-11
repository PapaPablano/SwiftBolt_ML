"""
Indicator overlay builders for charts.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import pandas as pd


def add_simple_moving_average(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Return a simple moving average series."""
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    return df["close"].rolling(window=window, min_periods=window).mean().rename(f"sma_{window}")


