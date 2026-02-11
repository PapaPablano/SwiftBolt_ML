from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_kdj(
    df: pd.DataFrame,
    period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
    include_divergence: bool = True,
    include_position: bool = True,
) -> pd.DataFrame:
    if not {"high", "low", "close"}.issubset(df.columns):
        raise ValueError("calculate_kdj requires df columns: high, low, close")

    low_min = df["low"].rolling(window=period).min()
    high_max = df["high"].rolling(window=period).max()
    denom = (high_max - low_min).where((high_max - low_min) != 0, np.nan)
    rsv = 100.0 * (df["close"] - low_min) / denom

    k_line = rsv.ewm(span=k_smooth).mean()
    d_line = k_line.ewm(span=d_smooth).mean()
    j_line = 3.0 * k_line - 2.0 * d_line

    out = pd.DataFrame(index=df.index)
    out["kdj_k"] = k_line
    out["kdj_d"] = d_line
    out["kdj_j"] = j_line
    if include_divergence:
        out["j_minus_d"] = j_line - d_line
    if include_position:
        out["j_above_d"] = (j_line > d_line).astype(float)

    return out.shift(1)
