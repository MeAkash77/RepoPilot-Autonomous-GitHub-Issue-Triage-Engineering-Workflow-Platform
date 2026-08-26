import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db, get_queue
from repopilot_api.main import create_app
from repopilot_core.db import WebhookDelivery
from repopilot_core.settings import get_settings
from repopilot_github.webhooks import compute_signature

SECRET = "webhook-test-secret"


class FakeQueue:
    """Records enqueued jobs instead of touching Redis."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((name, args))


@pytest.fixture
def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession],
    fake_queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_queue] = lambda: fake_queue
    return TestClient(app)


def _post(client: TestClient, payload: dict[str, Any], event: str, delivery_id: str) -> Any:
    body = json.dumps(payload).encode()
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": compute_signature(SECRET, body),
            "Content-Type": "application/json",
        },
    )


def test_invalid_signature_rejected(client: TestClient) -> None:
    response = client.post(
        "/webhooks/github",
        content=b"{}",
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "d-1",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert response.status_code == 401


def test_missing_signature_rejected(client: TestClient) -> None:
    response = client.post(
        "/webhooks/github",
        content=b"{}",
        headers={"X-GitHub-Event": "issues", "X-GitHub-Delivery": "d-1"},
    )
    assert response.status_code == 401


def test_valid_delivery_ledgered_and_enqueued(
    client: TestClient,
    fake_queue: FakeQueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = _post(client, {"action": "opened"}, "issues", "d-100")
    assert response.status_code == 202
    assert fake_queue.jobs and fake_queue.jobs[0][0] == "process_webhook"


def test_duplicate_delivery_not_reenqueued(client: TestClient, fake_queue: FakeQueue) -> None:
    assert _post(client, {"action": "opened"}, "issues", "d-200").status_code == 202
    assert _post(client, {"action": "opened"}, "issues", "d-200").status_code == 202
    assert len(fake_queue.jobs) == 1


def test_unhandled_event_acknowledged_not_ledgered(
    client: TestClient, fake_queue: FakeQueue
) -> None:
    response = _post(client, {"zen": "ok"}, "ping", "d-300")
    assert response.status_code == 202
    assert fake_queue.jobs == []


async def test_delivery_row_written(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _post(client, {"action": "opened"}, "issues", "d-400")
    async with session_factory() as session:
        row = await session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.github_delivery_id == "d-400")
        )
    assert row is not None
    assert row.event_type == "issues"
    assert row.payload == {"action": "opened"}
