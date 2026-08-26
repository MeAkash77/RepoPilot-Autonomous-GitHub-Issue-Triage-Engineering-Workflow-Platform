"""Security middleware: body-size cap, security response headers, global error handler."""

import uuid

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = structlog.get_logger()

# Per-path body-size ceilings (bytes).
_WEBHOOK_MAX = 2 * 1024 * 1024  # 2 MB
_DEFAULT_MAX = 256 * 1024  # 256 KB

_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "X-Robots-Tag": "noindex, nofollow",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enforce body-size cap and inject security headers on every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Body-size guard — check Content-Length header first (fast path).
        content_length = request.headers.get("content-length")
        if content_length is not None:
            max_size = _WEBHOOK_MAX if request.url.path.startswith("/webhooks") else _DEFAULT_MAX
            if int(content_length) > max_size:
                return JSONResponse(
                    {"detail": "request body too large"},
                    status_code=413,
                )

        response = await call_next(request)

        # Inject security headers; skip Server header leak.
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        if "server" in response.headers:
            del response.headers["server"]

        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Mint or propagate X-Request-ID; bind it + route info to structlog context."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log full traceback, return opaque 500 to client."""
    logger.exception("unhandled_exception", path=request.url.path, exc_info=exc)
    return JSONResponse({"detail": "internal server error"}, status_code=500)
