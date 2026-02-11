"""
Enterprise-grade Redis caching for multi-user scalability.

Falls back to Streamlit cache if Redis unavailable.

Author: Cursor Agent
Created: 2025-01-27
"""

import pickle
import hashlib
import logging
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=False,  # Keep binary for pickle
        socket_timeout=5
    )
    # Test connection
    redis_client.ping()
    logger.info("[CACHE] ✅ Redis connection established")
except Exception as e:
    REDIS_AVAILABLE = False
    redis_client = None
    logger.warning(f"[CACHE] Redis unavailable, falling back to Streamlit cache: {e}")


class RedisCacheManager:
    """
    Distributed cache manager with Redis backend.
    Automatically falls back to Streamlit cache if Redis unavailable.
    """

    def __init__(self, namespace: str = "ml_dashboard"):
        self.namespace = namespace
        self.redis_available = REDIS_AVAILABLE and redis_client is not None

        if self.redis_available:
            logger.info(f"[CACHE] Using Redis cache (namespace: {namespace})")
        else:
            logger.info("[CACHE] Using Streamlit fallback cache")

    def cache_key(self, *args, **kwargs) -> str:
        """
        Generate cache key from function arguments.
        Format: {namespace}:{function_name}:{hash_of_args}
        """
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])

        key_string = ":".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()

        return f"{self.namespace}:{key_hash}"

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        Returns None if not found or expired.
        """
        if not self.redis_available:
            return None

        try:
            cached_value = redis_client.get(key)

            if cached_value is None:
                logger.debug(f"[CACHE] MISS: {key}")
                return None

            # Deserialize
            value = pickle.loads(cached_value)
            logger.debug(f"[CACHE] HIT: {key}")
            return value

        except Exception as e:
            logger.warning(f"[CACHE] Get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        """
        Store value in cache with TTL (seconds).

        Args:
            key: Cache key
            value: Value to cache (must be pickleable)
            ttl: Time-to-live in seconds (default 5 minutes)
        """
        if not self.redis_available:
            return False

        try:
            # Serialize
            serialized = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

            # Set with expiration
            redis_client.setex(key, ttl, serialized)

            logger.debug(f"[CACHE] SET: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"[CACHE] Set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.redis_available:
            return False

        try:
            result = redis_client.delete(key)
            logger.debug(f"[CACHE] DELETE: {key}")
            return result > 0

        except Exception as e:
            logger.warning(f"[CACHE] Delete error for {key}: {e}")
            return False

    def clear_namespace(self) -> int:
        """
        Clear all keys in this namespace.
        Returns count of deleted keys.
        """
        if not self.redis_available:
            return 0

        try:
            pattern = f"{self.namespace}:*"
            keys = list(redis_client.scan_iter(match=pattern))

            if keys:
                deleted = redis_client.delete(*keys)
                logger.info(f"[CACHE] Cleared {deleted} keys from namespace {self.namespace}")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"[CACHE] Clear namespace error: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.redis_available:
            return {'status': 'redis_unavailable', 'fallback': 'streamlit'}

        try:
            info = redis_client.info('stats')

            pattern = f"{self.namespace}:*"
            namespace_keys = len(list(redis_client.scan_iter(match=pattern, count=1000)))

            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total_requests = hits + misses
            hit_rate = hits / max(1, total_requests)

            return {
                'status': 'redis_active',
                'total_keys': info.get('db0', {}).get('keys', 0) if isinstance(info.get('db0'), dict) else 0,
                'namespace_keys': namespace_keys,
                'hits': hits,
                'misses': misses,
                'hit_rate': hit_rate,
                'used_memory_human': info.get('used_memory_human', 'N/A')
            }

        except Exception as e:
            logger.error(f"[CACHE] Stats error: {e}")
            return {'status': 'error', 'message': str(e)}


# Global cache instance
_cache_manager = RedisCacheManager()


def cached_function(ttl: int = 300, show_spinner: bool = False):
    """
    Decorator for caching function results with Redis.
    Falls back to Streamlit cache if Redis unavailable.

    Usage:
        @cached_function(ttl=600)
        def expensive_function(symbol: str, days: int):
            # ... expensive computation
            return result
    """
    def decorator(func: Callable):
        # If Redis unavailable, use Streamlit cache (which already has .clear() method)
        if not _cache_manager.redis_available:
            import streamlit as st
            return st.cache_data(ttl=ttl, show_spinner=show_spinner)(func)

        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _cache_manager.cache_key(func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_result = _cache_manager.get(cache_key)

            if cached_result is not None:
                return cached_result

            # Cache miss - compute result
            result = func(*args, **kwargs)

            # Store in cache
            _cache_manager.set(cache_key, result, ttl=ttl)

            return result

        # Add clear() method for compatibility with Streamlit cache API
        def clear_cache():
            """Clear all cached results for this function."""
            # Clear all keys matching this function's namespace
            try:
                # Use the global redis_client (already imported at module level)
                if redis_client:
                    pattern = f"{_cache_manager.namespace}:*"
                    keys = list(redis_client.scan_iter(match=pattern))
                    if keys:
                        redis_client.delete(*keys)
                        logger.info(f"[CACHE] Cleared {len(keys)} keys for {func.__name__}")
            except Exception as e:
                logger.warning(f"[CACHE] Failed to clear cache for {func.__name__}: {e}")

        wrapper.clear = clear_cache
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator

