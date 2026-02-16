"""
Yahoo Finance Client for Futures Data.

Fetches CME Globex futures data (OHLCV bars) from Yahoo Finance.
Free, no subscription required (delayed data).

Yahoo Finance futures symbols: ES=F, GC=F, NQ=F, CL=F, etc.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

YAHOO_FUTURES_MAP = {
    "ES": "ES=F",
    "NQ": "NQ=F",
    "GC": "GC=F",
    "CL": "CL=F",
    "ZC": "ZC=F",
    "ZS": "ZS=F",
    "ZW": "ZW=F",
    "HE": "HE=F",
    "LE": "LE=F",
    "HG": "HG=F",
    "SI": "SI=F",
    "PL": "PL=F",
    "PA": "PA=F",
}

YAHOO_INTERVAL_MAP = {
    "1s": "1m",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "1d": "1d",
    "1w": "1wk",
}


class YahooFuturesClient:
    def __init__(self):
        pass

    def get_continuous_contract(
        self,
        root: str,
        resolution: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch continuous contract data for a futures root using Yahoo Finance.

        Args:
            root: Futures root symbol (e.g., "ES", "GC", "NQ")
            resolution: Time resolution ("1m", "15m", "1h", "1d")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV columns: timestamp, open, high, low, close, volume
        """
        yahoo_symbol = YAHOO_FUTURES_MAP.get(root.upper())
        if not yahoo_symbol:
            logger.warning(f"Unknown futures root: {root}")
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        return self._fetch_bars(
            symbol=yahoo_symbol,
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )

    def get_expiry_contract(
        self,
        symbol: str,
        resolution: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch specific expiry contract data from Yahoo Finance.

        Yahoo doesn't support specific expiry symbols well - falls back to continuous.
        """
        root = symbol.upper()
        if len(root) <= 2:
            return self.get_continuous_contract(root, resolution, start_date, end_date)

        for base, full in YAHOO_FUTURES_MAP.items():
            if root.startswith(base):
                return self.get_continuous_contract(
                    base, resolution, start_date, end_date
                )

        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

    def _fetch_bars(
        self,
        symbol: str,
        resolution: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Internal method to fetch bars from Yahoo Finance.
        """
        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = pd.to_datetime(end_date)

        if start_date is None:
            start_date = end_date - timedelta(days=365)
        else:
            start_date = pd.to_datetime(start_date)

        interval = YAHOO_INTERVAL_MAP.get(resolution, "1d")
        logger.info(
            f"Fetching {symbol} from {start_date.date()} to {end_date.date()} (interval: {interval})"
        )

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame(
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )

            df = df.reset_index()
            df = df.rename(columns={"Date": "timestamp"})

            if "Datetime" in df.columns:
                df = df.rename(columns={"Datetime": "timestamp"})

            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)

            df = df[["timestamp", "Open", "High", "Low", "Close", "Volume"]]
            df = df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            df = df.dropna(subset=["close"])
            df["volume"] = df["volume"].fillna(0).astype(int)

            return df

        except Exception as e:
            logger.error(f"Error fetching {symbol} from Yahoo Finance: {e}")
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

    def get_futures_roots(self) -> list[str]:
        """Return list of supported futures roots."""
        return list(YAHOO_FUTURES_MAP.keys())


def get_client() -> YahooFuturesClient:
    """Factory function to create YahooFuturesClient."""
    return YahooFuturesClient()
