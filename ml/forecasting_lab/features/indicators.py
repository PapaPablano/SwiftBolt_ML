"""
Pure technical indicator functions for Forecasting Lab.

No side effects; no production deps. Same definitions as production (e.g. technical_indicators_corrected)
so UI and evaluation stay stable. Input/output are arrays or Series; no DataFrame mutation.
"""

import numpy as np
import pandas as pd
from typing import Tuple

# Standard parameters (align with production)
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0
KDJ_PERIOD = 9
KDJ_K_SMOOTH = 5
KDJ_D_SMOOTH = 5


def rsi(close: pd.Series | np.ndarray, period: int = RSI_PERIOD) -> pd.Series:
    """
    RSI (Relative Strength Index). Wilder-style: EMA smoothing of gains/losses.
    Returns values 0–100; NaN until enough history.
    """
    s = pd.Series(close).astype(float)
    delta = s.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    avg_gain = gains.ewm(span=period, adjust=False).mean()
    avg_loss = losses.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    close: pd.Series | np.ndarray,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD line, signal line, histogram. Standard: EMA(12)-EMA(26), signal=EMA(9) of MACD.
    Returns (macd, macd_signal, macd_hist).
    """
    s = pd.Series(close).astype(float)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist_line = macd_line - macd_signal_line
    return macd_line, macd_signal_line, macd_hist_line


def bollinger(
    close: pd.Series | np.ndarray,
    period: int = BB_PERIOD,
    std_dev: float = BB_STD,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands: middle = SMA(period), upper = middle + k*std, lower = middle - k*std.
    Returns (bb_upper, bb_mid, bb_lower).
    """
    s = pd.Series(close).astype(float)
    mid = s.rolling(window=period).mean()
    std = s.rolling(window=period).std(ddof=0)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def kdj(
    high: pd.Series | np.ndarray,
    low: pd.Series | np.ndarray,
    close: pd.Series | np.ndarray,
    period: int = KDJ_PERIOD,
    k_smooth: int = KDJ_K_SMOOTH,
    d_smooth: int = KDJ_D_SMOOTH,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    KDJ (stochastic). RSV = (close - min) / (max - min) * 100; K = EMA(RSV); D = EMA(K); J = 3K - 2D.
    Returns (kdj_k, kdj_d, kdj_j).
    """
    h = pd.Series(high).astype(float)
    l = pd.Series(low).astype(float)
    c = pd.Series(close).astype(float)
    lowest = l.rolling(window=period, min_periods=1).min()
    highest = h.rolling(window=period, min_periods=1).max()
    rng = (highest - lowest).replace(0, np.nan)
    rsv = 100 * (c - lowest) / rng
    k_line = rsv.ewm(span=k_smooth, adjust=False).mean()
    d_line = k_line.ewm(span=d_smooth, adjust=False).mean()
    j_line = 3 * k_line - 2 * d_line
    return k_line, d_line, j_line


def compute_indicator_bundle(
    close: np.ndarray | pd.Series,
    high: np.ndarray | pd.Series | None = None,
    low: np.ndarray | pd.Series | None = None,
) -> pd.DataFrame:
    """
    Compute RSI, MACD, Bollinger, KDJ on the given series. Pure function; returns a DataFrame
    with columns: rsi_14, macd, macd_signal, macd_hist, bb_upper, bb_mid, bb_lower, kdj_k, kdj_d, kdj_j.
    high/low optional; if missing, KDJ uses close for high/low (degrades gracefully).
    """
    c = pd.Series(close).astype(float)
    h = pd.Series(high).astype(float) if high is not None else c
    l = pd.Series(low).astype(float) if low is not None else c

    out = pd.DataFrame(index=c.index)
    out["rsi_14"] = rsi(c, RSI_PERIOD)
    macd_line, macd_sig, macd_hist = macd(c, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    out["macd"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    bb_u, bb_m, bb_l = bollinger(c, BB_PERIOD, BB_STD)
    out["bb_upper"] = bb_u
    out["bb_mid"] = bb_m
    out["bb_lower"] = bb_l
    kk, kd, kj = kdj(h, l, c, KDJ_PERIOD, KDJ_K_SMOOTH, KDJ_D_SMOOTH)
    out["kdj_k"] = kk
    out["kdj_d"] = kd
    out["kdj_j"] = kj
    return out


# Names for the indicator forecast bundle (for storage / mlforecasts.points JSONB alignment)
INDICATOR_KEYS = [
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_mid", "bb_lower",
    "kdj_k", "kdj_d", "kdj_j",
]
