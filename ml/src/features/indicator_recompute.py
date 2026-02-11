"""
Recompute technical indicators on (history + predicted bars) for L1 forecast points.

Used by the production L1 pipeline: after predicting path points (value/lower/upper per step),
we concatenate history bars with predicted bars (synthetic OHLC when only close is available),
recompute RSI, MACD, Bollinger, KDJ on the full series, then attach per-step indicator
values to each forecast point so chart and downstream consumers get enriched points.

See: L1 15m Forecast Pipeline plan, Chart Intraday and Production L1 Writer plan.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.features.technical_indicators_corrected import TechnicalIndicatorsCorrect

logger = logging.getLogger(__name__)

# Indicator keys we attach to forecast points (blueprint / chart contract).
INDICATOR_KEYS = [
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "kdj_k",
    "kdj_d",
    "kdj_j",
]


def _ensure_ohlc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure open, high, low, close exist; derive high/low from open/close if missing."""
    df = df.copy()
    if "close" not in df.columns and "value" in df.columns:
        df["close"] = df["value"]
    if "open" not in df.columns:
        df["open"] = df["close"].shift(1).bfill().fillna(df["close"].iloc[0])
    if "high" not in df.columns:
        df["high"] = df[["open", "close"]].max(axis=1)
    if "low" not in df.columns:
        df["low"] = df[["open", "close"]].min(axis=1)
    return df


def recompute_indicators_on_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recompute RSI, MACD, Bollinger, and KDJ on a full OHLC series (history + predicted).

    Requires DataFrame with open, high, low, close. Adds columns used by
    attach_indicators_to_forecast_points. First bars may have NaN for indicators
    (lookback); callers use last valid or leave null for predicted steps when needed.

    Args:
        df: DataFrame with open, high, low, close (and optionally volume).

    Returns:
        DataFrame with added columns: rsi_14, macd, macd_signal, macd_hist,
        bb_upper, bb_middle, bb_lower, kdj_k, kdj_d, kdj_j.
    """
    df = _ensure_ohlc_columns(df)
    tic = TechnicalIndicatorsCorrect

    # RSI (close-only)
    df["rsi_14"] = tic.calculate_rsi(df["close"], period=14)

    # MACD (close-only)
    macd_line, signal_line, hist = tic.calculate_macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = hist

    # Bollinger (close-based)
    df = tic.calculate_bollinger_bands(
        df, period=20, std_dev=2.0, use_population_std=True, include_ttm_squeeze=False
    )

    # KDJ (requires high, low, close)
    df = tic.calculate_kdj_correct(df, period=9, k_smooth=5, d_smooth=5)

    return df


def _points_to_ohlc_df(points: list[dict], last_close: float) -> pd.DataFrame:
    """Build a DataFrame with open, high, low, close from forecast points (value = close)."""
    rows = []
    prev_close = last_close
    for p in points:
        close = float(p.get("value", p.get("close", 0)))
        open_ = prev_close
        high = max(open_, close)
        low = min(open_, close)
        rows.append({"open": open_, "high": high, "low": low, "close": close})
        prev_close = close
    return pd.DataFrame(rows)


def _history_to_ohlc_df(history_df: pd.DataFrame) -> pd.DataFrame:
    """Extract or derive open, high, low, close from history bars."""
    df = history_df.copy()
    required = ["open", "high", "low", "close"]
    if all(c in df.columns for c in required):
        return df[required]
    if "close" in df.columns:
        df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
        df["high"] = df[["open", "close"]].max(axis=1)
        df["low"] = df[["open", "close"]].min(axis=1)
        return df[["open", "high", "low", "close"]]
    raise ValueError("history_df must have open/high/low/close or at least close")


def attach_indicators_to_forecast_points(
    history_df: pd.DataFrame,
    points: list[dict],
    *,
    volume_default: float = 0.0,
) -> list[dict]:
    """
    Attach OHLC and recomputed indicators to each forecast point.

    Concatenates history bars with predicted steps (synthetic OHLC: open=prev_close,
    high/low from open/close, close=value), recomputes RSI, MACD, Bollinger, KDJ on
    the full series, then for each predicted step reads off indicator values and
    sets point["indicators"] and point["ohlc"].

    Args:
        history_df: DataFrame with open, high, low, close (and optionally volume).
        points: List of forecast point dicts with at least "value" (close).
        volume_default: Volume for predicted bars when not present.

    Returns:
        New list of point dicts with "ohlc" and "indicators" added (and existing
        keys preserved). If recompute fails or points are empty, returns points
        unchanged (no indicators).
    """
    if not points:
        return []
    try:
        hist_ohlc = _history_to_ohlc_df(history_df)
        last_close = float(hist_ohlc["close"].iloc[-1])
        pred_ohlc = _points_to_ohlc_df(points, last_close)
        combined = pd.concat([hist_ohlc, pred_ohlc], ignore_index=True)
        combined = recompute_indicators_on_series(combined)
    except Exception as e:
        logger.warning("Indicator recompute failed, returning points without indicators: %s", e)
        return [dict(p) for p in points]

    n_hist = len(hist_ohlc)
    result = []
    for i, p in enumerate(points):
        out = dict(p)
        row = combined.iloc[n_hist + i]
        # Attach OHLC for this step
        out["ohlc"] = {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(p.get("volume", volume_default)),
        }
        # Attach indicators (only non-NaN)
        ind = {}
        for k in INDICATOR_KEYS:
            if k in row and pd.notna(row[k]):
                ind[k] = round(float(row[k]), 4)
        if ind:
            out["indicators"] = ind
        result.append(out)
    return result
