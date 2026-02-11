from __future__ import annotations

import pandas as pd


def detect_engulfing_patterns(df: pd.DataFrame) -> pd.DataFrame:
    if not {"open", "close"}.issubset(df.columns):
        raise ValueError("detect_engulfing_patterns requires df columns: open, close")

    prev_open = df["open"].shift(1)
    prev_close = df["close"].shift(1)

    bullish = (
        (df["close"] > df["open"])
        & (prev_close < prev_open)
        & (df["open"] < prev_close)
        & (df["close"] > prev_open)
    ).astype(float)

    bearish = (
        (df["close"] < df["open"])
        & (prev_close > prev_open)
        & (df["open"] > prev_close)
        & (df["close"] < prev_open)
    ).astype(float)

    out = pd.DataFrame(index=df.index)
    out["bullish_engulfing"] = bullish
    out["bearish_engulfing"] = bearish
    return out.shift(1)


def detect_higher_highs_lows(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    if not {"high", "low"}.issubset(df.columns):
        raise ValueError("detect_higher_highs_lows requires df columns: high, low")

    prev_max_high = df["high"].rolling(lookback).max().shift(1)
    prev_min_low = df["low"].rolling(lookback).min().shift(1)

    out = pd.DataFrame(index=df.index)
    out["higher_high"] = (df["high"] > prev_max_high).astype(float)
    out["higher_low"] = (df["low"] > prev_min_low).astype(float)
    out["lower_high"] = (df["high"] < prev_max_high).astype(float)
    out["lower_low"] = (df["low"] < prev_min_low).astype(float)
    return out.shift(1)


def detect_volume_patterns(df: pd.DataFrame) -> pd.DataFrame:
    if "volume" not in df.columns:
        return pd.DataFrame(index=df.index)

    vol_ma20 = df["volume"].rolling(20).mean()
    out = pd.DataFrame(index=df.index)
    out["volume_surge"] = (df["volume"] > vol_ma20 * 1.5).astype(float)
    out["volume_spike"] = (df["volume"] > vol_ma20 * 2.0).astype(float)

    if {"open", "close"}.issubset(df.columns):
        price_up = df["close"] > df["open"]
        price_down = df["close"] < df["open"]
        volume_up = df["volume"] > df["volume"].shift(1)
        out["bullish_volume"] = (price_up & volume_up).astype(float)
        out["bearish_volume"] = (price_down & volume_up).astype(float)

    return out.shift(1)
