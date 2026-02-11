"""
Alpaca data adapter for Forecasting Lab.

Loads OHLC from Alpaca data API (server-side only). Uses same env vars as
ml/src/data/alpaca_underlying_history.py: ALPACA_API_KEY, ALPACA_API_SECRET.
"""

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import aiohttp
import pandas as pd

from forecasting_lab.data.base import DataAdapter

# Alpaca data API (bars)
ALPACA_DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets/v2")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")

# Timeframe mapping: lab names -> Alpaca bar timeframe
TIMEFRAME_MAP = {
    "15m": "15Min",
    "m15": "15Min",
    "1h": "1Hour",
    "h1": "1Hour",
    "4h": "4Hour",
    "h4": "4Hour",
    "1d": "1Day",
    "d1": "1Day",
    "1D": "1Day",
    "1wk": "1Week",
    "w1": "1Week",
}


class AlpacaAdapter(DataAdapter):
    """Load OHLC via Alpaca data API (sync wrapper around async fetch)."""

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
            "Accept": "application/json",
        }

    async def _fetch_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pd.DataFrame:
        url = f"{ALPACA_DATA_BASE}/stocks/{symbol}/bars"
        params = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timeframe": timeframe,
            "limit": 10000,
            "adjustment": "all",
            "feed": "iex",
        }
        all_bars = []
        next_page_token = None
        async with aiohttp.ClientSession() as session:
            while True:
                if next_page_token:
                    params["page_token"] = next_page_token
                async with session.get(url, params=params, headers=self._headers()) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Alpaca data API error: status={resp.status} symbol={symbol} timeframe={timeframe} body={body[:500]}"
                        )
                    data = await resp.json()
                bars = data.get("bars", [])
                if not bars:
                    break
                for bar in bars:
                    all_bars.append({
                        "ts": bar["t"],
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"],
                        "volume": bar["v"],
                    })
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break
        if not all_bars:
            return pd.DataFrame()
        df = pd.DataFrame(all_bars)
        df["ts"] = pd.to_datetime(df["ts"])
        return df.sort_values("ts").reset_index(drop=True)

    def load(
        self,
        symbol: str,
        start: Optional[date | datetime | str] = None,
        end: Optional[date | datetime | str] = None,
        timeframe: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLC from Alpaca. Returns DataFrame with ts, open, high, low, close, volume.
        Regular session only (Alpaca bars are session-based when requested with feed=iex).
        """
        if not ALPACA_API_KEY or not ALPACA_API_SECRET:
            return pd.DataFrame()
        tf = (timeframe or "1d").strip().lower()
        alpaca_tf = TIMEFRAME_MAP.get(tf, "1Day")
        end_dt = pd.Timestamp(end) if end is not None else datetime.now(timezone.utc)
        if hasattr(end_dt, "tzinfo") and end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        start_dt = pd.Timestamp(start) if start is not None else (end_dt - timedelta(days=365 * 2))
        if hasattr(start_dt, "tzinfo") and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        return asyncio.run(
            self._fetch_bars(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime(), alpaca_tf)
        )
