"""
yfinance data adapter for Forecasting Lab.

Fetches OHLC from yfinance only; no Supabase or production DB.
"""

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from forecasting_lab.data.base import DataAdapter


class YFinanceAdapter(DataAdapter):
    """Load OHLC via yfinance (no DB)."""

    def load(
        self,
        symbol: str,
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
        timeframe: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLC from yfinance. Returns DataFrame with ts, open, high, low, close, volume.
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance is required for YFinanceAdapter; pip install yfinance")

        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = (end - timedelta(days=365 * 2)) if isinstance(end, (date, datetime)) else "2y"
        period = None
        interval = "1d"
        if isinstance(start, str) and start.endswith("y"):
            period = start
            start = None
        elif isinstance(end, str) and end.endswith("y"):
            period = end
            end = None
        if timeframe and timeframe.lower() in ("1h", "1d", "1wk"):
            interval = {"1h": "1h", "1d": "1d", "1wk": "1wk"}.get(timeframe.lower(), "1d")

        ticker = yf.Ticker(symbol)
        if period:
            hist = ticker.history(period=period, interval=interval)
        else:
            hist = ticker.history(
                start=pd.Timestamp(start),
                end=pd.Timestamp(end),
                interval=interval,
            )
        if hist is None or hist.empty:
            return pd.DataFrame()

        hist = hist.reset_index()
        hist = hist.rename(columns={
            "Date": "ts",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        if "ts" not in hist.columns and "Datetime" in hist.columns:
            hist = hist.rename(columns={"Datetime": "ts"})
        for col in ("open", "high", "low", "close", "volume"):
            if col not in hist.columns:
                hist[col] = None
        hist["ts"] = pd.to_datetime(hist["ts"]).dt.tz_localize(None)
        return hist[["ts", "open", "high", "low", "close", "volume"]].dropna(subset=["close"])
