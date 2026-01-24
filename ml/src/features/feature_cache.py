"""Feature cache utilities for technical indicators."""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from typing import Optional

import pandas as pd

from src.data.supabase_db import SupabaseDatabase
from src.features.technical_indicators import add_technical_features

# Try to import redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_TIMEFRAMES = ["m15", "h1", "h4", "d1", "w1"]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _cache_window() -> timedelta:
    try:
        minutes = int(os.getenv("FEATURE_CACHE_MINUTES", "30"))
    except Exception:
        minutes = 30
    return timedelta(minutes=max(1, minutes))


def _is_cache_fresh(df: pd.DataFrame, since_ts: pd.Timestamp) -> bool:
    if df.empty:
        return False
    if "created_at" in df.columns:
        created_at = pd.to_datetime(df["created_at"], errors="coerce")
        if created_at.notna().any() and created_at.max() >= since_ts:
            return True
    return False


class DistributedFeatureCache:
    """Redis-backed distributed feature cache with TTL."""
    
    def __init__(self, redis_client=None, ttl_seconds=86400):
        """
        Initialize distributed cache.
        
        Args:
            redis_client: Redis connection (if None, no Redis caching)
            ttl_seconds: Cache TTL in seconds (default 24 hours)
        """
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.enabled = redis_client is not None and REDIS_AVAILABLE
    
    def get_cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key."""
        return f"features:v1:{symbol}:{timeframe}"
    
    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get features from Redis cache.
        
        Args:
            symbol: Symbol ticker
            timeframe: Timeframe (d1, h1, m15, etc.)
        
        Returns:
            DataFrame of features or None if not cached
        """
        if not self.enabled:
            return None
        
        try:
            key = self.get_cache_key(symbol, timeframe)
            data = self.redis_client.get(key)
            if data:
                # Deserialize JSON to dict, then convert to DataFrame
                records = json.loads(data)
                df = pd.DataFrame(records)
                logger.debug(f"Redis cache HIT: {symbol} {timeframe}")
                return df
        except Exception as e:
            logger.debug(f"Redis cache get error for {symbol} {timeframe}: {e}")
        
        return None
    
    def set(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """
        Set features in Redis cache with TTL.
        
        Args:
            symbol: Symbol ticker
            timeframe: Timeframe
            df: DataFrame to cache
        
        Returns:
            True if cached successfully
        """
        if not self.enabled:
            return False
        
        try:
            key = self.get_cache_key(symbol, timeframe)
            # Convert DataFrame to JSON (records format)
            # Note: We exclude 'created_at' if it exists since Redis TTL handles staleness
            data = df.to_json(orient='records', date_format='iso')
            self.redis_client.setex(key, self.ttl_seconds, data)
            logger.debug(f"Redis cache SET: {symbol} {timeframe} (TTL={self.ttl_seconds}s)")
            return True
        except Exception as e:
            logger.debug(f"Redis cache set error for {symbol} {timeframe}: {e}")
        
        return False
    
    def delete(self, symbol: str, timeframe: str) -> bool:
        """
        Delete features from Redis cache.
        
        Args:
            symbol: Symbol ticker
            timeframe: Timeframe
        
        Returns:
            True if deleted successfully
        """
        if not self.enabled:
            return False
        
        try:
            key = self.get_cache_key(symbol, timeframe)
            self.redis_client.delete(key)
            logger.debug(f"Redis cache DELETE: {symbol} {timeframe}")
            return True
        except Exception as e:
            logger.debug(f"Redis cache delete error for {symbol} {timeframe}: {e}")
        
        return False
    
    def clear_all(self, pattern: str = "features:v1:*") -> int:
        """
        Clear all features from cache matching pattern.
        
        Args:
            pattern: Redis key pattern
        
        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Redis cache cleared: {deleted} keys")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Redis cache clear error: {e}")
            return 0


def fetch_or_build_features(
    *,
    db: SupabaseDatabase,
    symbol: str,
    timeframes: list[str] | None = None,
    limits: dict[str, int] | None = None,
    redis_cache: Optional = None,
    cutoff_ts: pd.Timestamp | None = None,
    force_refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Fetch cached features or compute and store for requested timeframes.
    
    Cache priority:
    1. Redis (if redis_cache provided) - 24h TTL
    2. Database indicator_values - 30min freshness
    3. Rebuild from OHLC data
    
    Args:
        db: Database connection
        symbol: Symbol ticker
        timeframes: List of timeframes to fetch (default: DEFAULT_TIMEFRAMES)
        limits: Optional dict of per-timeframe row limits
        redis_cache: Optional Redis client for distributed caching
        cutoff_ts: Optional cutoff timestamp (exclusive) used to prevent
            lookahead in training windows. If set, caches are bypassed.
        force_refresh: Skip caches and rebuild features from OHLC data.
    
    Returns:
        Dict mapping timeframe to DataFrame of features
    """
    tfs = timeframes or DEFAULT_TIMEFRAMES
    limit_map = limits or {}
    symbol_id = db.get_symbol_id(symbol)
    since_ts = pd.Timestamp.now('UTC') - _cache_window()
    results: dict[str, pd.DataFrame] = {}
    use_cache = (not force_refresh) and (cutoff_ts is None)
    
    # Initialize Redis cache wrapper if provided
    redis_enabled = redis_cache is not None and _bool_env("REDIS_FEATURE_CACHE", default=True)
    distributed_cache = DistributedFeatureCache(redis_client=redis_cache) if redis_enabled else None

    for timeframe in tfs:
        limit = limit_map.get(timeframe)
        
        # === Priority 1: Check Redis cache (fastest) ===
        if use_cache and distributed_cache:
            redis_cached = distributed_cache.get(symbol, timeframe)
            if redis_cached is not None and not redis_cached.empty:
                # Apply limit if specified
                if limit:
                    redis_cached = redis_cached.tail(limit)
                results[timeframe] = redis_cached
                continue
        
        # === Priority 2: Check DB indicator_values cache ===
        if use_cache:
            cached = db.fetch_indicator_values(symbol_id, timeframe, limit=limit)
            if _bool_env("ENABLE_FEATURE_CACHE", default=True) and _is_cache_fresh(
                cached,
                since_ts,
            ):
                results[timeframe] = cached
                
                # Store in Redis for next worker
                if distributed_cache:
                    distributed_cache.set(symbol, timeframe, cached)
                
                continue

        # === Priority 3: Rebuild from OHLC data ===
        ohlc = db.fetch_ohlc_bars(
            symbol,
            timeframe=timeframe,
            limit=limit,
            end_ts=cutoff_ts,
        )
        if cutoff_ts is not None and not ohlc.empty and "ts" in ohlc.columns:
            ohlc = ohlc[ohlc["ts"] < cutoff_ts].copy()
        if ohlc.empty:
            results[timeframe] = ohlc
            continue

        features = add_technical_features(ohlc)
        
        # Store in both caches
        if use_cache and _bool_env("ENABLE_FEATURE_CACHE", default=True):
            db.upsert_indicator_values(symbol_id, timeframe, features)
        
        if use_cache and distributed_cache:
            distributed_cache.set(symbol, timeframe, features)
        
        results[timeframe] = features

    return results
