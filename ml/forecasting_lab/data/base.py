"""
Abstract data adapter interface for Forecasting Lab.

Provides OHLC time series without touching production DBs.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional

import pandas as pd


class DataAdapter(ABC):
    """Abstract adapter: load(symbol, start, end, timeframe?) -> DataFrame with ts, close, [open, high, low, volume]."""

    @abstractmethod
    def load(
        self,
        symbol: str,
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
        timeframe: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load OHLC time series for a symbol.

        Args:
            symbol: Ticker symbol.
            start: Start date/datetime (inclusive).
            end: End date/datetime (inclusive).
            timeframe: Optional resolution (e.g. '1d', '1h'). Adapter-dependent.

        Returns:
            DataFrame with at least columns: ts (datetime), close.
            Ideally also: open, high, low, volume. Sorted by ts ascending.
        """
        pass

    def supported_symbols(self) -> Optional[list[str]]:
        """Optional: return list of symbols this adapter supports, or None if open-ended."""
        return None
