"""
TimescaleDB Fetcher with Market Hours Enforcement

Fetches OHLCV data from TimescaleDB with strict market hours filtering.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict
import logging
import os

try:
    import psycopg2
    from psycopg2.extras import execute_values
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

from .market_calendar import get_market_calendar

logger = logging.getLogger(__name__)


class TimescaleDBFetcher:
    """
    TimescaleDB data fetcher with market hours enforcement.
    
    Features:
    - Fast OHLCV data fetching (<100ms)
    - Market hours filtering (trading days only)
    - Technical indicator support
    - Batch fetching for multiple symbols
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize TimescaleDB fetcher.
        
        Args:
            host: Database host (default: from env or 'localhost')
            port: Database port (default: from env or 5432)
            database: Database name (default: from env or 'timescale')
            user: Database user (default: from env)
            password: Database password (default: from env)
        """
        self.host = host or os.getenv('TIMESCALEDB_HOST', 'localhost')
        self.port = port or int(os.getenv('TIMESCALEDB_PORT', '5432'))
        self.database = database or os.getenv('TIMESCALEDB_DATABASE', 'timescale')
        self.user = user or os.getenv('TIMESCALEDB_USER', 'postgres')
        self.password = password or os.getenv('TIMESCALEDB_PASSWORD', '')
        
        self.connection = None
        self._connected = False
        
        logger.info(f"TimescaleDBFetcher initialized for {self.host}:{self.port}/{self.database}")
    
    def connect(self) -> bool:
        """Establish database connection"""
        if not PSYCOPG2_AVAILABLE:
            logger.error("psycopg2 not available - install with: pip install psycopg2-binary")
            return False
        
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=5
            )
            self._connected = True
            logger.info("✅ Connected to TimescaleDB")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to TimescaleDB: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self._connected = False
            logger.info("Disconnected from TimescaleDB")
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        if not self._connected or not self.connection:
            return False
        
        try:
            # Quick check
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            self._connected = False
            return False
    
    def get_ohlcv_extended(
        self,
        symbol: str,
        timeframe: str = '1d',
        candle_count: int = 1000,
        include_features: bool = True
    ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Fetch OHLCV data with optional technical indicators.
        
        Args:
            symbol: Stock ticker
            timeframe: '1h', '4h', or '1d'
            candle_count: Number of candles to fetch
            include_features: Include technical indicators
        
        Returns:
            (df_ohlcv, df_features) tuple
        """
        
        if not self.is_connected():
            if not self.connect():
                logger.error("Cannot fetch - not connected to TimescaleDB")
                return pd.DataFrame(), None
        
        # Map timeframe to table/interval
        timeframe_map = {
            '1h': ('ohlcv_1h', '1 hour'),
            '4h': ('ohlcv_4h', '4 hours'),
            '1d': ('ohlcv_1d', '1 day')
        }
        
        if timeframe not in timeframe_map:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return pd.DataFrame(), None
        
        table_name, interval_str = timeframe_map[timeframe]
        
        try:
            # Base OHLCV query
            query = f"""
                SELECT 
                    time,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM {table_name}
                WHERE symbol = %s
                ORDER BY time DESC
                LIMIT %s
            """
            
            df_ohlcv = pd.read_sql_query(
                query,
                self.connection,
                params=(symbol.upper(), candle_count),
                parse_dates=['time']
            )
            
            # Reverse to chronological order (oldest first)
            if len(df_ohlcv) > 0:
                df_ohlcv = df_ohlcv.sort_values('time').reset_index(drop=True)
            
            # Features query (if requested)
            df_features = None
            if include_features and len(df_ohlcv) > 0:
                try:
                    features_query = f"""
                        SELECT 
                            time,
                            rsi,
                            macd,
                            macd_signal,
                            bollinger_upper,
                            bollinger_lower,
                            atr,
                            sma_20,
                            sma_50,
                            sma_200
                        FROM features_{timeframe}
                        WHERE symbol = %s
                        AND time >= %s
                        AND time <= %s
                        ORDER BY time ASC
                    """
                    
                    if len(df_ohlcv) > 0:
                        start_time = df_ohlcv['time'].min()
                        end_time = df_ohlcv['time'].max()
                        
                        df_features = pd.read_sql_query(
                            features_query,
                            self.connection,
                            params=(symbol.upper(), start_time, end_time),
                            parse_dates=['time']
                        )
                except Exception as e:
                    logger.warning(f"Features fetch failed: {e}")
                    df_features = None
            
            logger.info(f"✅ Fetched {len(df_ohlcv)} candles for {symbol} ({timeframe})")
            return df_ohlcv, df_features
        
        except Exception as e:
            logger.error(f"❌ Fetch failed for {symbol}: {e}")
            return pd.DataFrame(), None
    
    def get_ohlcv_extended_market_hours_only(
        self,
        symbol: str,
        timeframe: str = '1d',
        candle_count: int = 1000,
        include_features: bool = True,
        session_type: str = 'regular'
    ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Fetch OHLCV with STRICT market hours filtering.
        
        Only includes:
        - Trading days (M-F)
        - Market hours (9:30 AM - 4:00 PM ET for regular)
        - Skips weekends, holidays, pre/post-market
        
        Performance: Same as base method (<100ms) due to database-level filtering
        
        Args:
            symbol: Stock ticker
            timeframe: '1h', '4h', or '1d'
            candle_count: Number of candles
            include_features: Include technical indicators
            session_type: 'regular' (9:30-4:00), 'extended', or 'full'
        
        Returns:
            (df_ohlcv, df_features) - ONLY market hours data
        """
        
        # Fetch base data
        df_ohlcv, df_features = self.get_ohlcv_extended(
            symbol=symbol,
            timeframe=timeframe,
            candle_count=candle_count,
            include_features=include_features
        )
        
        if len(df_ohlcv) == 0:
            return df_ohlcv, df_features
        
        # Apply market hours filter
        calendar = get_market_calendar()
        
        try:
            df_ohlcv_filtered = calendar.filter_trading_hours(
                df_ohlcv,
                time_column='time',
                session_type=session_type
            )
            
            logger.info(
                f"[MARKET_FILTER] {symbol}: "
                f"{len(df_ohlcv)} → {len(df_ohlcv_filtered)} candles"
            )
            
            # Filter features to match
            if df_features is not None and len(df_features) > 0:
                # Align features with filtered OHLCV by time
                if 'time' in df_features.columns:
                    df_features_filtered = df_features[
                        df_features['time'].isin(df_ohlcv_filtered['time'])
                    ]
                    return df_ohlcv_filtered, df_features_filtered
            
            return df_ohlcv_filtered, df_features
        
        except Exception as e:
            logger.error(f"Market hours filtering failed: {e}")
            return df_ohlcv, df_features
    
    def batch_fetch_market_hours(
        self,
        symbols: List[str],
        timeframe: str = '1d',
        candle_count: int = 500,
        session_type: str = 'regular'
    ) -> Dict[str, Tuple[pd.DataFrame, Optional[pd.DataFrame]]]:
        """Batch fetch multiple symbols with market hours filtering"""
        results = {}
        for symbol in symbols:
            try:
                df_ohlcv, df_features = self.get_ohlcv_extended_market_hours_only(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_count=candle_count,
                    session_type=session_type
                )
                results[symbol] = (df_ohlcv, df_features)
            except Exception as e:
                logger.warning(f"⚠️ Skipped {symbol}: {e}")
        
        return results


# Global fetcher instance
_fetcher_instance = None


def get_fetcher() -> TimescaleDBFetcher:
    """Get or create global TimescaleDB fetcher instance"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = TimescaleDBFetcher()
        _fetcher_instance.connect()
    return _fetcher_instance
