"""
Unified data pipeline for OHLCV loading and feature engineering with Polygon.io integration.

Author: Cursor Agent
Created: 2025-10-31
Updated: 2025-01-27 - Added Polygon.io support for elite ML platform
"""

from __future__ import annotations

# Third-party imports
import yfinance as yf
import pandas as pd
import streamlit as st

# Standard library imports
from pathlib import Path
import logging
from datetime import datetime, timedelta
import os
import pytz
import asyncio
import time
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Callable

# Local imports
from .feature_engine import engineer_features, preprocess_ohlcv_data
from .redis_cache_manager import cached_function

# Initialize logger early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Holidays import for trading calendar
try:
    import holidays
    US_HOLIDAYS = holidays.US(years=range(2020, 2031))
    logger.info("✅ Holidays library loaded (trading calendar active)")
except ImportError:
    holidays = None
    US_HOLIDAYS = {}
    logger.warning("⚠️ Holidays library not available - install via: pip install holidays")

# TimescaleDB and market calendar imports
try:
    from main_production_system.data_infrastructure.timescale_fetcher import get_fetcher
    from main_production_system.data_infrastructure.market_calendar import get_market_calendar
    from main_production_system.data_infrastructure.data_quality_validator import (
        get_data_quality_validator,
    )
    TIMESCALE_AVAILABLE = True
except ImportError:
    TIMESCALE_AVAILABLE = False
    get_fetcher = None
    get_market_calendar = None

# For provider status tracking
_provider_manager_instance = None

# ES futures data handler
try:
    from core.data_providers.futures_data_handler import FuturesDataHandler
    FUTURES_HANDLER_AVAILABLE = True
except ImportError:
    FUTURES_HANDLER_AVAILABLE = False
    FuturesDataHandler = None

# Version info
try:
    from main_production_system import __version__
    SYSTEM_VERSION = __version__
except ImportError:
    SYSTEM_VERSION = "2.0.0"

# Retry decorator for API calls
def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry decorator with exponential backoff for API calls.
    Handles rate limiting gracefully.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a rate limit error
                    if 'rate' in str(e).lower() or 'limit' in str(e).lower() or '429' in str(e):
                        if attempt < max_retries - 1:
                            wait_time = base_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(
                                f"[RETRY] Rate limited on attempt {attempt + 1}/{max_retries}. "
                                f"Waiting {wait_time:.1f}s before retry..."
                            )
                            time.sleep(wait_time)
                        else:
                            logger.error(f"[RETRY] Max retries exceeded after {max_retries} attempts")
                            raise
                    else:
                        # Not a rate limit error, raise immediately
                        raise
            return None
        return wrapper
    return decorator


class UserFriendlyError(Exception):
    """Exception with user-friendly message and troubleshooting steps."""
    
    def __init__(self, technical_error: str, user_message: str, troubleshooting_steps: List[str]):
        self.technical_error = technical_error
        self.user_message = user_message
        self.troubleshooting_steps = troubleshooting_steps
        super().__init__(user_message)
    
    def display_in_streamlit(self):
        """Display error with troubleshooting in Streamlit UI."""
        st.error(f"❌ {self.user_message}")
        
        with st.expander("🔧 Troubleshooting Steps"):
            for i, step in enumerate(self.troubleshooting_steps, 1):
                st.markdown(f"{i}. {step}")
        
        with st.expander("🐛 Technical Details (for debugging)"):
            st.code(self.technical_error)


def is_market_open() -> bool:
    """
    Check if current time is during US market trading hours.
    
    Returns:
        True if market is open (9:30 AM - 4:00 PM ET, Monday-Friday), False otherwise
    """
    try:
        # Get current time in Eastern timezone (US market)
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5
        
        # Check if current time is within market hours
        is_market_time = market_open <= now <= market_close
        
        return is_weekday and is_market_time
    except Exception as e:
        logger.warning(f"[TTL] Failed to determine market hours: {e}, defaulting to market closed")
        return False


def get_market_aware_ttl(timeframe: str) -> int:
    """
    Get time-to-live (TTL) for cache based on market hours and timeframe.
    
    Uses shorter TTL during trading hours for fresher data, longer TTL after hours.
    
    Args:
        timeframe: Time interval ('1h', '4h', '1d', etc.)
    
    Returns:
        TTL in seconds (int)
    
    Strategy:
        - During market hours: Shorter TTL (more frequent refreshes)
          - 1h: 300s (5 min) - intraday data changes quickly
          - 4h: 600s (10 min) - 4h bars update every 4 hours
          - 1d: 1800s (30 min) - daily data less frequent
          - Other: 600s (10 min default)
        
        - After market hours: Longer TTL (data won't change until next session)
          - 1h: 3600s (1 hour)
          - 4h: 7200s (2 hours)
          - 1d: 86400s (24 hours) - daily won't change until next day
          - Other: 7200s (2 hours default)
    """
    market_open = is_market_open()
    
    # Define TTL based on timeframe and market status
    if market_open:
        # Trading hours: Shorter TTL for fresher data
        ttl_map = {
            '1h': 300,      # 5 minutes - intraday updates frequently
            '4h': 600,      # 10 minutes - 4h bars update every 4 hours
            '1d': 1800,     # 30 minutes - daily data less frequent
            'daily': 1800,  # 30 minutes
        }
    else:
        # After hours: Longer TTL (data won't change until market opens)
        ttl_map = {
            '1h': 3600,     # 1 hour
            '4h': 7200,     # 2 hours
            '1d': 86400,    # 24 hours - daily won't change until next day
            'daily': 86400, # 24 hours
        }
    
    ttl = ttl_map.get(timeframe.lower(), 600 if market_open else 7200)
    
    logger.debug(f"[TTL] Market {'OPEN' if market_open else 'CLOSED'}, timeframe={timeframe}, TTL={ttl}s")
    return ttl


