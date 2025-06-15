"""Rate limiting middleware with Redis support."""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import logging
import json
from typing import Dict, Tuple, Optional
import asyncio

from src.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis-based tracking."""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        """Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            calls: Number of calls allowed per period
            period: Time period in seconds
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.redis_prefix = "rate_limit"
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        # Check if request should be rate limited
        if await self._is_rate_limited(request, client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Too many requests.",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )
        
        # Update request count
        await self._update_request_count(client_ip)
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    async def _is_rate_limited(self, request: Request, client_ip: str) -> bool:
        """Check if the client IP is rate limited using Redis."""
        redis = await get_redis()
        if not redis:
            logger.warning("Redis not available, skipping rate limiting")
            return False
            
        current_time = time.time()
        redis_key = f"{self.redis_prefix}:{client_ip}"
        
        try:
            # Get client data from Redis
            client_data_str = await redis.get(redis_key)
            if client_data_str:
                client_data = json.loads(client_data_str)
            else:
                client_data = {"requests": [], "blocked_until": 0}
            
            # Check if client is currently blocked
            if current_time < client_data["blocked_until"]:
                return True
            
            # Clean old requests (outside the time window)
            client_data["requests"] = [
                req_time for req_time in client_data["requests"]
                if current_time - req_time < self.period
            ]
            
            # Check if limit exceeded
            if len(client_data["requests"]) >= self.calls:
                # Block for the remaining time window
                oldest_request = min(client_data["requests"]) if client_data["requests"] else current_time
                client_data["blocked_until"] = oldest_request + self.period
                
                # Save updated data to Redis
                await redis.setex(
                    redis_key, 
                    self.period * 2,  # TTL longer than period
                    json.dumps(client_data)
                )
                
                logger.warning(f"Rate limit exceeded for IP {client_ip}. Blocked until {client_data['blocked_until']}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            return False
    
    async def _update_request_count(self, client_ip: str) -> None:
        """Update request count for the client IP in Redis."""
        redis = await get_redis()
        if not redis:
            return
            
        current_time = time.time()
        redis_key = f"{self.redis_prefix}:{client_ip}"
        
        try:
            # Get current data
            client_data_str = await redis.get(redis_key)
            if client_data_str:
                client_data = json.loads(client_data_str)
            else:
                client_data = {"requests": [], "blocked_until": 0}
            
            # Add current request
            client_data["requests"].append(current_time)
            
            # Save to Redis with TTL
            await redis.setex(
                redis_key, 
                self.period * 2,  # TTL longer than period
                json.dumps(client_data)
            )
            
        except Exception as e:
            logger.error(f"Redis error updating request count: {e}")


class AuthRateLimitingMiddleware(BaseHTTPMiddleware):
    """Specialized rate limiting for authentication endpoints using Redis."""
    
    def __init__(self, app, calls: int = 5, period: int = 300):  # 5 attempts per 5 minutes
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.redis_prefix = "auth_rate_limit"
    
    async def dispatch(self, request: Request, call_next):
        # Only apply to auth endpoints
        if not self._is_auth_endpoint(request):
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        # Check rate limit for auth endpoints
        if await self._is_auth_rate_limited(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many authentication attempts. Please try again later.",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )
        
        response = await call_next(request)
        
        # If auth attempt failed, increment counter
        if self._is_failed_auth(response):
            await self._update_auth_attempt_count(client_ip)
        elif self._is_successful_auth(response):
            # Reset counter on successful auth
            await self._reset_auth_attempts(client_ip)
        
        return response
    
    def _is_auth_endpoint(self, request: Request) -> bool:
        """Check if request is to an authentication endpoint."""
        auth_paths = ["/api/v1/auth/login", "/api/v1/auth/register"]
        return request.url.path in auth_paths and request.method == "POST"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def _is_auth_rate_limited(self, client_ip: str) -> bool:
        """Check if auth attempts are rate limited using Redis."""
        redis = await get_redis()
        if not redis:
            logger.warning("Redis not available, skipping auth rate limiting")
            return False
            
        current_time = time.time()
        redis_key = f"{self.redis_prefix}:{client_ip}"
        
        try:
            # Get client data from Redis
            client_data_str = await redis.get(redis_key)
            if client_data_str:
                client_data = json.loads(client_data_str)
            else:
                client_data = {"attempts": [], "blocked_until": 0}
            
            # Check if blocked
            if current_time < client_data["blocked_until"]:
                return True
            
            # Clean old attempts
            client_data["attempts"] = [
                attempt_time for attempt_time in client_data["attempts"]
                if current_time - attempt_time < self.period
            ]
            
            return len(client_data["attempts"]) >= self.calls
            
        except Exception as e:
            logger.error(f"Redis error checking auth rate limit: {e}")
            return False
    
    async def _update_auth_attempt_count(self, client_ip: str) -> None:
        """Update failed auth attempt count in Redis."""
        redis = await get_redis()
        if not redis:
            return
            
        current_time = time.time()
        redis_key = f"{self.redis_prefix}:{client_ip}"
        
        try:
            # Get current data
            client_data_str = await redis.get(redis_key)
            if client_data_str:
                client_data = json.loads(client_data_str)
            else:
                client_data = {"attempts": [], "blocked_until": 0}
            
            # Add failed attempt
            client_data["attempts"].append(current_time)
            
            # If limit reached, block for the period
            if len(client_data["attempts"]) >= self.calls:
                client_data["blocked_until"] = current_time + self.period
                logger.warning(f"Auth rate limit exceeded for IP {client_ip}")
            
            # Save to Redis with TTL
            await redis.setex(
                redis_key, 
                self.period * 2,  # TTL longer than period
                json.dumps(client_data)
            )
            
        except Exception as e:
            logger.error(f"Redis error updating auth attempt count: {e}")
    
    async def _reset_auth_attempts(self, client_ip: str) -> None:
        """Reset auth attempts on successful login in Redis."""
        redis = await get_redis()
        if not redis:
            return
            
        redis_key = f"{self.redis_prefix}:{client_ip}"
        
        try:
            # Delete the key to reset attempts
            await redis.delete(redis_key)
            
        except Exception as e:
            logger.error(f"Redis error resetting auth attempts: {e}")
    
    def _is_failed_auth(self, response) -> bool:
        """Check if response indicates failed authentication."""
        return response.status_code in [401, 403, 423]  # Unauthorized, Forbidden, Locked
    
    def _is_successful_auth(self, response) -> bool:
        """Check if response indicates successful authentication."""
        return response.status_code == 200


def add_rate_limiting(app):
    """Add rate limiting middleware to the application."""
    from src.core.config import settings
    
    # General rate limiting
    app.add_middleware(
        RateLimitingMiddleware, 
        calls=settings.RATE_LIMIT_CALLS, 
        period=settings.RATE_LIMIT_PERIOD
    )
    
    # Auth-specific rate limiting
    app.add_middleware(
        AuthRateLimitingMiddleware, 
        calls=settings.AUTH_RATE_LIMIT_CALLS, 
        period=settings.AUTH_RATE_LIMIT_PERIOD
    )
