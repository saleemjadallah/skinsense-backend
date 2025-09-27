"""
Redis caching service for frequently accessed data
"""
import json
import redis
from typing import Optional, Any, Dict
from datetime import timedelta
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Service for caching frequently accessed data in Redis"""
    
    def __init__(self):
        """Initialize Redis connection"""
        try:
            # Parse Redis URL for connection
            if settings.REDIS_URL.startswith("redis://"):
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
            else:
                # Fallback to localhost if URL format is different
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✓ Connected to Redis cache")
            self.is_available = True
            
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self.redis_client = None
            self.is_available = False
    
    def _get_key(self, prefix: str, identifier: str) -> str:
        """Generate cache key with prefix"""
        return f"skinsense:{prefix}:{identifier}"
    
    def get(self, prefix: str, identifier: str) -> Optional[Dict[str, Any]]:
        """Get cached data"""
        if not self.is_available:
            return None
            
        try:
            key = self._get_key(prefix, identifier)
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, prefix: str, identifier: str, data: Dict[str, Any], 
            ttl_seconds: int = 300) -> bool:
        """Set cached data with TTL"""
        if not self.is_available:
            return False
            
        try:
            key = self._get_key(prefix, identifier)
            json_data = json.dumps(data)
            self.redis_client.setex(
                key,
                ttl_seconds,
                json_data
            )
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, prefix: str, identifier: str) -> bool:
        """Delete cached data"""
        if not self.is_available:
            return False
            
        try:
            key = self._get_key(prefix, identifier)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user"""
        if not self.is_available:
            return
            
        try:
            # Patterns to invalidate
            patterns = [
                f"skinsense:progress:{user_id}",
                f"skinsense:routines:{user_id}",
                f"skinsense:goals:{user_id}",
                f"skinsense:achievements:{user_id}",
                f"skinsense:insights:{user_id}",
                f"skinsense:analysis_history:{user_id}",
                f"skinsense:progress_summary:{user_id}*",
                f"skinsense:progress_trends:{user_id}*",
                f"skinsense:progress_insights:{user_id}*",
                f"skinsense:metric_progress:{user_id}*",
            ]
            
            for pattern in patterns:
                keys = self.redis_client.keys(pattern + "*")
                if keys:
                    self.redis_client.delete(*keys)
                    
            logger.info(f"Invalidated cache for user {user_id}")
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")

# Global cache instance
cache_service = CacheService()

# Cache decorators for common patterns
def cache_result(prefix: str, ttl_seconds: int = 300):
    """Decorator to cache function results"""
    def decorator(func):
        async def wrapper(user_id: str, *args, **kwargs):
            # Try to get from cache first
            cached = cache_service.get(prefix, user_id)
            if cached is not None:
                logger.debug(f"Cache hit for {prefix}:{user_id}")
                return cached
            
            # Get fresh data
            result = await func(user_id, *args, **kwargs)
            
            # Cache the result
            if result:
                cache_service.set(prefix, user_id, result, ttl_seconds)
                
            return result
        return wrapper
    return decorator