"""
CSV data adapter for Forecasting Lab.

Reads OHLC from local CSV (e.g. fixtures) for reproducible tests. No DB.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from forecasting_lab.data.base import DataAdapter


class CSVAdapter(DataAdapter):
    """Load OHLC from CSV. Expects columns: ts (or date), open, high, low, close, [volume]."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = base_path or Path(__file__).resolve().parent.parent / "data" / "fixtures"

    def load(
        self,
        symbol: str,
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
        timeframe: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Read CSV from base_path / {symbol}.csv (or base_path / {symbol}_{timeframe}.csv).
        """
        name = f"{symbol}.csv" if not timeframe else f"{symbol}_{timeframe}.csv"
        path = self.base_path / name
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        if "date" in df.columns and "ts" not in df.columns:
            df = df.rename(columns={"date": "ts"})
        df["ts"] = pd.to_datetime(df["ts"])
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return pd.DataFrame()
        if "volume" not in df.columns:
            df["volume"] = 0
        if start is not None:
            df = df[df["ts"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["ts"] <= pd.Timestamp(end)]
        return df[["ts", "open", "high", "low", "close", "volume"]].sort_values("ts").reset_index(drop=True)
