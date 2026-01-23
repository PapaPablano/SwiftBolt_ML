"""Feature cache utilities for technical indicators."""

from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd

from src.data.supabase_db import SupabaseDatabase
from src.features.technical_indicators import add_technical_features

DEFAULT_TIMEFRAMES = ["m15", "h1", "h4", "d1", "w1"]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _cache_window() -> timedelta:
    try:
        minutes = int(os.getenv("FEATURE_CACHE_MINUTES", "30"))
    except Exception:
        minutes = 30
    return timedelta(minutes=max(1, minutes))


def _is_cache_fresh(df: pd.DataFrame, since_ts: pd.Timestamp) -> bool:
    if df.empty:
        return False
    if "created_at" in df.columns:
        created_at = pd.to_datetime(df["created_at"], errors="coerce")
        if created_at.notna().any() and created_at.max() >= since_ts:
            return True
    return False


def fetch_or_build_features(
    *,
    db: SupabaseDatabase,
    symbol: str,
    timeframes: list[str] | None = None,
    limits: dict[str, int] | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch cached features or compute and store for requested timeframes."""
    tfs = timeframes or DEFAULT_TIMEFRAMES
    limit_map = limits or {}
    symbol_id = db.get_symbol_id(symbol)
    since_ts = pd.Timestamp.now('UTC') - _cache_window()
    results: dict[str, pd.DataFrame] = {}

    for timeframe in tfs:
        limit = limit_map.get(timeframe)
        cached = db.fetch_indicator_values(symbol_id, timeframe, limit=limit)
        if _bool_env("ENABLE_FEATURE_CACHE", default=True) and _is_cache_fresh(
            cached,
            since_ts,
        ):
            results[timeframe] = cached
            continue

        ohlc = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=limit)
        if ohlc.empty:
            results[timeframe] = ohlc
            continue

        features = add_technical_features(ohlc)
        if _bool_env("ENABLE_FEATURE_CACHE", default=True):
            db.upsert_indicator_values(symbol_id, timeframe, features)
        results[timeframe] = features

    return results
