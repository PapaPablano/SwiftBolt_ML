"""AdaptiveSuperTrend adapter for existing forecast jobs.

Bridges the production adaptive_supertrend package into the intraday/daily
jobs with a thin synchronous wrapper, feature‑flag friendly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from adaptive_supertrend import AdaptiveSuperTrend, SuperTrendConfig

logger = logging.getLogger(__name__)


def _run(coro):
    """Run an async coroutine from sync code."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # If an event loop is already running (unlikely in current jobs),
        # create a new task and gather.
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)


class AdaptiveSuperTrendAdapter:
    """Synchronous adapter for AdaptiveSuperTrend."""

    def __init__(
        self,
        *,
        metric_objective: str = "sharpe",
        cache_enabled: bool = True,
        cache_ttl_hours: int = 24,
        min_bars: int = 60,
        enable_optimization: bool = True,
    ) -> None:
        self.min_bars = min_bars
        self.enable_optimization = enable_optimization

        config = SuperTrendConfig(
            metric_objective=metric_objective,
            cache_enabled=cache_enabled,
            cache_ttl_hours=cache_ttl_hours,
        )
        self.ast = AdaptiveSuperTrend(config=config)

    def compute_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str,
        use_cached_factor: bool = True,
    ) -> Optional[Dict]:
        """Compute a single adaptive SuperTrend signal for the provided OHLCV."""
        if df is None or len(df) < self.min_bars:
            logger.debug(
                "Adaptive ST skipped: insufficient bars for %s %s (%s)",
                symbol,
                timeframe,
                len(df) if df is not None else 0,
            )
            return None

        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)

        try:
            if self.enable_optimization:
                signal = _run(
                    self.ast.generate_signal_with_optimization(
                        symbol=symbol,
                        timeframe=timeframe,
                        high=high,
                        low=low,
                        close=close,
                    )
                )
            else:
                # Use a fixed factor if optimization is disabled
                signal = self.ast.generate_signal(
                    symbol=symbol,
                    timeframe=timeframe,
                    high=high,
                    low=low,
                    close=close,
                    factor=3.0,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Adaptive ST failed for %s %s: %s", symbol, timeframe, exc)
            return None

        if signal is None:
            return None

        return {
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "timestamp": signal.timestamp,
            "trend": signal.trend,
            "supertrend_value": float(signal.supertrend_value),
            "factor": float(signal.factor),
            "signal_strength": float(signal.signal_strength),
            "confidence": float(signal.confidence),
            "distance_pct": float(signal.distance_pct),
            "trend_duration": int(signal.trend_duration),
            "performance_index": float(signal.performance_index),
            "metrics": (
                {
                    "sharpe_ratio": float(signal.metrics.sharpe_ratio),
                    "sortino_ratio": float(signal.metrics.sortino_ratio),
                    "calmar_ratio": float(signal.metrics.calmar_ratio),
                    "max_drawdown": float(signal.metrics.max_drawdown),
                    "win_rate": float(signal.metrics.win_rate),
                    "profit_factor": float(signal.metrics.profit_factor),
                    "total_return": float(signal.metrics.total_return),
                    "num_trades": int(signal.metrics.num_trades),
                    "recent_score": float(signal.metrics.recent_score),
                }
                if signal.metrics
                else None
            ),
        }


_adapter_singleton: Optional[AdaptiveSuperTrendAdapter] = None


def get_adaptive_supertrend_adapter(
    *,
    metric_objective: str = "sharpe",
    cache_enabled: bool = True,
    cache_ttl_hours: int = 24,
    min_bars: int = 60,
    enable_optimization: bool = True,
) -> AdaptiveSuperTrendAdapter:
    """Singleton accessor to avoid repeated model init in jobs."""
    global _adapter_singleton
    if _adapter_singleton is None:
        _adapter_singleton = AdaptiveSuperTrendAdapter(
            metric_objective=metric_objective,
            cache_enabled=cache_enabled,
            cache_ttl_hours=cache_ttl_hours,
            min_bars=min_bars,
            enable_optimization=enable_optimization,
        )
    return _adapter_singleton
