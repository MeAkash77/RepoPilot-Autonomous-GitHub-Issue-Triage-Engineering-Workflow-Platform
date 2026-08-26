"""Rate limiter mechanism test.

We can't easily trigger the real routes' 120/minute limit in unit tests.
Instead we build a minimal app with a 2/minute limit to prove the
SlowAPI + SecurityMiddleware stack correctly returns 429 + Retry-After.

We also verify that create_app() exposes app.state.limiter (configured)
and that the real routes still return 200 under normal usage.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db
from repopilot_api.main import create_app
from repopilot_api.middleware import SecurityMiddleware
from repopilot_api.ratelimit import (
    RateLimitExceeded,
    SlowAPIMiddleware,
    _rate_limit_exceeded_handler,
    make_limiter,
)
from repopilot_core.settings import get_settings

KEY = "rl-test-key"


# ── Mechanism test (isolated mini-app with a 2/minute route) ─────────────────


@pytest.fixture
def tight_client() -> TestClient:
    """Minimal app with a route limited to 2/minute."""
    limiter = make_limiter(None)  # in-memory

    mini = FastAPI()
    mini.state.limiter = limiter
    mini.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    mini.add_middleware(SecurityMiddleware)
    mini.add_middleware(SlowAPIMiddleware)

    @mini.get("/ping")
    @limiter.limit("2/minute")
    async def ping(request: Request) -> dict:  # type: ignore[return]
        return {"ok": True}

    return TestClient(mini, raise_server_exceptions=False)


def test_rate_limit_429_after_burst(tight_client: TestClient) -> None:
    statuses = [tight_client.get("/ping").status_code for _ in range(4)]
    assert 429 in statuses, f"Expected 429 in {statuses}"


def test_rate_limit_allows_under_limit(tight_client: TestClient) -> None:
    assert tight_client.get("/ping").status_code == 200
    assert tight_client.get("/ping").status_code == 200


def test_retry_after_header_present(tight_client: TestClient) -> None:
    responses = [tight_client.get("/ping") for _ in range(5)]
    throttled = [r for r in responses if r.status_code == 429]
    assert throttled, "No 429 produced"
    assert "retry-after" in throttled[0].headers


# ── Real app: limiter wired, normal usage still 200 ──────────────────────────


@pytest.fixture
def real_client(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("INTERNAL_API_KEY", KEY)
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    get_settings.cache_clear()


def test_limiter_attached_to_app(real_client: TestClient) -> None:
    assert hasattr(real_client.app, "state")
    assert real_client.app.state.limiter is not None


def test_normal_request_not_throttled(real_client: TestClient) -> None:
    r = real_client.get("/api/v1/repos", headers={"X-Internal-Key": KEY})
    assert r.status_code == 200
