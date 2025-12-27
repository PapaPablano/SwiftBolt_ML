"""Tradier API client for options data.

Fetches options chains, expirations, and quotes from Tradier's free API.
Requires a Tradier brokerage account (free to open).

Usage:
    client = TradierClient()

    # Get options expirations
    expirations = client.get_expirations("AAPL")

    # Get full options chain
    chain = client.get_options_chain("AAPL", "2024-01-19")

    # Get specific option quote
    quote = client.get_option_quote("AAPL240119C00150000")
"""

import logging
import time
from datetime import datetime, date
from typing import Any

import httpx
import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)


class TradierClient:
    """Client for Tradier API - options and market data."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize Tradier client.

        Args:
            api_key: Tradier API key. Defaults to settings.tradier_api_key
            base_url: API base URL. Defaults to settings.tradier_base_url
        """
        self.api_key = api_key or settings.tradier_api_key
        self.base_url = base_url or settings.tradier_base_url

        if not self.api_key:
            raise ValueError(
                "Tradier API key required. Set TRADIER_API_KEY environment variable."
            )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
        )

        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 0.2  # 5 requests per second max

        logger.info("Tradier client initialized")

    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, endpoint: str, params: dict | None = None) -> dict:
        """Make API request with rate limiting.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response data
        """
        self._rate_limit()

        try:
            response = self._client.request(method, endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Tradier API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Tradier request failed: {e}")
            raise

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get current quote for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Quote data with bid, ask, last, volume, etc.
        """
        data = self._request("GET", "/markets/quotes", {"symbols": symbol})
        quotes = data.get("quotes", {}).get("quote", {})

        # Handle single vs multiple quotes
        if isinstance(quotes, list):
            return quotes[0] if quotes else {}
        return quotes

    def get_expirations(self, symbol: str) -> list[str]:
        """Get available options expiration dates.

        Args:
            symbol: Underlying stock symbol

        Returns:
            List of expiration dates (YYYY-MM-DD format)
        """
        data = self._request("GET", "/markets/options/expirations", {"symbol": symbol})
        expirations = data.get("expirations", {}).get("date", [])

        # Handle single date returned as string
        if isinstance(expirations, str):
            return [expirations]
        return expirations or []

    def get_options_chain(
        self,
        symbol: str,
        expiration: str,
        greeks: bool = True,
    ) -> pd.DataFrame:
        """Get full options chain for a symbol and expiration.

        Args:
            symbol: Underlying stock symbol
            expiration: Expiration date (YYYY-MM-DD)
            greeks: Include Greeks (delta, gamma, theta, vega)

        Returns:
            DataFrame with all options in the chain
        """
        params = {
            "symbol": symbol,
            "expiration": expiration,
            "greeks": str(greeks).lower(),
        }

        data = self._request("GET", "/markets/options/chains", params)
        options = data.get("options", {}).get("option", [])

        if not options:
            logger.warning(f"No options found for {symbol} expiring {expiration}")
            return pd.DataFrame()

        # Handle single option returned as dict
        if isinstance(options, dict):
            options = [options]

        df = pd.DataFrame(options)

        # Parse greeks if present
        if greeks and "greeks" in df.columns:
            greeks_df = pd.json_normalize(df["greeks"])
            greeks_df.columns = [f"greek_{c}" for c in greeks_df.columns]
            df = pd.concat([df.drop("greeks", axis=1), greeks_df], axis=1)

        # Add metadata
        df["underlying"] = symbol
        df["expiration_date"] = expiration
        df["fetched_at"] = datetime.utcnow().isoformat()

        logger.info(f"Fetched {len(df)} options for {symbol} exp {expiration}")
        return df

    def get_all_chains(
        self,
        symbol: str,
        max_expirations: int = 4,
        greeks: bool = True,
    ) -> pd.DataFrame:
        """Get options chains for multiple expirations.

        Args:
            symbol: Underlying stock symbol
            max_expirations: Maximum number of expirations to fetch
            greeks: Include Greeks

        Returns:
            Combined DataFrame with all chains
        """
        expirations = self.get_expirations(symbol)[:max_expirations]

        if not expirations:
            logger.warning(f"No expirations found for {symbol}")
            return pd.DataFrame()

        chains = []
        for exp in expirations:
            try:
                chain = self.get_options_chain(symbol, exp, greeks=greeks)
                if not chain.empty:
                    chains.append(chain)
            except Exception as e:
                logger.error(f"Failed to fetch chain for {symbol} {exp}: {e}")
                continue

        if not chains:
            return pd.DataFrame()

        return pd.concat(chains, ignore_index=True)

    def get_option_quote(self, option_symbol: str) -> dict[str, Any]:
        """Get quote for a specific option contract.

        Args:
            option_symbol: OCC option symbol (e.g., AAPL240119C00150000)

        Returns:
            Option quote data
        """
        data = self._request("GET", "/markets/quotes", {"symbols": option_symbol})
        quotes = data.get("quotes", {}).get("quote", {})

        if isinstance(quotes, list):
            return quotes[0] if quotes else {}
        return quotes

    def get_historical_prices(
        self,
        symbol: str,
        interval: str = "daily",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Get historical price data.

        Args:
            symbol: Stock ticker symbol
            interval: Price interval (daily, weekly, monthly)
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        params = {"symbol": symbol, "interval": interval}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        data = self._request("GET", "/markets/history", params)
        history = data.get("history", {})

        if not history:
            return pd.DataFrame()

        days = history.get("day", [])
        if isinstance(days, dict):
            days = [days]

        df = pd.DataFrame(days)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.rename(columns={"date": "ts"})
            df = df.sort_values("ts").reset_index(drop=True)

        return df

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
