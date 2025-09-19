"""
Rate limiting functionality for API endpoints
"""
from fastapi import HTTPException, Request, status
from typing import Optional, Dict, Any
import time
from functools import wraps
import asyncio
from app.core.redis import get_redis
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter using Redis for distributed rate limiting"""

    def __init__(self, requests: int, window: int, identifier_callback=None):
        """
        Initialize rate limiter

        Args:
            requests: Number of requests allowed
            window: Time window in seconds
            identifier_callback: Function to get identifier from request (default: IP address)
        """
        self.requests = requests
        self.window = window
        self.identifier_callback = identifier_callback or self._get_client_ip

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded IP (when behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    async def check_rate_limit(self, request: Request) -> bool:
        """
        Check if request should be rate limited

        Returns:
            True if request is within limits, False if rate limited
        """
        redis = get_redis()
        if not redis:
            # If Redis is not available, allow the request but log warning
            logger.warning("Redis not available for rate limiting")
            return True

        # Get identifier (IP address or custom)
        identifier = self.identifier_callback(request) if callable(self.identifier_callback) else self.identifier_callback

        # Create Redis key with endpoint path
        key = f"rate_limit:{request.url.path}:{identifier}"

        try:
            # Use Redis pipeline for atomic operations
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window)
            results = pipe.execute()

            request_count = results[0]

            if request_count > self.requests:
                return False

            return True

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On error, allow the request
            return True

    def __call__(self, func):
        """Decorator for rate limiting endpoints"""
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not await self.check_rate_limit(request):
                # Get remaining time for rate limit window
                redis = get_redis()
                if redis:
                    identifier = self.identifier_callback(request) if callable(self.identifier_callback) else self.identifier_callback
                    key = f"rate_limit:{request.url.path}:{identifier}"
                    ttl = redis.ttl(key)
                else:
                    ttl = self.window

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Please try again in {ttl} seconds.",
                    headers={"Retry-After": str(ttl)}
                )

            # Call the actual endpoint
            if asyncio.iscoroutinefunction(func):
                return await func(request, *args, **kwargs)
            else:
                return func(request, *args, **kwargs)

        return wrapper


def rate_limit(requests: int = 10, window: int = 60, identifier_callback=None):
    """
    Decorator for rate limiting endpoints

    Args:
        requests: Number of requests allowed (default: 10)
        window: Time window in seconds (default: 60)
        identifier_callback: Function to get identifier from request

    Example:
        @router.post("/login")
        @rate_limit(requests=5, window=60)  # 5 requests per minute
        async def login(request: Request, ...):
            ...
    """
    limiter = RateLimiter(requests, window, identifier_callback)
    return limiter


# Pre-configured rate limiters for common use cases
auth_rate_limit = rate_limit(requests=5, window=60)  # 5 requests per minute for auth endpoints
api_rate_limit = rate_limit(requests=60, window=60)  # 60 requests per minute for general API
strict_rate_limit = rate_limit(requests=3, window=300)  # 3 requests per 5 minutes for sensitive operations