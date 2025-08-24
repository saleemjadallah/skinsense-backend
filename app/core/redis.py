import redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Redis client instance
redis_client = None

def get_redis():
    """Get Redis client instance"""
    global redis_client
    
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
            redis_client = None
    
    return redis_client

def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        redis_client.close()
        redis_client = None
        logger.info("Disconnected from Redis")