"""Sliding-window rate limiter via slowapi + Redis (in-memory fallback for dev)."""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    """Key by X-User-Login (dashboard) or real client IP (webhooks/public)."""
    login = request.headers.get("x-user-login")
    if login:
        return f"user:{login}"
    return f"ip:{get_remote_address(request)}"


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 with Retry-After so clients know when to back off."""
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        {"detail": f"rate limit exceeded: {exc.detail}"},
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )


def make_limiter(redis_url: str | None = None) -> Limiter:
    """Build a Limiter backed by Redis in prod, in-memory otherwise."""
    if redis_url:
        # limits lib uses redis-py (sync) for rediss:// — no coredis needed.
        # Strip any existing scheme variations down to rediss:// or redis://.
        storage_uri = redis_url.replace("async+rediss://", "rediss://").replace(
            "async+redis://", "redis://"
        )
        return Limiter(key_func=_key_func, storage_uri=storage_uri)
    return Limiter(key_func=_key_func)


# Limits per endpoint tier (can be overridden via env/config).
WEBHOOK_LIMIT = "300/minute"
DASHBOARD_READ_LIMIT = "120/minute"
MUTATION_LIMIT = "30/minute"
STREAM_LIMIT = "10/minute"

__all__ = [
    "DASHBOARD_READ_LIMIT",
    "MUTATION_LIMIT",
    "STREAM_LIMIT",
    "WEBHOOK_LIMIT",
    "RateLimitExceeded",
    "SlowAPIMiddleware",
    "_rate_limit_exceeded_handler",
    "make_limiter",
]
