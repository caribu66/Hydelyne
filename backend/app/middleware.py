from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.cache import cache_service

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging request details and timing (structured)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        request.state.request_id = request_id

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client": client_ip,
                },
            )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{duration:.3f}"
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request_error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                    "client": client_ip,
                },
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # CSP is intentionally conservative; allow self + fonts + data/inline where needed
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: https://images.unsplash.com https://api.dicebear.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self'; "
            "connect-src 'self' https://api.gemini.google.com; "
            "frame-ancestors 'self';",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based distributed rate limiting per IP."""

    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}"

        try:
            if await cache_service.is_redis_available():
                count = await cache_service.increment_rate_limit(key, self.window_seconds)
                if count and count > self.requests_per_minute:
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded. Try again later.",
                            "retry_after": self.window_seconds,
                        },
                    )
        except Exception as e:
            # Fail-open with security degradation signal: blocking traffic
            # because Redis is down would be a worse availability event than
            # letting requests through unmetered. See ADR-0002.
            logger.warning("security_degradation: rate limit lookup failed, failing open: %s", e)

        return await call_next(request)
