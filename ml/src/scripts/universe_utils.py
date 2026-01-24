"""Shared helpers for resolving the ML processing universe."""

from __future__ import annotations

import logging
import os
from typing import Iterable, Sequence

from src.data.supabase_db import db
from src.features.multi_timeframe import DEFAULT_TIMEFRAMES

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_SYMBOLS: list[str] = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "SPY",
    "QQQ",
]


def _extract_tickers(rows: Iterable[dict]) -> list[str]:
    tickers: set[str] = set()
    for row in rows:
        symbol_info = row.get("symbol_id") if isinstance(row, dict) else None
        ticker = (
            symbol_info.get("ticker")
            if isinstance(symbol_info, dict)
            else None
        )
        if ticker:
            tickers.add(ticker.upper())
    return sorted(tickers)


def fetch_watchlist_symbols() -> list[str]:
    """Fetch the current unique tickers from all watchlists."""

    try:
        # Try to fetch watchlist items - use added_at (correct column name)
        try:
            response = (
                db.client.table("watchlist_items")
                .select("symbol_id(ticker)")
                .order("added_at", desc=True)
                .execute()
            )
        except Exception as order_error:
            # If added_at doesn't exist, try created_at, then fetch without ordering
            try:
                logger.debug("added_at column not available, trying created_at: %s", order_error)
                response = (
                    db.client.table("watchlist_items")
                    .select("symbol_id(ticker)")
                    .order("created_at", desc=True)
                    .execute()
                )
            except Exception:
                # If neither exists, fetch without ordering
                logger.debug("No timestamp column available, fetching without order")
                response = (
                    db.client.table("watchlist_items")
                    .select("symbol_id(ticker)")
                    .execute()
                )
        
        rows = response.data or []
        if not rows:
            logger.info("No watchlist rows returned; falling back to defaults")
            return []
        return _extract_tickers(rows)
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning("Unable to fetch watchlist symbols: %s", exc)
        return []


def resolve_symbol_list(fallback: Sequence[str] | None = None) -> list[str]:
    """Return the preferred symbol list, falling back when necessary."""

    symbols_env = os.getenv("INPUT_SYMBOLS", "").strip()
    if symbols_env:
        return [s.strip().upper() for s in symbols_env.split(",") if s.strip()]

    symbols = fetch_watchlist_symbols()
    if symbols:
        return symbols
    return list(fallback or DEFAULT_FALLBACK_SYMBOLS)


def resolve_timeframe_list(
    fallback: Sequence[str] | None = None,
) -> list[str]:
    """Return timeframes honoring INPUT_TIMEFRAMES when provided."""

    tf_env = os.getenv("INPUT_TIMEFRAMES", "").strip()
    if tf_env:
        return [t.strip() for t in tf_env.split(",") if t.strip()]

    return list(fallback or DEFAULT_TIMEFRAMES)


def get_symbol_universe(
    include_timeframes: bool = True,
    fallback_symbols: Sequence[str] | None = None,
    fallback_timeframes: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Return the symbol/timeframe set used by nightly jobs."""

    universe: dict[str, list[str]] = {
        "symbols": resolve_symbol_list(fallback_symbols),
    }

    if include_timeframes:
        universe["timeframes"] = resolve_timeframe_list(fallback_timeframes)

    return universe


def format_env_exports(
    symbols: Sequence[str],
    timeframes: Sequence[str],
    *,
    prefix: str = "SWIFTBOLT",
) -> str:
    """Format shell-friendly export statements for use in workflows."""

    symbol_csv = ",".join(symbols)
    timeframe_csv = ",".join(timeframes)
    return (
        f"{prefix}_SYMBOLS={symbol_csv}\n"
        f"{prefix}_TIMEFRAMES={timeframe_csv}\n"
        f"{prefix}_SYMBOL_COUNT={len(symbols)}\n"
    )
