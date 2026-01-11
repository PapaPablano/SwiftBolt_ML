"""Tradier API client for market data.

Fetches options chains, OHLCV bars, quotes, tick data, and more from Tradier's API.
Requires a Tradier brokerage account (free to open).

Supported Data Types:
    - Historical OHLCV (daily, weekly, monthly, minute, tick)
    - Real-time Quotes (bid/ask, volume, last price)
    - Options Chains (with Greeks)
    - Time & Sales (tick data at intervals)
    - Futures Data (full futures support)

Usage:
    client = TradierClient()

    # Get intraday bars
    bars = client.get_intraday_bars("AAPL", interval="5min")

    # Get options expirations
    expirations = client.get_expirations("AAPL")

    # Get full options chain
    chain = client.get_options_chain("AAPL", "2024-01-19")

    # Get time and sales (tick data)
    ticks = client.get_timesales("AAPL", interval="1min")

    # Get multiple quotes at once
    quotes = client.get_quotes(["AAPL", "MSFT", "GOOGL"])
"""

import logging
import time
from datetime import date, datetime, timedelta
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
            raise ValueError("Tradier API key required. Set TRADIER_API_KEY environment variable.")

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

    def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "5min",
        start: str | None = None,
        end: str | None = None,
        session_filter: str = "all",
    ) -> pd.DataFrame:
        """Get intraday OHLCV bars.

        Args:
            symbol: Stock ticker symbol
            interval: Bar interval - 1min, 5min, 15min, or tick
            start: Start datetime (YYYY-MM-DD HH:MM or YYYY-MM-DD)
            end: End datetime (YYYY-MM-DD HH:MM or YYYY-MM-DD)
            session_filter: Session filter - 'all', 'open' (market hours only)

        Returns:
            DataFrame with intraday OHLCV data
        """
        # Map our interval names to Tradier's format
        interval_map = {
            "1min": "1min",
            "1m": "1min",
            "5min": "5min",
            "5m": "5min",
            "15min": "15min",
            "15m": "15min",
            "tick": "tick",
        }
        tradier_interval = interval_map.get(interval, interval)

        # Default to last trading day if no dates specified
        if not start:
            start = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        params = {
            "symbol": symbol,
            "interval": tradier_interval,
            "start": start,
            "end": end,
            "session_filter": session_filter,
        }

        data = self._request("GET", "/markets/timesales", params)
        series = data.get("series", {})

        if not series:
            logger.warning(f"No intraday data for {symbol} from {start} to {end}")
            return pd.DataFrame()

        # Tradier returns 'data' for timesales
        bars = series.get("data", [])
        if isinstance(bars, dict):
            bars = [bars]

        if not bars:
            return pd.DataFrame()

        df = pd.DataFrame(bars)

        # Rename and parse columns
        if "time" in df.columns:
            df["ts"] = pd.to_datetime(df["time"])
            df = df.drop("time", axis=1)
        elif "timestamp" in df.columns:
            df["ts"] = pd.to_datetime(df["timestamp"], unit="s")
            df = df.drop("timestamp", axis=1)

        # Ensure standard column names
        rename_map = {
            "price": "close",  # tick data has price instead of OHLC
        }
        df = df.rename(columns=rename_map)

        df["symbol"] = symbol
        df = df.sort_values("ts").reset_index(drop=True)

        logger.info(f"Fetched {len(df)} intraday bars for {symbol}")
        return df

    def get_timesales(
        self,
        symbol: str,
        interval: str = "tick",
        start: str | None = None,
        end: str | None = None,
        session_filter: str = "open",
    ) -> pd.DataFrame:
        """Get time and sales (tick) data.

        This is useful for volume analysis and understanding order flow.

        Args:
            symbol: Stock ticker symbol
            interval: Aggregation interval - 'tick', '1min', '5min', '15min'
            start: Start datetime (YYYY-MM-DD HH:MM)
            end: End datetime (YYYY-MM-DD HH:MM)
            session_filter: 'all' or 'open' (market hours only)

        Returns:
            DataFrame with tick/trade data
        """
        return self.get_intraday_bars(
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            session_filter=session_filter,
        )

    def get_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """Get quotes for multiple symbols at once.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            DataFrame with quote data for all symbols
        """
        if not symbols:
            return pd.DataFrame()

        # Tradier accepts comma-separated symbols
        symbols_str = ",".join(s.upper() for s in symbols)
        data = self._request("GET", "/markets/quotes", {"symbols": symbols_str})

        quotes = data.get("quotes", {}).get("quote", [])
        if not quotes:
            return pd.DataFrame()

        # Handle single quote returned as dict
        if isinstance(quotes, dict):
            quotes = [quotes]

        df = pd.DataFrame(quotes)
        df["fetched_at"] = datetime.utcnow().isoformat()

        logger.info(f"Fetched quotes for {len(df)} symbols")
        return df

    def get_clock(self) -> dict[str, Any]:
        """Get current market clock/status.

        Returns:
            Market status including open/close times, current state
        """
        data = self._request("GET", "/markets/clock")
        return data.get("clock", {})

    def get_calendar(self, month: int | None = None, year: int | None = None) -> dict[str, Any]:
        """Get market calendar.

        Args:
            month: Month (1-12)
            year: Year (YYYY)

        Returns:
            Market calendar with trading days and hours
        """
        params = {}
        if month:
            params["month"] = month
        if year:
            params["year"] = year

        data = self._request("GET", "/markets/calendar", params)
        return data.get("calendar", {})

    def is_market_open(self) -> bool:
        """Check if market is currently open.

        Returns:
            True if market is open for trading
        """
        clock = self.get_clock()
        state = clock.get("state", "").lower()
        return state == "open"

    def get_current_day_bars(
        self,
        symbol: str,
        interval: str = "5min",
    ) -> pd.DataFrame:
        """Get intraday bars for current trading day only.

        Convenience method for real-time updates.

        Args:
            symbol: Stock ticker symbol
            interval: Bar interval

        Returns:
            DataFrame with today's intraday bars
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_intraday_bars(
            symbol=symbol,
            interval=interval,
            start=today,
            end=today,
            session_filter="open",
        )

    def get_extended_hours_data(
        self,
        symbol: str,
        interval: str = "5min",
    ) -> pd.DataFrame:
        """Get extended hours (pre-market + after-hours) data.

        Args:
            symbol: Stock ticker symbol
            interval: Bar interval

        Returns:
            DataFrame with extended hours bars
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_intraday_bars(
            symbol=symbol,
            interval=interval,
            start=today,
            end=today,
            session_filter="all",  # Include pre/post market
        )

    def compute_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute VWAP from intraday bars.

        Args:
            df: DataFrame with columns: close (or price), volume

        Returns:
            DataFrame with vwap column added
        """
        if df.empty:
            return df

        price_col = "close" if "close" in df.columns else "price"
        if price_col not in df.columns or "volume" not in df.columns:
            logger.warning("Cannot compute VWAP: missing price or volume columns")
            return df

        df = df.copy()
        df["_cumvol"] = df["volume"].cumsum()
        df["_cumvol_price"] = (df[price_col] * df["volume"]).cumsum()
        df["vwap"] = df["_cumvol_price"] / df["_cumvol"]
        df = df.drop(["_cumvol", "_cumvol_price"], axis=1)

        return df

    def get_futures_quote(self, symbol: str) -> dict[str, Any]:
        """Get quote for a futures contract.

        Args:
            symbol: Futures symbol (e.g., /ES, /NQ, /CL)

        Returns:
            Futures quote data
        """
        # Futures symbols typically start with /
        if not symbol.startswith("/"):
            symbol = f"/{symbol}"

        return self.get_quote(symbol)

    def get_futures_chain(self, root: str) -> pd.DataFrame:
        """Get available futures contracts for a root symbol.

        Args:
            root: Futures root symbol (e.g., ES, NQ, CL)

        Returns:
            DataFrame with available futures contracts
        """
        # Note: This may require specific Tradier subscription
        data = self._request("GET", "/markets/options/lookup", {"underlying": f"/{root}"})
        symbols = data.get("symbols", {}).get("symbol", [])

        if not symbols:
            return pd.DataFrame()

        if isinstance(symbols, str):
            symbols = [symbols]

        return pd.DataFrame({"symbol": symbols})

    def get_option_timesales(
        self,
        option_symbol: str,
        interval: str = "5min",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Get time and sales (tick) data for an option contract.

        This can help estimate historical prices from recent trades.

        Args:
            option_symbol: Full option symbol (e.g., AAPL260117C00150000)
            interval: Aggregation interval - 'tick', '1min', '5min', '15min'
            start: Start datetime (YYYY-MM-DD HH:MM)
            end: End datetime (YYYY-MM-DD HH:MM)

        Returns:
            DataFrame with trade data (timestamp, price, volume)
        """
        if not start:
            start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        if not end:
            end = datetime.now().strftime("%Y-%m-%d")

        params = {
            "symbol": option_symbol,
            "interval": interval,
            "start": start,
            "end": end,
        }

        try:
            data = self._request("GET", "/markets/timesales", params)
            series = data.get("series", {})

            if not series:
                logger.debug(f"No timesales data for option {option_symbol}")
                return pd.DataFrame()

            trades = series.get("data", [])
            if isinstance(trades, dict):
                trades = [trades]

            if not trades:
                return pd.DataFrame()

            df = pd.DataFrame(trades)

            if "time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["time"])
                df = df.drop("time", axis=1)
            elif "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

            df["option_symbol"] = option_symbol
            df = df.sort_values("timestamp").reset_index(drop=True)

            return df

        except Exception as e:
            logger.debug(f"Failed to get option timesales for {option_symbol}: {e}")
            return pd.DataFrame()

    def get_option_strike_prices(
        self,
        symbol: str,
        expiration: str,
    ) -> list[float]:
        """Get available strike prices for a symbol and expiration.

        Args:
            symbol: Underlying stock symbol
            expiration: Expiration date (YYYY-MM-DD)

        Returns:
            List of available strike prices
        """
        params = {
            "symbol": symbol,
            "expiration": expiration,
        }

        try:
            data = self._request("GET", "/markets/options/strikes", params)
            strikes = data.get("strikes", {}).get("strike", [])

            if isinstance(strikes, (int, float)):
                return [float(strikes)]
            return [float(s) for s in strikes] if strikes else []

        except Exception as e:
            logger.error(f"Failed to get strikes for {symbol} {expiration}: {e}")
            return []

    def get_historical_underlying_prices(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> pd.DataFrame:
        """Get historical daily prices for underlying symbol.

        Useful for estimating historical option prices based on underlying movement.

        Args:
            symbol: Stock ticker symbol
            days_back: Number of days of history

        Returns:
            DataFrame with date, open, high, low, close, volume
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return self.get_historical_prices(
            symbol=symbol,
            interval="daily",
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )

    def snapshot_options_chain(
        self,
        symbol: str,
        max_expirations: int = 6,
    ) -> pd.DataFrame:
        """Get a complete snapshot of options chain for storage.

        Fetches all available options with Greeks and formats for database storage.

        Args:
            symbol: Underlying stock symbol
            max_expirations: Maximum expirations to fetch

        Returns:
            DataFrame formatted for options_snapshots table
        """
        # Get current underlying price
        quote = self.get_quote(symbol)
        underlying_price = float(quote.get("last", quote.get("close", 0)))

        # Get all chains
        chains = self.get_all_chains(symbol, max_expirations=max_expirations, greeks=True)

        if chains.empty:
            return pd.DataFrame()

        # Format for database
        snapshot_time = datetime.utcnow().isoformat()
        chains["underlying_price"] = underlying_price
        chains["snapshot_time"] = snapshot_time

        # Rename columns to match database schema
        rename_map = {
            "symbol": "contract_symbol",
            "option_type": "option_type",
            "expiration_date": "expiration",
            "greek_delta": "delta",
            "greek_gamma": "gamma",
            "greek_theta": "theta",
            "greek_vega": "vega",
            "greek_rho": "rho",
            "greek_mid_iv": "iv",
        }

        for old_col, new_col in rename_map.items():
            if old_col in chains.columns and new_col not in chains.columns:
                chains[new_col] = chains[old_col]

        # Ensure required columns exist
        required_cols = [
            "contract_symbol",
            "option_type",
            "strike",
            "expiration",
            "bid",
            "ask",
            "last",
            "underlying_price",
            "volume",
            "open_interest",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "iv",
            "snapshot_time",
        ]

        for col in required_cols:
            if col not in chains.columns:
                chains[col] = (
                    0
                    if col not in ["contract_symbol", "option_type", "expiration", "snapshot_time"]
                    else ""
                )

        logger.info(f"Created snapshot of {len(chains)} options for {symbol}")
        return chains[required_cols]

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