def _log_with_context(level: str, message: str, **kwargs):
    """
    Enhanced logging with ISO 8601 timestamps and context.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **kwargs: Additional context to include in message
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    context_parts = []
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        context_parts.append(context)
    context_parts.append(f"version={SYSTEM_VERSION}")
    
    if context_parts:
        context_str = " | " + " | ".join(context_parts)
    else:
        context_str = ""
    
    full_message = f"[{timestamp}]{context_str} {message}"
    
    if level == "DEBUG":
        logger.debug(full_message)
    elif level == "INFO":
        logger.info(full_message)
    elif level == "WARNING":
        logger.warning(full_message)
    elif level == "ERROR":
        logger.error(full_message)


# Cached version with market-aware TTL (minimum 5 minutes)
# Note: TTL adjusts based on market hours - shorter during trading, longer after hours
# Uses Redis for multi-user scalability (falls back to Streamlit if unavailable)
@cached_function(ttl=300, show_spinner=False)  # Minimum TTL - actual TTL determined by get_market_aware_ttl
def _cached_load_market_data(symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Cached wrapper for market data loading."""
    return _load_market_data_impl(symbol, timeframe, days)


def load_market_data(symbol: str, timeframe: str = "1d", days: int = 365, force_refresh: bool = False, historical_days: int = None) -> pd.DataFrame:
    """
    Unified data loader with fallback chain and market-aware caching:
    1. Primary: yfinance (real-time, internet-dependent)
    2. Fallback 1: Cached CSV at data/cache/<symbol>_<timeframe>_<days>d.csv
    3. Fallback 2: Test data at tests/test_data/<symbol>_test_data.csv

    Uses market-aware TTL for intelligent caching:
    - During market hours: Shorter TTL (5-30 min depending on timeframe)
    - After hours: Longer TTL (1-24 hours depending on timeframe)

    Args:
        symbol: Stock ticker
        timeframe: Time interval ('1h', '4h', '1d', etc.)
        days: Number of historical days for display
        force_refresh: If True, bypass cache and fetch fresh data
        historical_days: Optional int - fetch extended history for SuperTrend AI K-Means (auto-calc if None)
    
    Returns:
        DataFrame with columns: ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
    Note:
        If historical_days is provided, fetches extended history (up to 10,000 bars).
        Auto-calculation targets 10,000 bars based on timeframe (e.g., 1d→40 years, 1h→417 days).
    """
    
    # Auto-calculate historical extent if not specified (for SuperTrend AI K-Means stability)
    if historical_days is None:
        # Map timeframe to approximate bars per trading day
        bars_per_day_map = {
            '1d': 1,      # 1 bar per day
            '1h': 6.5,    # ~6.5 trading hours
            '4h': 1.625,  # ~1.6 bars per day
            '5m': 78,     # ~78 5-min bars per trading day
            '1m': 390     # ~390 1-min bars per trading day
        }
        bars_per_day = bars_per_day_map.get(timeframe, 1)
        target_bars = 10000  # K-Means clustering ideal: 10K bars for stable factor selection
        historical_days = int(target_bars / bars_per_day)
        
        # Cap at reasonable limits (yfinance/Polygon constraints)
        # NOTE: yfinance intraday limit is 730d for 1h/4h and below
        max_days_map = {'1d': 14600, '1h': 730, '4h': 730, '5m': 60, '1m': 30}  # ~40y, 2y, 2y, 2mo, 1mo
        historical_days = min(historical_days, max_days_map.get(timeframe, 730))
        
        logger.info(f"[DATA] {symbol} {timeframe}: Auto-calc historical_days={historical_days} (target {int(historical_days * bars_per_day)} bars, yfinance cap applied)")
    
    # Use historical_days for fetching (wider context for K-Means), days for caching key
    fetch_days = historical_days if historical_days else days
    
    # If force refresh, clear cache and load fresh
    if force_refresh:
        try:
            _cached_load_market_data.clear()  # Clear cache
        except Exception:
            pass  # Cache might not exist yet
        return _load_market_data_impl(symbol, timeframe, fetch_days)
    
    # Use cached version (TTL handled by Streamlit, but we check expiration manually)
    ttl = get_market_aware_ttl(timeframe)
    
    # Try to get from cache (use historical_days as cache key if extended)
    cache_key_days = historical_days if historical_days else days
    try:
        return _cached_load_market_data(symbol, timeframe, cache_key_days)
    except Exception as e:
        logger.warning(f"[DATA] Cache load failed, falling back to direct load: {e}")
        return _load_market_data_impl(symbol, timeframe, fetch_days)


def _load_market_data_impl(symbol: str, timeframe: str = "1d", days: int = 365) -> pd.DataFrame:
    """
    Internal implementation of data loading (used by cached and direct paths).
    
    Returns a DataFrame with columns: ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    """

    # PRIMARY: yfinance
    try:
        logger.info(f"[DATA] Fetching {symbol} {timeframe} {days}d from yfinance...")
        df = yf.download(symbol, period=f"{days}d", interval=timeframe, progress=False)

        if df is None or df.empty:
            raise ValueError(f"Empty data from yfinance for {symbol}")

        # Standardize column names
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        df = df.reset_index()
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        logger.info(f"[DATA] ✅ SUCCESS: Loaded {len(df)} rows from yfinance")
        return df

    except Exception as e:
        logger.warning(f"[DATA] ⚠️ yfinance failed: {str(e)[:100]}. Trying fallback chain...")

    # FALLBACK 1: Cached CSV
    try:
        cache_dir = Path("data/cache")
        cache_file = cache_dir / f"{symbol}_{timeframe}_{days}d.csv"

        if cache_file.exists():
            logger.info(f"[DATA] Attempting cache fallback: {cache_file}...")
            df = pd.read_csv(cache_file)
            if df is None or df.empty:
                raise ValueError(f"Cache file exists but is empty: {cache_file}")
            logger.info(f"[DATA] ✅ SUCCESS: Loaded {len(df)} rows from cache")
            return df
        else:
            logger.warning(f"[DATA] Cache file not found: {cache_file}")

    except Exception as e:
        logger.warning(f"[DATA] ⚠️ Cache fallback failed: {str(e)[:100]}")

    # FALLBACK 2: Test data
    try:
        test_dir = Path("tests/test_data")
        test_file = test_dir / f"{symbol}_test_data.csv"

        if test_file.exists():
            logger.info(f"[DATA] Attempting test data fallback: {test_file}...")
            df = pd.read_csv(test_file)
            if df is None or df.empty:
                raise ValueError(f"Test file exists but is empty: {test_file}")
            logger.info(f"[DATA] ✅ SUCCESS: Loaded {len(df)} rows from test data")
            return df
        else:
            logger.warning(f"[DATA] Test data file not found: {test_file}")

    except Exception as e:
        logger.warning(f"[DATA] ⚠️ Test data fallback failed: {str(e)[:100]}")

    error_msg = (
        f"[DATA] ❌ CRITICAL: All data providers failed for {symbol}\n"
        f"  - yfinance: Network/API error\n"
        f"  - Cache: data/cache/{symbol}_{timeframe}_{days}d.csv not found\n"
        f"  - Test  tests/test_data/{symbol}_test_data.csv not found\n"
        f"  Action: Check internet, populate cache directory, or add test data."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)


