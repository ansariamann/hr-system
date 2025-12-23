"""Redis connection and utilities."""

from typing import Optional
import redis.asyncio as redis
from redis.asyncio import Redis

from .config import settings
import structlog

logger = structlog.get_logger(__name__)


class RedisManager:
    """Manages Redis connections and operations."""
    
    def __init__(self, redis_url: str) -> None:
        """Initialize Redis manager.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.client: Optional[Redis] = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self.client is not None:
            logger.warning("Redis client already initialized")
            return
        
        self.client = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        
        # Test connection
        await self.client.ping()
        logger.info("Redis connection initialized", url=self.redis_url)
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
            self.client = None
    
    async def health_check(self) -> bool:
        """Check Redis connectivity.
        
        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            if self.client is None:
                return False
            
            await self.client.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False
    
    async def set_cache(
        self, 
        key: str, 
        value: str, 
        expire_seconds: Optional[int] = None
    ) -> bool:
        """Set cache value.
        
        Args:
            key: Cache key
            value: Cache value
            expire_seconds: Optional expiration time
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.client is None:
                raise RuntimeError("Redis not initialized")
            
            await self.client.set(key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error("Failed to set cache", key=key, error=str(e))
            return False
    
    async def get_cache(self, key: str) -> Optional[str]:
        """Get cache value.
        
        Args:
            key: Cache key
            
        Returns:
            Cache value or None if not found
        """
        try:
            if self.client is None:
                raise RuntimeError("Redis not initialized")
            
            return await self.client.get(key)
        except Exception as e:
            logger.error("Failed to get cache", key=key, error=str(e))
            return None
    
    async def delete_cache(self, key: str) -> bool:
        """Delete cache value.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.client is None:
                raise RuntimeError("Redis not initialized")
            
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error("Failed to delete cache", key=key, error=str(e))
            return False


# Global Redis manager instance
redis_manager = RedisManager(settings.redis_url)


async def get_redis() -> Redis:
    """Get Redis client instance.
    
    Returns:
        Redis client
        
    Raises:
        RuntimeError: If Redis is not initialized
    """
    if redis_manager.client is None:
        raise RuntimeError("Redis not initialized. Call initialize() first.")
    
    return redis_manager.client