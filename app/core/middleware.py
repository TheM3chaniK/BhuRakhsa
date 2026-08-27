from collections import defaultdict
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional
import uuid

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.logging import logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing secure HTTP response headers and correlation ID tracking."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Request correlation ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Security Headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"

        # Internal execution timing logged
        if request.url.path not in ("/health", "/api/v1/health"):
            logger.info(
                "[%s] %s %s completed with %d in %.2fms",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        return response


class RateLimiter:
    """In-memory sliding-window rate limiter for sensitive routes."""

    def __init__(self) -> None:
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if the given key has exceeded max_requests in the window."""
        now = time.time()
        cutoff = now - window_seconds

        # Clean old timestamps
        timestamps = [ts for ts in self._records[key] if ts > cutoff]
        if len(timestamps) >= max_requests:
            self._records[key] = timestamps
            return True

        timestamps.append(now)
        self._records[key] = timestamps
        return False

    def clear(self) -> None:
        self._records.clear()


limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing request rate limits on sensitive endpoints."""

    SENSITIVE_PATHS = {
        "/api/v1/auth/login": (10, 60),        # 10 requests per minute
        "/api/v1/auth/register": (5, 60),      # 5 registrations per minute
        "/api/v1/auth/refresh": (30, 60),      # 30 refreshes per minute
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in self.SENSITIVE_PATHS:
            max_reqs, window = self.SENSITIVE_PATHS[path]
            client_ip = request.client.host if request.client else "unknown"
            key = f"{path}:{client_ip}"

            if limiter.is_rate_limited(key, max_reqs, window):
                logger.warning("Rate limit exceeded for client %s on %s", client_ip, path)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please wait before retrying.",
                        }
                    },
                    headers={"Retry-After": str(window)},
                )

        return await call_next(request)
