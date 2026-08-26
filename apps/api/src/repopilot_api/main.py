"""FastAPI application entrypoint."""

from fastapi import Depends, FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware

from repopilot_api.deps import require_internal
from repopilot_api.middleware import (
    RequestContextMiddleware,
    SecurityMiddleware,
    global_exception_handler,
)
from repopilot_api.ratelimit import (
    RateLimitExceeded,
    SlowAPIMiddleware,
    _rate_limit_exceeded_handler,
    make_limiter,
)
from repopilot_api.routes.actions import router as actions_router
from repopilot_api.routes.analytics import router as analytics_router
from repopilot_api.routes.health import router as health_router
from repopilot_api.routes.observability import router as observability_router
from repopilot_api.routes.repos import router as repos_router
from repopilot_api.routes.runs import router as runs_router
from repopilot_api.routes.search import router as search_router
from repopilot_api.routes.webhooks import router as webhooks_router
from repopilot_core.logging import configure_logging
from repopilot_core.settings import get_settings
from repopilot_core.telemetry import init_telemetry


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.environment, settings.log_level)
    init_telemetry("api")
    app = FastAPI(
        title="RepoPilot API",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
    )

    # Rate limiter — Redis-backed in prod, in-memory in dev.
    redis_url = str(settings.redis_url) if settings.environment != "local" else None
    limiter = make_limiter(redis_url)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, global_exception_handler)

    # Middleware (outermost first).
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    # CORS — locked to the web front-end origin; webhooks/health are unaffected
    # (GitHub never sends CORS preflight).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["X-Internal-Key", "X-User-Login", "Content-Type"],
    )

    # Trusted-host guard — only enforced in production to avoid dev friction.
    if settings.environment == "production":
        # Include localhost so Fly's internal health checker (Host: localhost) passes.
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["repopilot-api.fly.dev", "*.fly.dev"],
        )

    # Public: health (liveness) and webhooks (HMAC-verified separately).
    app.include_router(health_router)
    app.include_router(webhooks_router)

    # Dashboard data — gated behind the BFF internal key.
    gated = [Depends(require_internal)]
    app.include_router(actions_router, dependencies=gated)
    app.include_router(runs_router, dependencies=gated)
    app.include_router(repos_router, dependencies=gated)
    app.include_router(analytics_router, dependencies=gated)
    app.include_router(observability_router, dependencies=gated)
    app.include_router(search_router, dependencies=gated)
    return app


app = create_app()
