"""
Databento Client Module.

Fetches CME Globex futures data (OHLCV bars) from Databento API.
Supports both continuous contracts and specific expiries.

Databento dataset: GLBX.MDP3 (CME Globex MDP 3.0)
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from databento import Historical
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABENTO_API_KEY = os.getenv("DATABENTO_API_KEY", "")
DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1d"

CONTINUOUS_SUFFIX_MAP = {
    "ES": "ES.v.0",
    "NQ": "NQ.v.0",
    "GC": "GC.v.0",
    "CL": "CL.v.0",
    "ZC": "ZC.v.0",
    "ZS": "ZS.v.0",
    "ZW": "ZW.v.0",
    "HE": "HE.v.0",
    "LE": "LE.v.0",
    "HG": "HG.v.0",
    "SI": "SI.v.0",
    "PL": "PL.v.0",
    "PA": "PA.v.0",
}


@dataclass
class FuturesBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class DatabentoClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or DATABENTO_API_KEY
        if not self.api_key or self.api_key == "your-databento-api-key-here":
            raise ValueError("DATABENTO_API_KEY is required")
        self.client = Historical(key=self.api_key)

    def get_continuous_contract(
        self,
        root: str,
        resolution: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch continuous contract data for a futures root.

        Args:
            root: Futures root symbol (e.g., "ES", "GC", "NQ")
            resolution: Time resolution ("1s", "1m", "1h", "1d")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV columns: timestamp, open, high, low, close, volume
        """
        symbol = f"{root}.v.0"
        return self._fetch_bars(
            symbol=symbol,
            stype_in="continuous",
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
        Fetch specific expiry contract data.

        Args:
            symbol: Full contract symbol (e.g., "GCZ4", "ESH6")
            resolution: Time resolution ("1s", "1m", "1h", "1d")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV columns
        """
        return self._fetch_bars(
            symbol=symbol,
            stype_in="parent",
            resolution=resolution,
            start_date=start_date,
            end_date=end_date,
        )

    def _fetch_bars(
        self,
        symbol: str,
        stype_in: str,
        resolution: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Internal method to fetch bars from Databento.
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        logger.info(f"Fetching {symbol} ({stype_in}) from {start_date} to {end_date}")

        try:
            data = self.client.timeseries.get_range(
                dataset=DATASET,
                symbol=symbol,
                stype_in=stype_in,
                schema="ohlcv-1d",
                start=start_date,
                end=end_date,
            )

            df = data.to_pandas()
            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame(
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )

            df = df.reset_index()
            df = df.rename(columns={"ts_event": "timestamp"})
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)

            return df

        except Exception as e:
            logger.error(f"Error fetching {symbol} from Databento: {e}")
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

    def get_futures_roots(self) -> list[str]:
        """Return list of supported futures roots."""
        return list(CONTINUOUS_SUFFIX_MAP.keys())


def get_client() -> DatabentoClient:
    """Factory function to create DatabentoClient."""
    return DatabentoClient()
