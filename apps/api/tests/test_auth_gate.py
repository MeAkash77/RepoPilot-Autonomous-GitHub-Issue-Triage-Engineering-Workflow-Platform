"""BFF internal-key gate: dashboard endpoints reject callers without the key."""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db
from repopilot_api.main import create_app
from repopilot_core.settings import get_settings

SECRET = "test-internal-secret"


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("INTERNAL_API_KEY", SECRET)
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    get_settings.cache_clear()


def test_missing_key_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/actions/pending").status_code == 401


def test_wrong_key_is_rejected(client: TestClient) -> None:
    r = client.get("/api/v1/actions/pending", headers={"X-Internal-Key": "nope"})
    assert r.status_code == 401


def test_valid_key_passes(client: TestClient) -> None:
    r = client.get("/api/v1/actions/pending", headers={"X-Internal-Key": SECRET})
    assert r.status_code == 200


def test_health_stays_public(client: TestClient) -> None:
    # Liveness must not require the key.
    assert client.get("/healthz").status_code == 200