def fetch_market_data_polygon(
    symbol: str,
    timeframe: str = '1h',
    days: int = 365,
    limit: int = 50000
) -> pd.DataFrame | None:
    """
    Fetch market data from Polygon.io with automatic fallback.
    
    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        timeframe: '1h', '4h', '1d', 'minute', 'weekly', 'monthly'
        days: Historical days (Polygon supports full 365 for 1h)
        limit: Max records to return
    
    Returns:
        DataFrame with OHLCV data (standardized format) or None
    """
    
    try:
        # Use secure secrets loader (st.secrets or env vars)
        try:
            from main_production_system.core.secure_secrets import get_polygon_key
            polygon_key = get_polygon_key()
        except ImportError:
            polygon_key = os.getenv('POLYGON_API_KEY')
        
        if not polygon_key:
            logger.warning("POLYGON_API_KEY not found - will use fallback providers")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"[DATA] Fetching {symbol} {timeframe} {days}d from Polygon.io...")
        
        # Try to use DataProviderManager if available
        try:
            from src.option_analysis.data_providers import DataProviderManager
            
            manager = DataProviderManager(polygon_key=polygon_key)
            
            # Fetch from Polygon (primary)
            df = manager.providers.get('polygon')
            if df:
                df_polygon = df.fetch(
                    symbol=symbol,
                    start=start_date,
                    end=end_date,
                    interval=timeframe
                )
                
                if df_polygon is not None and len(df_polygon) > 0:
                    # Standardize column names
                    rename_map = {
                        'timestamp': 'Date',
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }
                    df_polygon = df_polygon.rename(columns=rename_map)
                    
                    # Reset index if timestamp is the index
                    if df_polygon.index.name in ['timestamp', 'Date']:
                        df_polygon = df_polygon.reset_index()
                    
                    logger.info(f"[DATA] ✅ Polygon: {len(df_polygon)} candles fetched")
                    return df_polygon
            
        except Exception as e:
            logger.warning(f"[DATA] DataProviderManager approach failed: {e}")
        
        # Fallback: Try direct Polygon API if polygon package is installed
        try:
            from polygon import RESTClient
            
            client = RESTClient(api_key=polygon_key)
            
            # Map timeframe to Polygon's multiplier and timespan
            interval_map = {
                '1h': (1, 'hour'),
                '4h': (4, 'hour'),
                '1d': (1, 'day'),
                'daily': (1, 'day'),
                'minute': (1, 'minute'),
                'weekly': (1, 'week'),
                'monthly': (1, 'month')
            }
            
            multiplier, timespan = interval_map.get(timeframe.lower(), (1, 'day'))
            
            from_date_str = start_date.strftime('%Y-%m-%d')
            to_date_str = end_date.strftime('%Y-%m-%d')
            
            response = client.get_aggs(
                ticker=symbol.upper(),
                multiplier=multiplier,
                timespan=timespan,
                from_=from_date_str,
                to=to_date_str,
                limit=limit
            )
            
            # Convert to DataFrame
            data = []
            for agg in response:
                data.append({
                    'Date': pd.to_datetime(agg.timestamp, unit='ms'),
                    'Open': agg.open,
                    'High': agg.high,
                    'Low': agg.low,
                    'Close': agg.close,
                    'Volume': agg.volume
                })
            
            if data:
                df = pd.DataFrame(data)
                df = df.sort_values('Date').reset_index(drop=True)
                logger.info(f"[DATA] ✅ Polygon direct: {len(df)} candles fetched")
                return df
                
        except ImportError:
            logger.warning("[DATA] polygon-api-client not installed")
        except Exception as e:
            logger.warning(f"[DATA] Polygon direct API failed: {e}")
        
        # Fallback to Alpha Vantage
        logger.warning(f"[DATA] Polygon returned empty, trying Alpha Vantage...")
        try:
            from src.option_analysis.data_providers import DataProviderManager
            manager = DataProviderManager()
            df = manager.providers.get('alpha_vantage')
            if df:
                df_av = df.fetch(symbol, start_date, end_date, timeframe)
                if df_av is not None and len(df_av) > 0:
                    # Standardize column names
                    rename_map = {
                        'timestamp': 'Date',
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }
                    df_av = df_av.rename(columns=rename_map)
                    if df_av.index.name in ['timestamp', 'Date']:
                        df_av = df_av.reset_index()
                    logger.info(f"[DATA] ✅ Alpha Vantage: {len(df_av)} candles fetched")
                    return df_av
        except Exception as e:
            logger.warning(f"[DATA] Alpha Vantage fallback failed: {e}")
        
        # Final fallback to yfinance
        logger.warning(f"[DATA] Using yfinance fallback...")
        try:
            df_yf = yf.download(symbol, period=f'{days}d', interval=timeframe, progress=False)
            if df_yf is not None and not df_yf.empty:
                df_yf.columns = ["Open", "High", "Low", "Close", "Volume"]
                df_yf = df_yf.reset_index()
                df_yf.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
                logger.info(f"[DATA] ✅ yfinance: {len(df_yf)} candles fetched")
                return df_yf
        except Exception as e:
            logger.warning(f"[DATA] yfinance fallback failed: {e}")
        
        logger.error(f"[DATA] All providers failed for {symbol}")
        return None
        
    except Exception as e:
        logger.error(f"[DATA] Fetch failed: {e}", exc_info=True)
        return None


