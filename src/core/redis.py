"""Redis connection and utilities."""

import redis.asyncio as redis
from typing import Optional, Any
import json
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection pool."""
    global redis_pool, redis_client
    
    if not settings.REDIS_HOST:
        logger.warning("Redis not configured, skipping Redis initialization")
        return
    
    try:
        redis_pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT or 6379,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True,
            max_connections=20
        )
        
        redis_client = redis.Redis(connection_pool=redis_pool)
        
        # Test connection
        await redis_client.ping()
        logger.info("✅ Redis connected successfully")
        
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        redis_pool = None
        redis_client = None


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_pool, redis_client
    
    if redis_client:
        await redis_client.close()
    
    if redis_pool:
        await redis_pool.disconnect()
    
    redis_pool = None
    redis_client = None
    logger.info("Redis connection closed")


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client instance."""
    return redis_client


async def redis_set(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """Set a value in Redis with optional expiration."""
    if not redis_client:
        logger.warning("Redis not available")
        return False
    
    logger.debug("sett redis")
    
    try:
        # Serialize value to JSON if it's not a string
        if not isinstance(value, str):
            value = json.dumps(value)
        
        expire_time = expire or settings.REDIS_TTL
        await redis_client.setex(key, expire_time, value)
        return True
        
    except Exception as e:
        logger.error(f"Redis SET error for key {key}: {e}")
        return False


async def redis_get(key: str) -> Optional[Any]:
    """Get a value from Redis."""
    if not redis_client:
        logger.warning("Redis not available")
        return None
    
    try:
        value = await redis_client.get(key)
        if value is None:
            return None
        
        # Try to deserialize JSON, fallback to string
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
            
    except Exception as e:
        logger.error(f"Redis GET error for key {key}: {e}")
        return None


async def redis_delete(key: str) -> bool:
    """Delete a key from Redis."""
    if not redis_client:
        logger.warning("Redis not available")
        return False
    
    try:
        result = await redis_client.delete(key)
        return result > 0
        
    except Exception as e:
        logger.error(f"Redis DELETE error for key {key}: {e}")
        return False


async def redis_exists(key: str) -> bool:
    """Check if a key exists in Redis."""
    if not redis_client:
        return False
    
    try:
        result = await redis_client.exists(key)
        return result > 0
        
    except Exception as e:
        logger.error(f"Redis EXISTS error for key {key}: {e}")
        return False


async def redis_increment(key: str, amount: int = 1, expire: Optional[int] = None) -> Optional[int]:
    """Increment a counter in Redis."""
    if not redis_client:
        logger.warning("Redis not available")
        return None
    
    try:
        # Use pipeline for atomic operation
        async with redis_client.pipeline() as pipe:
            await pipe.incrby(key, amount)
            if expire:
                await pipe.expire(key, expire)
            results = await pipe.execute()
            return results[0]
            
    except Exception as e:
        logger.error(f"Redis INCREMENT error for key {key}: {e}")
        return None


async def redis_get_pattern(pattern: str) -> list:
    """Get all keys matching a pattern."""
    if not redis_client:
        return []
    
    try:
        keys = await redis_client.keys(pattern)
        return keys
        
    except Exception as e:
        logger.error(f"Redis KEYS error for pattern {pattern}: {e}")
        return []


async def redis_flush_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern."""
    if not redis_client:
        return 0
    
    try:
        keys = await redis_get_pattern(pattern)
        if not keys:
            return 0
        
        result = await redis_client.delete(*keys)
        return result
        
    except Exception as e:
        logger.error(f"Redis FLUSH error for pattern {pattern}: {e}")
        return 0
