#!/usr/bin/env python3
from fastapi import Request, HTTPException
import time
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter for API endpoints."""
    
    def __init__(self, requests_per_minute: int = 60, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = requests_per_minute
        self.window_seconds = window_seconds
        # Store IP -> list of timestamps
        self.request_history: Dict[str, List[float]] = {}
    
    def get_client_identifier(self, request: Request) -> str:
        """Get a unique identifier for the client (e.g., IP address)."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP if there are multiple in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Check for Vapi-specific headers that might help identify the source
        vapi_request_id = request.headers.get("X-Vapi-Request-Id", "")
        if vapi_request_id:
            return f"{client_ip}:{vapi_request_id}"
        
        return client_ip
    
    async def check_rate_limit(self, request: Request) -> Tuple[bool, Optional[Dict]]:
        """
        Check if the request should be rate limited.
        
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        client_id = self.get_client_identifier(request)
        
        # Initialize history for new clients
        if client_id not in self.request_history:
            self.request_history[client_id] = []
        
        # Clean up old timestamps
        self.request_history[client_id] = [
            ts for ts in self.request_history[client_id] 
            if now - ts < self.window_seconds
        ]
        
        # Calculate metrics
        current_count = len(self.request_history[client_id])
        is_allowed = current_count < self.max_requests
        
        # Record this request if allowed
        if is_allowed:
            self.request_history[client_id].append(now)
        
        # Calculate remaining requests
        remaining = max(0, self.max_requests - current_count)
        
        # Calculate reset time (when the oldest request expires)
        reset_time = (
            self.window_seconds - (now - min(self.request_history[client_id])) 
            if self.request_history[client_id] else self.window_seconds
        )
        
        # Periodically clean up clients we haven't seen in a while
        if len(self.request_history) > 1000:  # Arbitrary cleanup threshold
            self._cleanup_old_clients(now)
        
        rate_limit_info = {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": int(reset_time),
            "window": self.window_seconds
        }
        
        # Log rate limiting info
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_id}: {rate_limit_info}")
        
        return is_allowed, rate_limit_info
    
    def _cleanup_old_clients(self, now: float):
        """Remove clients that haven't made requests recently."""
        to_remove = []
        for client_id, timestamps in self.request_history.items():
            if not timestamps or now - max(timestamps) > self.window_seconds * 2:
                to_remove.append(client_id)
        
        for client_id in to_remove:
            del self.request_history[client_id]
        
        logger.info(f"Cleaned up {len(to_remove)} inactive clients from rate limiter")

# Create a global instance for use in the main application
rate_limiter = RateLimiter(requests_per_minute=60)

async def rate_limit_middleware(request: Request):
    """
    FastAPI middleware to apply rate limiting.
    
    Usage:
        @app.post("/vapi-search")
        async def vapi_search(request: Request, ...):
            await rate_limit_middleware(request)
            # Rest of your function
    """
    is_allowed, rate_limit_info = await rate_limiter.check_rate_limit(request)
    
    # Add rate limit headers
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(rate_limit_info["limit"]),
        "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
        "X-RateLimit-Reset": str(rate_limit_info["reset"])
    }
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "too_many_requests",
                "hint": f"Rate limit exceeded. Try again in {rate_limit_info['reset']} seconds."
            }
        ) 