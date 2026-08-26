"""Security headers present on API responses; body-size cap returns 413."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db
from repopilot_api.main import create_app
from repopilot_core.settings import get_settings

SECRET = "sec-header-test-key"


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("INTERNAL_API_KEY", SECRET)
    get_settings.cache_clear()

    async def override_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app, raise_server_exceptions=False)
    get_settings.cache_clear()


def test_security_headers_on_health(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert "max-age=" in (r.headers.get("strict-transport-security") or "")


def test_security_headers_on_gated_endpoint(client: TestClient) -> None:
    r = client.get("/api/v1/runs", headers={"X-Internal-Key": SECRET})
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_oversize_body_rejected(client: TestClient) -> None:
    # Provide a Content-Length header over the default 256 KB cap.
    oversize = 300 * 1024
    r = client.post(
        "/api/v1/runs",
        content=b"x" * oversize,
        headers={
            "X-Internal-Key": SECRET,
            "Content-Type": "application/json",
            "Content-Length": str(oversize),
        },
    )
    assert r.status_code == 413


def test_oversize_webhook_body_rejected(client: TestClient) -> None:
    oversize = 3 * 1024 * 1024  # 3 MB > 2 MB webhook cap
    r = client.post(
        "/webhooks/github",
        content=b"x" * oversize,
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "d-big",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "Content-Length": str(oversize),
        },
    )
    assert r.status_code == 413