# Helper function to extract date range from DataFrame for cache
def _extract_date_range(df: pd.DataFrame) -> tuple:
    """
    Extract start and end dates from DataFrame for cache key.
    
    Returns:
        Tuple of (start_date_str, end_date_str) in YYYY-MM-DD format
    """
    if df is None or df.empty or 'Date' not in df.columns:
        # Fallback: use current date
        today = datetime.now().strftime('%Y-%m-%d')
        return today, today
    
    try:
        dates = pd.to_datetime(df['Date'])
        start_date = dates.min().strftime('%Y-%m-%d')
        end_date = dates.max().strftime('%Y-%m-%d')
        return start_date, end_date
    except Exception as e:
        logger.warning(f"[CACHE] Failed to extract date range: {e}")
        today = datetime.now().strftime('%Y-%m-%d')
        return today, today


# Cached version for load_and_engineer
# Uses Redis for multi-user scalability (falls back to Streamlit if unavailable)
@cached_function(ttl=300, show_spinner=False)  # Minimum TTL - actual TTL determined by get_market_aware_ttl
def _cached_load_and_engineer(symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Cached wrapper for load and engineer."""
    df = load_market_data(symbol, timeframe, days, force_refresh=False)
    df_clean = preprocess_ohlcv_data(df)
    
    # Build cache params for feature engineering
    start_date, end_date = _extract_date_range(df_clean)
    cache_params = {
        'symbol': symbol,
        'timeframe': timeframe,
        'start_date': start_date,
        'end_date': end_date
    }
    
    df_features = engineer_features(df_clean, cache_params=cache_params)
    return df_features


def load_and_engineer(symbol: str, timeframe: str = "1d", days: int = 365, force_refresh: bool = False, historical_days: int = None) -> pd.DataFrame:
    """
    Combined operation: Load data → Preprocess → Engineer features → Return enriched dataframe
    Main entry point for pages needing market data + features.
    
    NEW: Now includes preprocessing layer for data quality and governance.
    Uses market-aware TTL for intelligent caching.
    
    Args:
        symbol: Stock ticker
        timeframe: Time interval ('1h', '4h', '1d', etc.)
        days: Number of historical days for display
        force_refresh: If True, bypass cache and fetch fresh data
        historical_days: Optional int - fetch extended history for SuperTrend AI (auto-calc if None)
    
    Returns:
        DataFrame with engineered features
    """
    _log_with_context("INFO", "[PIPELINE] Starting unified load+preprocess+engineer", symbol=symbol, timeframe=timeframe, days=days)
    logger.info(f"[PIPELINE] Starting unified load+engineer for {symbol}...")
    
    try:
        if force_refresh:
            try:
                _cached_load_and_engineer.clear()  # Clear cache
            except Exception:
                pass
            # Direct load without cache (pass historical_days for extended context)
            df = load_market_data(symbol, timeframe, days, force_refresh=True, historical_days=historical_days)
            df_clean = preprocess_ohlcv_data(df)
            
            # Build cache params for feature engineering
            start_date, end_date = _extract_date_range(df_clean)
            cache_params = {
                'symbol': symbol,
                'timeframe': timeframe,
                'start_date': start_date,
                'end_date': end_date
            }
            
            df_features = engineer_features(df_clean, cache_params=cache_params)
            return df_features
        else:
            # Use cached version (note: _cached_load_and_engineer doesn't support historical_days param yet)
            # For now, if historical_days is specified, bypass cache
            if historical_days is not None:
                df = load_market_data(symbol, timeframe, days, force_refresh=False, historical_days=historical_days)
                df_clean = preprocess_ohlcv_data(df)
                
                start_date, end_date = _extract_date_range(df_clean)
                cache_params = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
                df_features = engineer_features(df_clean, cache_params=cache_params)
                return df_features
            else:
                return _cached_load_and_engineer(symbol, timeframe, days)
    except Exception as e:
        # Fallback to direct load on cache error
        logger.warning(f"[PIPELINE] Cache failed, using direct load: {e}")
        df = load_market_data(symbol, timeframe, days, force_refresh=False, historical_days=historical_days)
        _log_with_context("INFO", "[PIPELINE] Data loaded", rows=len(df))
        df_clean = preprocess_ohlcv_data(df)
        _log_with_context("INFO", "[PIPELINE] Preprocessing complete", rows=len(df_clean))
        
        # Build cache params for feature engineering
        start_date, end_date = _extract_date_range(df_clean)
        cache_params = {
            'symbol': symbol,
            'timeframe': timeframe,
            'start_date': start_date,
            'end_date': end_date
        }
        
        df_features = engineer_features(df_clean, cache_params=cache_params)
        _log_with_context("INFO", "[PIPELINE] Pipeline complete", rows=df_features.shape[0], features=df_features.shape[1])
        logger.info(f"[PIPELINE] ✅ Pipeline complete: {df_features.shape[0]} rows × {df_features.shape[1]} features")
        
        return df_features


def validate_ohlcv(df: pd.DataFrame) -> bool:
    """Validate OHLCV columns and NaN ratios for critical columns."""
    required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required_columns):
        logger.error(
            f"[VALIDATE] Missing required columns. Expected {required_columns}, got {df.columns.tolist()}"
        )
        return False

    nan_threshold = 0.1
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        nan_pct = df[col].isna().sum() / len(df) if len(df) else 1.0
        if nan_pct > nan_threshold:
            logger.error(
                f"[VALIDATE] Column '{col}' has {nan_pct*100:.1f}% NaN (threshold: {nan_threshold*100}%)"
            )
            return False

    logger.info("[VALIDATE] ✅ OHLCV validation passed")
    return True


def get_provider_status_summary() -> dict:
    """
    Get provider status summary for UI display.
    
    Returns:
        Dictionary with provider health, failover history, and rate limiter stats
    """
    global _provider_manager_instance
    
    try:
        from src.option_analysis.data_providers import DataProviderManager
        
        # Initialize or get existing provider manager instance
        if _provider_manager_instance is None:
            import os
            # Use secure secrets loader (st.secrets or env vars)
            try:
                from main_production_system.core.secure_secrets import get_polygon_key
                polygon_key = get_polygon_key()
            except ImportError:
                polygon_key = os.getenv('POLYGON_API_KEY')
            # Use secure secrets loader for Alpha Vantage key
            try:
                from main_production_system.core.secure_secrets import get_alpha_vantage_key
                alpha_key = get_alpha_vantage_key()
            except ImportError:
                alpha_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
            _provider_manager_instance = DataProviderManager(
                polygon_key=polygon_key,
                alpha_vantage_key=alpha_key
            )
        
        return _provider_manager_instance.get_provider_status_summary()
    except Exception as e:
        logger.warning(f"[PROVIDER_STATUS] Failed to get provider status: {e}")
        return {
            'current_provider': 'unknown',
            'provider_health': {},
            'recent_failovers': [],
            'rate_limiter_stats': {},
        }


def get_data_and_features(
    symbol: str, timeframe: str = "1d", days: int = 365, feature_set: str = "all", use_polygon: bool = True, force_refresh: bool = False, historical_days: int = None
):
    """
    Streamlined wrapper for pages: Get market data + engineered features in one call.
    
    NEW: Now includes preprocessing layer for data quality and governance.
    Uses market-aware TTL for intelligent caching.
    CACHING: Now uses Redis for multi-user scalability (falls back to Streamlit if unavailable)
    Tracks last fetch time in session state.
    
    Args:
        symbol: Stock ticker
        timeframe: Time interval ('1h', '4h', '1d', etc.)
        days: Number of historical days for display
        feature_set: Feature engineering set ('all', 'technical', 'statistical')
        use_polygon: If True, prioritize Polygon.io for data fetching
        force_refresh: If True, bypass cache and fetch fresh data
        historical_days: Optional int - fetch extended history for SuperTrend AI (auto-calc if None)
    
    Returns:
        Tuple: (raw_df, features_df)
    """
    _log_with_context("INFO", "[PIPELINE] Fetching data + features", symbol=symbol, use_polygon=use_polygon)
    logger.info(f"[PIPELINE] Fetching {symbol} data + features (use_polygon={use_polygon})...")
    
    try:
        # Use Data QA backfill engine for intraday paths
        if use_polygon and timeframe in ['1h', '4h']:
            # ============================================================================
            # GRACEFUL FALLBACK CHAIN: TimescaleDB → Timescale Fallback → Standard Pipeline
            # ============================================================================
            logger.info(f"[PIPELINE] Attempting data fetch with fallback chain for {symbol} {timeframe}...")

            df_raw = None
            df_features = None

            # LEVEL 1: Try TimescaleDB with quality assurance & backfill (BEST - 792 rows)
            try:
                logger.info(f"[PIPELINE] Level 1: Attempting TimescaleDB with quality assurance...")
                df_ohlcv, df_features = get_data_and_features_with_quality_assurance(
                    symbol=symbol,
                    timeframe=timeframe,
                    session_type='regular'
                )
                df_raw = df_ohlcv.copy()

                try:
                    logger.info(
                        f"[PIPELINE] ✅ Level 1 SUCCESS: TimescaleDB + quality assurance "
                        f"({len(df_raw)} rows, {df_raw['time'].min()} to {df_raw['time'].max()})"
                    )
                except Exception:
                    logger.info(f"[PIPELINE] ✅ Level 1 SUCCESS: {len(df_raw)} rows")

            # LEVEL 2: If TimescaleDB unavailable, try strict market-hours Timescale method (GOOD)
            except Exception as level1_err:
                logger.warning(
                    f"[PIPELINE] ⚠️  Level 1 failed ({type(level1_err).__name__}): {level1_err}. "
                    f"Attempting Level 2 (Timescale fallback)..."
                )

                try:
                    logger.info(f"[PIPELINE] Level 2: Attempting Timescale market-hours fallback...")
                    df_ohlcv, df_features = get_data_and_features_timescale_market_hours(
                        symbol=symbol,
                        timeframe=timeframe,
                        candle_count=1000,
                        session_type='regular'
                    )
                    df_raw = df_ohlcv.copy()

                    try:
                        logger.warning(
                            f"[PIPELINE] ⚠️  Level 2 FALLBACK USED: Timescale (no backfill) "
                            f"({len(df_raw)} rows, {df_raw['time'].min()} to {df_raw['time'].max()})\n"
                            f"         Note: This is < 792 rows - model quality may be reduced"
                        )
                    except Exception:
                        logger.warning(
                            f"[PIPELINE] ⚠️  Level 2 FALLBACK USED: Timescale (no backfill) ({len(df_raw)} rows)"
                        )

                # LEVEL 3: If Timescale also fails, use standard pipeline (ACCEPTABLE - always works)
                except Exception as level2_err:
                    logger.error(
                        f"[PIPELINE] ❌ Level 2 failed ({type(level2_err).__name__}): {level2_err}. "
                        f"Falling back to Level 3 (standard pipeline)..."
                    )

                    try:
                        logger.info(f"[PIPELINE] Level 3: Using standard pipeline (Polygon/YFinance)...")

                        # Determine lookback days based on timeframe
                        lookback_days_map = {
                            '1min': 5,      # ~1 week
                            '5min': 10,     # ~2 weeks
                            '15min': 20,    # ~1 month
                            '30min': 30,    # ~1 month
                            '1h': 180,      # ~6 months (approximates 792 rows @ 6.5/day)
                            '4h': 730,      # ~2 years
                            '1d': 730,      # ~2 years
                            '1wk': 1095,    # ~3 years
                            '1mo': 2190     # ~6 years
                        }
                        lookback_days = lookback_days_map.get(timeframe, 180)

                        # Use existing load_and_engineer function (pass historical_days for extended context)
                        df_features = load_and_engineer(
                            symbol,
                            timeframe,
                            days=lookback_days,
                            force_refresh=force_refresh,
                            historical_days=historical_days
                        )

                        # Extract OHLCV from features
                        ohlcv_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
                        available_cols = [c for c in ohlcv_cols if c in df_features.columns]
                        df_raw = df_features[available_cols].copy()

                        # Rename to lowercase, align time column
                        df_raw.columns = df_raw.columns.str.lower()
                        if 'date' in df_raw.columns:
                            df_raw = df_raw.rename(columns={'date': 'time'})

                        try:
                            logger.error(
                                f"[PIPELINE] ❌ Level 3 FALLBACK USED: Standard pipeline "
                                f"({len(df_raw)} rows, {df_raw['time'].min()} to {df_raw['time'].max()})\n"
                                f"         WARNING: Data quality/consistency not guaranteed"
                            )
                        except Exception:
                            logger.error(
                                f"[PIPELINE] ❌ Level 3 FALLBACK USED: Standard pipeline ({len(df_raw)} rows)"
                            )

                    except Exception as level3_err:
                        # COMPLETE FAILURE
                        logger.critical(
                            f"[PIPELINE] 🔴 ALL LEVELS FAILED:\n"
                            f"  Level 1 (TimescaleDB+QA): {type(level1_err).__name__}\n"
                            f"  Level 2 (Timescale):       {type(level2_err).__name__}\n"
                            f"  Level 3 (Standard):        {type(level3_err).__name__}"
                        )
                        raise RuntimeError(
                            f"Unable to fetch data for {symbol} {timeframe} from any source. "
                            f"Last error: {level3_err}"
                        )
        else:
            # Standard pipeline (includes preprocessing, pass historical_days for SuperTrend AI context)
            df_features = load_and_engineer(symbol, timeframe, days, force_refresh=force_refresh, historical_days=historical_days)
            df_raw = df_features[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        
        # Update last fetch time in session state
        try:
            from datetime import datetime
            st.session_state['last_fetch_time'] = datetime.now()
            st.session_state['last_fetch_symbol'] = symbol
            st.session_state['last_fetch_timeframe'] = timeframe
            
            # Update cache TTL
            ttl = get_market_aware_ttl(timeframe)
            st.session_state['cache_ttl_seconds'] = ttl
        except Exception as e:
            # Non-critical - just log warning
            logger.warning(f"[PIPELINE] Could not update session state: {e}")
        
        _log_with_context("INFO", "[PIPELINE] Complete", candles=len(df_raw), features=len(df_features.columns)-6)
        logger.info(f"[PIPELINE] ✅ Complete: {len(df_raw)} candles + {len(df_features.columns)-6} features")
        return df_raw, df_features
        
    except Exception as e:
        _log_with_context("ERROR", f"[PIPELINE] Failed: {str(e)}", symbol=symbol, exc_info=True)
        logger.exception(f"get_data_and_features failed for {symbol}")
        raise


def get_data_and_features_with_friendly_errors(symbol: str, timeframe: str, days: int, **kwargs):
    """Wrapper with user-friendly error messages."""
    try:
        return get_data_and_features(symbol, timeframe, days, **kwargs)
        
    except RuntimeError as e:
        error_str = str(e).lower()
        
        # Rate limit error
        if '429' in error_str or 'rate limit' in error_str:
            raise UserFriendlyError(
                technical_error=str(e),
                user_message="API rate limit reached. Too many requests in a short time.",
                troubleshooting_steps=[
                    "Wait 1-2 minutes and try again",
                    "Consider upgrading to a paid API plan for higher limits",
                    "Use the 'Manual Refresh' button instead of auto-refresh",
                    "For multi-symbol analysis, fetch symbols in smaller batches"
                ]
            )
        
        # All providers failed
        elif 'all providers failed' in error_str or 'all data providers failed' in error_str:
            raise UserFriendlyError(
                technical_error=str(e),
                user_message="Unable to fetch data from any provider (Polygon, Alpha Vantage, Yahoo Finance)",
                troubleshooting_steps=[
                    "Check your internet connection",
                    "Verify API keys are set correctly in `.streamlit/secrets.toml` or environment variables",
                    "Try a different symbol (some providers don't support all tickers)",
                    "Check provider status dashboards (Polygon Status, Yahoo Finance Status)",
                    "If using intraday data (1h/4h), try daily data first to verify connectivity"
                ]
            )
        
        # Invalid symbol
        elif 'invalid symbol' in error_str or 'no data returned' in error_str:
            raise UserFriendlyError(
                technical_error=str(e),
                user_message=f"Symbol '{symbol}' not found or has no data for the selected timeframe",
                troubleshooting_steps=[
                    f"Verify '{symbol}' is a valid ticker symbol",
                    "Try a common symbol like 'AAPL' or 'SPY' to test connectivity",
                    f"Check if '{symbol}' has trading history for the selected timeframe ({timeframe})",
                    "Some providers don't support all symbols - try switching provider in settings"
                ]
            )
        
        # Generic error
        else:
            raise UserFriendlyError(
                technical_error=str(e),
                user_message="An unexpected error occurred while fetching market data",
                troubleshooting_steps=[
                    "Refresh the page and try again",
                    "Check the Data Quality panel for more details",
                    "Try a different timeframe or shorter date range",
                    "Contact support if the issue persists"
                ]
            )
    
    except UserFriendlyError:
        # Re-raise UserFriendlyError as-is
        raise
    
    except Exception as e:
        # Catch-all for unexpected errors
        raise UserFriendlyError(
            technical_error=f"{type(e).__name__}: {str(e)}",
            user_message="An unexpected error occurred in the data pipeline",
            troubleshooting_steps=[
                "Refresh the page and try again",
                "Clear your browser cache",
                "Check the browser console for JavaScript errors",
                "If the issue persists, report this error to support"
            ]
        )


class AsyncDataPipeline:
    """
    Async data pipeline for parallel symbol fetching.
    
    Enables concurrent data fetching for multiple symbols with progress feedback.
    Uses ThreadPoolExecutor to run blocking I/O operations in parallel.
    """
    
    def __init__(self, max_workers: int = 3):
        """
        Initialize async data pipeline.
        
        Args:
            max_workers: Maximum number of concurrent workers (default: 3)
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"[ASYNC_PIPELINE] Initialized with {max_workers} workers")
    
    async def fetch_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str,
        days: int,
        use_polygon: bool = True,
        progress_callback: Optional[Callable[[int, int, str, bool, Optional[str]], None]] = None
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch multiple symbols in parallel with progress updates.
        
        Args:
            symbols: List of ticker symbols to fetch
            timeframe: Time interval ('1h', '4h', '1d')
            days: Historical days to fetch
            use_polygon: Use Polygon.io if True
            progress_callback: Optional callback function(current, total, symbol, success, error)
                Called with: (current_index, total, symbol, success_bool, error_message_or_None)
        
        Returns:
            Dict mapping symbol -> DataFrame (or None if fetch failed)
        """
        results = {}
        total = len(symbols)
        
        if total == 0:
            logger.warning("[ASYNC_PIPELINE] No symbols provided")
            return results
        
        logger.info(f"[ASYNC_PIPELINE] Starting parallel fetch for {total} symbols: {symbols}")
        
        loop = asyncio.get_event_loop()
        
        for i, symbol in enumerate(symbols):
            try:
                # Run blocking fetch in executor (non-blocking for other symbols)
                df_result = await loop.run_in_executor(
                    self.executor,
                    get_data_and_features,
                    symbol,
                    timeframe,
                    days,
                    'all',  # feature_set
                    use_polygon,
                    False  # force_refresh
                )
                
                # get_data_and_features returns (df_raw, df_features) tuple
                if isinstance(df_result, tuple):
                    df_features = df_result[1]  # Get features DataFrame
                else:
                    df_features = df_result
                
                results[symbol] = df_features
                
                # Progress callback for UI updates
                if progress_callback:
                    progress_callback(i + 1, total, symbol, success=True, error=None)
                
                logger.info(f"[ASYNC_PIPELINE] ✅ Fetched {symbol}: {len(df_features)} rows")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[ASYNC_PIPELINE] ❌ Failed to fetch {symbol}: {error_msg}")
                results[symbol] = None
                
                if progress_callback:
                    progress_callback(i + 1, total, symbol, success=False, error=error_msg)
        
        success_count = sum(1 for df in results.values() if df is not None)
        logger.info(f"[ASYNC_PIPELINE] ✅ Complete: {success_count}/{total} symbols fetched successfully")
        
        return results
    
    def close(self):
        """Cleanup executor resources."""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("[ASYNC_PIPELINE] Executor shutdown complete")


# ============================================================================
# TIMESCALEDB MARKET HOURS INTEGRATION
# ============================================================================

@st.cache_resource
def get_timescale_fetcher_market_hours():
    """Create fetcher with market hours enforcement"""
    if not TIMESCALE_AVAILABLE:
        logger.warning("TimescaleDB not available - install psycopg2-binary")
        return None
    
    try:
        fetcher = get_fetcher()
        if fetcher.is_connected():
            return fetcher
        else:
            logger.warning("TimescaleDB fetcher not connected")
            return None
    except Exception as e:
        logger.error(f"Failed to get TimescaleDB fetcher: {e}")
        return None


def get_data_and_features_timescale_market_hours(
    symbol: str,
    timeframe: str = '1d',
    candle_count: int = 1000,
    session_type: str = 'regular'  # 'regular', 'extended', or 'full'
):
    """
    Fetch data from TimescaleDB with STRICT market hours filtering.
    
    Guarantees:
    - Only trading days (M-F, not holidays)
    - Only market hours (9:30 AM - 4:00 PM ET for regular)
    - No pre-market or after-hours data (unless specified)
    
    Performance: <100ms due to database-level filtering
    
    Args:
        symbol: Stock ticker
        timeframe: '1h', '4h', or '1d'
        candle_count: Number of candles to fetch
        session_type: 'regular' (9:30-4:00), 'extended', or 'full'
    
    Returns:
        Tuple: (df_ohlcv, df_features) - both filtered to market hours
    """
    
    logger.info(
        f"[TIMESCALE_MKT] Fetching {candle_count} {timeframe} candles "
        f"for {symbol} (session: {session_type})"
    )
    
    try:
        fetcher = get_timescale_fetcher_market_hours()
        if fetcher is None:
            raise RuntimeError("TimescaleDB not available")
        
        calendar = get_market_calendar()
        
        # Check market status
        market_status = calendar.format_trading_status()
        logger.info(f"[MARKET_STATUS] {market_status}")
        
        if not fetcher.is_connected():
            logger.warning("[TIMESCALE] Database not connected")
            raise RuntimeError("TimescaleDB not available")
        
        # Fetch with market hours filter
        df_ohlcv, df_features = fetcher.get_ohlcv_extended_market_hours_only(
            symbol=symbol,
            timeframe=timeframe,
            candle_count=candle_count,
            include_features=True,
            session_type=session_type
        )
        
        if len(df_ohlcv) == 0:
            logger.warning("[TIMESCALE] No market hours data returned")
            raise RuntimeError("Empty result from TimescaleDB")
        
        # Convert time column to Date for consistency with existing pipeline
        if 'time' in df_ohlcv.columns:
            df_ohlcv = df_ohlcv.rename(columns={'time': 'Date'})
        
        if df_features is not None and 'time' in df_features.columns:
            df_features = df_features.rename(columns={'time': 'Date'})
        
        # Standardize column names (uppercase)
        rename_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }
        for old, new in rename_map.items():
            if old in df_ohlcv.columns:
                df_ohlcv = df_ohlcv.rename(columns={old: new})
        
        logger.info(
            f"[TIMESCALE_MKT] ✅ Loaded {len(df_ohlcv)} market-hours candles "
            f"({100*len(df_ohlcv)/candle_count:.1f}% of requested)"
        )
        
        return df_ohlcv, df_features
    
    except Exception as e:
        logger.error(f"[TIMESCALE_MKT] Failed: {e}")
        raise



def get_data_and_features_with_quality_assurance(
    symbol: str,
    timeframe: str = "1d",
    session_type: str = "regular",
    max_backfill_attempts: int = 5,
):
    """
    Fetch data with automatic backfilling until quality requirements are met.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (df_ohlcv, df_features)
    """
    logger = logging.getLogger(__name__)
    calendar = get_market_calendar() if get_market_calendar else None
    if calendar is None:
        raise RuntimeError("Market calendar not available")

    validator = get_data_quality_validator(calendar)

    logger.info(f"[DATA_QA] Starting fetch: {symbol} {timeframe} {session_type}")

    # Estimate parameters
    fetch_params = validator.estimate_data_fetch_params(timeframe, session_type)
    min_rows_required = fetch_params["minimum_rows_required"]
    trading_days_needed = fetch_params["minimum_trading_days"]

    logger.info(
        f"[DATA_QA] Requirements: {min_rows_required} rows ({trading_days_needed} trading days)"
    )

    attempt = 0
    current_start_date = datetime.fromisoformat(fetch_params["recommended_start_date"])  # type: ignore[arg-type]
    end_date = datetime.fromisoformat(fetch_params["recommended_end_date"])  # type: ignore[arg-type]

    while attempt < max_backfill_attempts:
        attempt += 1
        logger.info(
            f"[DATA_QA] Attempt {attempt}/{max_backfill_attempts}: Fetching {symbol} from {current_start_date.date()} to {end_date.date()}"
        )
        try:
            candle_count = max(
                1000,
                int(
                    trading_days_needed
                    * fetch_params["rows_per_day"]
                    * fetch_params["session_multiplier"]
                    * 1.5
                ),
            )

            df_ohlcv, df_features = get_data_and_features_timescale_market_hours(
                symbol=symbol,
                timeframe=timeframe,
                candle_count=candle_count,
                session_type=session_type,
            )

            validation = validator.validate_dataset(df_ohlcv, timeframe, session_type)
            logger.info(
                f"[DATA_QA] Validation: {validation['rows']} rows (need {validation['minimum_required']})"
            )

            if validation["is_valid"]:
                logger.info(f"[DATA_QA] ✅ Data quality check PASSED ({validation['rows']} rows)")
                return df_ohlcv, df_features

            logger.warning(
                f"[DATA_QA] Data insufficient: {validation['rows']} rows (need {validation['minimum_required']}, missing {validation['rows_needed']})"
            )
            extension_days = trading_days_needed * (attempt + 1)
            current_start_date = end_date - timedelta(days=int(extension_days * 1.5))
            logger.info(f"[DATA_QA] Extending backfill: {extension_days} more trading days")

        except Exception as e:
            logger.error(f"[DATA_QA] Fetch attempt {attempt} failed: {e}")
            if attempt < max_backfill_attempts:
                extension_days = trading_days_needed * (attempt + 1)
                current_start_date = end_date - timedelta(days=int(extension_days * 1.5))
                continue
            raise

    raise ValueError(
        f"Unable to fetch {min_rows_required} rows for {symbol} {timeframe} after {max_backfill_attempts} attempts"
    )


def load_es_and_stock_aligned(symbol: str, days: int = 252) -> Optional[Dict]:
    """
    Load ES futures and stock data with proper timezone/time alignment.
    
    This function uses FuturesDataHandler to:
    1. Fetch ES and stock data
    2. Align by trading hours + dates
    3. Calculate aligned returns
    4. Detect overnight gaps (informational)
    5. Return unified dataset ready for ARIMA-GARCH
    
    Args:
        symbol: Stock ticker symbol
        days: Number of days of historical data
        
    Returns:
        Dict with keys:
            - es_prices: Aligned ES prices DataFrame
            - stock_prices: Aligned stock prices DataFrame
            - es_returns: Aligned ES returns Series
            - stock_returns: Aligned stock returns Series
            - correlation: ES-Stock correlation
            - alignment_info: Alignment metadata
            - overnight_gaps: List of detected gaps
            - ready_for_arima_garch: bool
        None if data fetch fails
    """
    if not FUTURES_HANDLER_AVAILABLE:
        logger.error("[ES-ALIGN] FuturesDataHandler not available")
        return None
    
    try:
        handler = FuturesDataHandler()
        
        # Step 1: Fetch data
        es_data = handler.fetch_es_historical(days=days)
        stock_data = handler.fetch_stock_historical(symbol=symbol, days=days)
        
        if es_data is None or stock_data is None:
            logger.error('[ES-ALIGN] Failed to fetch futures/stock data')
            return None
        
        # Step 2: Align by trading hours + dates
        es_aligned, stock_aligned, alignment_info = handler.align_es_stock_data(es_data, stock_data)
        
        if es_aligned is None or stock_aligned is None:
            logger.error('[ES-ALIGN] Data alignment failed')
            return None
        
        logger.info(f'[ES-ALIGN] Alignment info: {alignment_info}')
        
        # Step 3: Calculate aligned returns
        es_returns, stock_returns, correlation = handler.calculate_returns_aligned(es_aligned, stock_aligned)
        
        if es_returns is None or stock_returns is None:
            logger.error('[ES-ALIGN] Returns calculation failed')
            return None
        
        # Step 4: Detect overnight gaps (informational)
        gaps = handler.handle_overnight_gaps(stock_aligned, es_aligned)
        
        # Step 5: Return unified dataset
        return {
            'es_prices': es_aligned,
            'stock_prices': stock_aligned,
            'es_returns': es_returns,
            'stock_returns': stock_returns,
            'correlation': correlation,
            'alignment_info': alignment_info,
            'overnight_gaps': gaps,
            'ready_for_arima_garch': True
        }
        
    except Exception as e:
        logger.error(f'[ES-ALIGN] Error in load_es_and_stock_aligned: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return None

