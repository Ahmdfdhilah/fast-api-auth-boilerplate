"""Cache utilities using Redis."""

import functools
import hashlib
import json
from typing import Any, Callable, Optional
import logging
from src.core.redis import redis_get, redis_set, redis_delete, redis_exists

logger = logging.getLogger(__name__)


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    # Create a string representation of all arguments
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    
    # Create a hash of the key for consistent length
    return hashlib.md5(key_string.encode()).hexdigest()


def redis_cache(expire: int = 3600, key_prefix: str = "cache"):
    """
    Decorator to cache function results in Redis.
    
    Args:
        expire: Cache expiration time in seconds
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            func_name = f"{func.__module__}.{func.__name__}"
            key_suffix = cache_key(*args, **kwargs)
            cache_key_name = f"{key_prefix}:{func_name}:{key_suffix}"
            
            # Try to get from cache first
            cached_result = await redis_get(cache_key_name)
            if cached_result is not None:
                logger.debug(f"Cache HIT for {func_name}")
                return cached_result
            
            # Call the function and cache result
            logger.debug(f"Cache MISS for {func_name}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            await redis_set(cache_key_name, result, expire)
            
            return result
        
        # Add cache management methods
        wrapper.cache_clear = lambda *args, **kwargs: redis_delete(
            f"{key_prefix}:{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"
        )
        wrapper.cache_exists = lambda *args, **kwargs: redis_exists(
            f"{key_prefix}:{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"
        )
        
        return wrapper
    return decorator


class CacheManager:
    """Centralized cache management."""
    
    def __init__(self, prefix: str = "app"):
        self.prefix = prefix
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        full_key = f"{self.prefix}:{key}"
        return await redis_get(full_key)
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache."""
        full_key = f"{self.prefix}:{key}"
        return await redis_set(full_key, value, expire)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        full_key = f"{self.prefix}:{key}"
        return await redis_delete(full_key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        full_key = f"{self.prefix}:{key}"
        return await redis_exists(full_key)
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        from src.core.redis import redis_flush_pattern
        full_pattern = f"{self.prefix}:{pattern}"
        return await redis_flush_pattern(full_pattern)


# Global cache manager instance
cache = CacheManager()
