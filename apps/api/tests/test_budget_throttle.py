"""Per-installation daily budget: 501st issue delivery is ledgered THROTTLED, not enqueued."""

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
from repopilot_core.db.models import WebhookDeliveryStatus
from repopilot_core.settings import get_settings
from repopilot_github.webhooks import compute_signature

SECRET = "budget-test-secret"
CAP = 3  # Override to 3 for fast tests.


class FakeBudgetQueue:
    """Fake arq queue: tracks enqueues; simulates Redis INCR + EXPIRE."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []
        self._counters: dict[str, int] = {}

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((name, args))

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        pass


@pytest.fixture
def fake_queue() -> FakeBudgetQueue:
    return FakeBudgetQueue()


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession],
    fake_queue: FakeBudgetQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("MAX_RUNS_PER_INSTALL_PER_DAY", str(CAP))
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_queue] = lambda: fake_queue
    yield TestClient(app)
    get_settings.cache_clear()


def _issue_post(client: TestClient, delivery_id: str) -> Any:
    payload = {"action": "opened", "installation": {"id": 999}}
    body = json.dumps(payload).encode()
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": compute_signature(SECRET, body),
            "Content-Type": "application/json",
        },
    )


async def test_under_cap_enqueued(client: TestClient, fake_queue: FakeBudgetQueue) -> None:
    for i in range(CAP):
        r = _issue_post(client, f"d-under-{i}")
        assert r.status_code == 202
    assert len(fake_queue.jobs) == CAP


async def test_over_cap_throttled_not_enqueued(
    client: TestClient,
    fake_queue: FakeBudgetQueue,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Fill to cap.
    for i in range(CAP):
        _issue_post(client, f"d-fill-{i}")
    jobs_at_cap = len(fake_queue.jobs)

    # One more — should be throttled.
    r = _issue_post(client, "d-throttled")
    assert r.status_code == 202  # GitHub still gets 202
    assert len(fake_queue.jobs) == jobs_at_cap  # not enqueued

    # Delivery row should be THROTTLED.
    async with session_factory() as session:
        row = await session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.github_delivery_id == "d-throttled")
        )
    assert row is not None
    assert row.status == WebhookDeliveryStatus.THROTTLED


async def test_non_issue_events_not_counted(
    client: TestClient, fake_queue: FakeBudgetQueue
) -> None:
    """installation events bypass the budget counter entirely."""
    payload = {"action": "created", "installation": {"id": 999}}
    body = json.dumps(payload).encode()
    for i in range(CAP + 5):
        client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "installation",
                "X-GitHub-Delivery": f"d-inst-{i}",
                "X-Hub-Signature-256": compute_signature(SECRET, body),
            },
        )
    # None of these should count against budget; issue posts still work.
    r = _issue_post(client, "d-after-inst")
    assert r.status_code == 202
    assert any(job[0] == "process_webhook" for job in fake_queue.jobs)
