"""
Alpaca Underlying History Module.

Fetches 7-day price history (daily bars, optional multi-timeframe) for options'
underlying assets from Alpaca API. Computes derived metrics (7-day return,
volatility, drawdown, gap frequency) and stores them in Supabase.

Features:
- Async batching with exponential backoff
- Multi-timeframe support (m15, h1, h4, d1, w1)
- Caching to reduce redundant API calls
- Integration with Supabase for persistent storage
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Alpaca API configuration
ALPACA_BASE_URL = "https://data.alpaca.markets/v2"
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")

# Rate limiting configuration
# Alpaca allows 200 requests/minute for free tier
RATE_LIMIT_REQUESTS_PER_MINUTE = 200
MIN_REQUEST_INTERVAL = 60.0 / RATE_LIMIT_REQUESTS_PER_MINUTE  # ~0.3 seconds

# Exponential backoff configuration
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 32.0
MAX_RETRIES = 5

# Timeframe configuration with bar counts for 7 days
TIMEFRAME_CONFIG = {
    "m15": {"alpaca_tf": "15Min", "bars_for_7d": 7 * 24 * 4},  # 672 bars
    "h1": {"alpaca_tf": "1Hour", "bars_for_7d": 7 * 24},  # 168 bars
    "h4": {"alpaca_tf": "4Hour", "bars_for_7d": 7 * 6},  # 42 bars
    "d1": {"alpaca_tf": "1Day", "bars_for_7d": 7},  # 7 bars
    "w1": {"alpaca_tf": "1Week", "bars_for_7d": 1},  # 1 bar
}


@dataclass
class UnderlyingMetrics:
    """7-day metrics for an underlying symbol."""

    symbol: str
    timeframe: str
    return_7d: float
    volatility_7d: float
    drawdown_7d: float
    gap_count: int
    bars_count: int
    first_ts: datetime | None
    last_ts: datetime | None
    computed_at: datetime


def compute_return(prices: pd.Series) -> float:
    """
    Compute 7-day return as percentage.

    Args:
        prices: Series of close prices, ordered oldest to newest

    Returns:
        Return percentage (e.g., 5.2 for 5.2% gain)
    """
    if len(prices) < 2:
        return 0.0

    first_price = prices.iloc[0]
    last_price = prices.iloc[-1]

    if first_price <= 0 or pd.isna(first_price) or pd.isna(last_price):
        return 0.0

    return ((last_price - first_price) / first_price) * 100


def compute_volatility(prices: pd.Series) -> float:
    """
    Compute 7-day annualized volatility.

    Args:
        prices: Series of close prices, ordered oldest to newest

    Returns:
        Annualized volatility as percentage
    """
    if len(prices) < 3:
        return 0.0

    # Calculate daily returns
    returns = prices.pct_change().dropna()

    if len(returns) < 2:
        return 0.0

    # Calculate standard deviation and annualize (252 trading days)
    daily_vol = returns.std()
    if pd.isna(daily_vol):
        return 0.0

    annualized_vol = daily_vol * np.sqrt(252) * 100
    return annualized_vol


def compute_drawdown(prices: pd.Series) -> float:
    """
    Compute maximum drawdown over 7-day period.

    Args:
        prices: Series of close prices, ordered oldest to newest

    Returns:
        Maximum drawdown as positive percentage (e.g., 5.0 for 5% drawdown)
    """
    if len(prices) < 2:
        return 0.0

    # Calculate running maximum
    running_max = prices.cummax()

    # Calculate drawdown from running max
    drawdown = (running_max - prices) / running_max * 100

    max_drawdown = drawdown.max()
    if pd.isna(max_drawdown):
        return 0.0

    return max_drawdown


def count_gaps(df: pd.DataFrame, threshold_pct: float = 1.0) -> int:
    """
    Count significant price gaps (overnight/weekend gaps).

    A gap is defined as an open price significantly different from
    previous close.

    Args:
        df: DataFrame with 'open' and 'close' columns
        threshold_pct: Minimum gap percentage to count

    Returns:
        Number of significant gaps detected
    """
    if len(df) < 2:
        return 0

    if "open" not in df.columns or "close" not in df.columns:
        return 0

    gap_count = 0
    for i in range(1, len(df)):
        prev_close = df.iloc[i - 1]["close"]
        curr_open = df.iloc[i]["open"]

        if prev_close > 0 and not pd.isna(prev_close) and not pd.isna(curr_open):
            gap_pct = abs((curr_open - prev_close) / prev_close) * 100
            if gap_pct >= threshold_pct:
                gap_count += 1

    return gap_count


def compute_all_metrics(df: pd.DataFrame, symbol: str, timeframe: str) -> UnderlyingMetrics:
    """
    Compute all 7-day metrics for a symbol's OHLC data.

    Args:
        df: DataFrame with ts, open, high, low, close, volume columns
        symbol: Stock ticker symbol
        timeframe: Timeframe string (m15, h1, h4, d1, w1)

    Returns:
        UnderlyingMetrics dataclass with computed values
    """
    if df.empty:
        return UnderlyingMetrics(
            symbol=symbol,
            timeframe=timeframe,
            return_7d=0.0,
            volatility_7d=0.0,
            drawdown_7d=0.0,
            gap_count=0,
            bars_count=0,
            first_ts=None,
            last_ts=None,
            computed_at=datetime.now(timezone.utc),
        )

    # Ensure sorted by timestamp
    df = df.sort_values("ts").reset_index(drop=True)

    close_prices = df["close"].astype(float)

    return UnderlyingMetrics(
        symbol=symbol,
        timeframe=timeframe,
        return_7d=compute_return(close_prices),
        volatility_7d=compute_volatility(close_prices),
        drawdown_7d=compute_drawdown(close_prices),
        gap_count=count_gaps(df),
        bars_count=len(df),
        first_ts=pd.to_datetime(df.iloc[0]["ts"]),
        last_ts=pd.to_datetime(df.iloc[-1]["ts"]),
        computed_at=datetime.now(timezone.utc),
    )


class AlpacaUnderlyingHistoryClient:
    """
    Client for fetching underlying price history from Alpaca.

    Implements async batching with exponential backoff for resilience.
    """

    def __init__(self):
        """Initialize the Alpaca client."""
        self._last_request_time: float = 0
        self._cache: dict[str, tuple[pd.DataFrame, float]] = {}
        self._cache_ttl_seconds = 3600  # 1 hour cache

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers for Alpaca API."""
        return {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
            "Accept": "application/json",
        }

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _get_cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key for symbol/timeframe pair."""
        return f"{symbol}:{timeframe}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        _, cached_time = self._cache[cache_key]
        return (time.time() - cached_time) < self._cache_ttl_seconds

    async def fetch_bars(
        self,
        symbol: str,
        timeframe: str = "d1",
        lookback_days: int = 7,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars from Alpaca for a symbol.

        Args:
            symbol: Stock ticker symbol
            timeframe: Timeframe (m15, h1, h4, d1, w1)
            lookback_days: Number of days to fetch

        Returns:
            DataFrame with ts, open, high, low, close, volume columns
        """
        if not ALPACA_API_KEY or not ALPACA_API_SECRET:
            logger.error("Alpaca API credentials not configured")
            return pd.DataFrame()

        cache_key = self._get_cache_key(symbol, timeframe)
        if self._is_cache_valid(cache_key):
            logger.debug(f"Using cached data for {symbol}/{timeframe}")
            return self._cache[cache_key][0].copy()

        config = TIMEFRAME_CONFIG.get(timeframe)
        if not config:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return pd.DataFrame()

        alpaca_tf = config["alpaca_tf"]
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        url = f"{ALPACA_BASE_URL}/stocks/{symbol}/bars"
        params = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "timeframe": alpaca_tf,
            "limit": config["bars_for_7d"] * 2,  # Extra buffer for safety
            "adjustment": "all",  # Adjust for splits/dividends
            "feed": "iex",  # Use IEX feed (free tier)
        }

        all_bars = []
        next_page_token = None
        retries = 0
        backoff = INITIAL_BACKOFF_SECONDS

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    await self._rate_limit()

                    if next_page_token:
                        params["page_token"] = next_page_token

                    async with session.get(
                        url,
                        params=params,
                        headers=self._get_headers(),
                    ) as response:
                        if response.status == 429:
                            # Rate limited - apply backoff
                            logger.warning(
                                f"Rate limited for {symbol}, backing off {backoff}s"
                            )
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                            retries += 1
                            if retries >= MAX_RETRIES:
                                logger.error(f"Max retries exceeded for {symbol}")
                                break
                            continue

                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(
                                f"Alpaca API error for {symbol}: {response.status} - {error_text}"
                            )
                            break

                        data = await response.json()

                        # Reset backoff on success
                        backoff = INITIAL_BACKOFF_SECONDS
                        retries = 0

                        bars = data.get("bars", [])
                        if not bars:
                            break

                        for bar in bars:
                            all_bars.append(
                                {
                                    "ts": bar["t"],
                                    "open": bar["o"],
                                    "high": bar["h"],
                                    "low": bar["l"],
                                    "close": bar["c"],
                                    "volume": bar["v"],
                                }
                            )

                        next_page_token = data.get("next_page_token")
                        if not next_page_token:
                            break

                except aiohttp.ClientError as e:
                    logger.error(f"Network error fetching {symbol}: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                    retries += 1
                    if retries >= MAX_RETRIES:
                        break

        if not all_bars:
            return pd.DataFrame()

        df = pd.DataFrame(all_bars)
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.sort_values("ts").reset_index(drop=True)

        # Cache the result
        self._cache[cache_key] = (df.copy(), time.time())

        logger.info(f"Fetched {len(df)} bars for {symbol}/{timeframe}")
        return df

    async def fetch_7day_metrics(
        self,
        symbol: str,
        timeframe: str = "d1",
    ) -> UnderlyingMetrics:
        """
        Fetch 7-day bars and compute metrics for a symbol.

        Args:
            symbol: Stock ticker symbol
            timeframe: Timeframe (m15, h1, h4, d1, w1)

        Returns:
            UnderlyingMetrics with computed values
        """
        df = await self.fetch_bars(symbol, timeframe, lookback_days=7)
        return compute_all_metrics(df, symbol, timeframe)

    async def fetch_metrics_batch(
        self,
        symbols: list[str],
        timeframe: str = "d1",
    ) -> list[UnderlyingMetrics]:
        """
        Fetch 7-day metrics for multiple symbols.

        Uses async batching to maximize throughput while respecting rate limits.

        Args:
            symbols: List of stock ticker symbols
            timeframe: Timeframe for all symbols

        Returns:
            List of UnderlyingMetrics for each symbol
        """
        results = []

        for symbol in symbols:
            try:
                metrics = await self.fetch_7day_metrics(symbol, timeframe)
                results.append(metrics)
            except Exception as e:
                logger.error(f"Error fetching metrics for {symbol}: {e}")
                # Add empty metrics for failed symbols
                results.append(
                    UnderlyingMetrics(
                        symbol=symbol,
                        timeframe=timeframe,
                        return_7d=0.0,
                        volatility_7d=0.0,
                        drawdown_7d=0.0,
                        gap_count=0,
                        bars_count=0,
                        first_ts=None,
                        last_ts=None,
                        computed_at=datetime.now(timezone.utc),
                    )
                )

        return results

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()


def metrics_to_dict(metrics: UnderlyingMetrics) -> dict[str, Any]:
    """
    Convert UnderlyingMetrics to a dictionary for database storage.

    Args:
        metrics: UnderlyingMetrics object

    Returns:
        Dictionary suitable for Supabase upsert
    """
    return {
        "symbol": metrics.symbol,
        "timeframe": metrics.timeframe,
        "ret_7d": metrics.return_7d,
        "vol_7d": metrics.volatility_7d,
        "drawdown_7d": metrics.drawdown_7d,
        "gap_count": metrics.gap_count,
        "bars_count": metrics.bars_count,
        "first_ts": metrics.first_ts.isoformat() if metrics.first_ts else None,
        "last_ts": metrics.last_ts.isoformat() if metrics.last_ts else None,
        "computed_at": metrics.computed_at.isoformat(),
    }


# Module-level client instance
_client: AlpacaUnderlyingHistoryClient | None = None


def get_client() -> AlpacaUnderlyingHistoryClient:
    """Get or create the module-level Alpaca client."""
    global _client
    if _client is None:
        _client = AlpacaUnderlyingHistoryClient()
    return _client


async def fetch_underlying_history(
    symbol: str,
    timeframe: str = "d1",
) -> UnderlyingMetrics:
    """
    Convenience function to fetch 7-day underlying metrics.

    Args:
        symbol: Stock ticker symbol
        timeframe: Timeframe (m15, h1, h4, d1, w1)

    Returns:
        UnderlyingMetrics with computed values
    """
    client = get_client()
    return await client.fetch_7day_metrics(symbol, timeframe)


async def fetch_underlying_history_batch(
    symbols: list[str],
    timeframe: str = "d1",
) -> list[UnderlyingMetrics]:
    """
    Convenience function to fetch 7-day metrics for multiple symbols.

    Args:
        symbols: List of stock ticker symbols
        timeframe: Timeframe for all symbols

    Returns:
        List of UnderlyingMetrics for each symbol
    """
    client = get_client()
    return await client.fetch_metrics_batch(symbols, timeframe)
