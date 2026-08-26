from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db
from repopilot_api.main import create_app
from repopilot_core.db import FeedbackEvent, Installation, Issue, ProposedAction, Repo, TriageRun
from repopilot_core.db.models import ActionRisk, ActionType
from repopilot_core.settings import get_settings


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    # Force empty app id so approve skips execution even when .env has a real key.
    monkeypatch.setenv("GITHUB_APP_ID", "")
    # Open the BFF gate for business-logic tests (gate is covered separately).
    monkeypatch.setenv("INTERNAL_API_KEY", "")
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


@pytest.fixture
async def seeded_action(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        installation = Installation(github_installation_id=1, account_login="a")
        session.add(installation)
        await session.flush()
        repo = Repo(installation_id=installation.id, github_repo_id=2, full_name="a/b")
        session.add(repo)
        await session.flush()
        issue = Issue(repo_id=repo.id, github_issue_number=7, title="t", body="b")
        session.add(issue)
        await session.flush()
        run = TriageRun(issue_id=issue.id)
        session.add(run)
        await session.flush()
        action = ProposedAction(
            triage_run_id=run.id,
            action_type=ActionType.ADD_LABELS,
            payload={"labels": ["bug"]},
            risk=ActionRisk.LOW,
        )
        session.add(action)
        await session.commit()
        return action.id


async def test_list_pending(client: TestClient, seeded_action: int) -> None:
    response = client.get("/api/v1/actions/pending")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["action_type"] == "add_labels"
    assert items[0]["repo_full_name"] == "a/b"
    assert items[0]["issue_number"] == 7


async def test_approve_records_feedback(
    client: TestClient,
    seeded_action: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = client.post(f"/api/v1/actions/{seeded_action}/approve", json={"reviewer": "ayush"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    async with session_factory() as session:
        feedback = (await session.scalars(select(FeedbackEvent))).all()
        assert len(feedback) == 1
        assert feedback[0].verdict.value == "approved"
        assert feedback[0].reviewer == "ayush"


async def test_approve_with_edit_records_edited_verdict(
    client: TestClient,
    seeded_action: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = client.post(
        f"/api/v1/actions/{seeded_action}/approve",
        json={"reviewer": "ayush", "edited_payload": {"labels": ["bug", "p1"]}},
    )
    assert response.status_code == 200
    async with session_factory() as session:
        feedback = (await session.scalars(select(FeedbackEvent))).one()
        assert feedback.verdict.value == "edited"
        assert feedback.edited_payload == {"labels": ["bug", "p1"]}
        action = await session.get(ProposedAction, seeded_action)
        assert action is not None and action.payload == {"labels": ["bug", "p1"]}


async def test_reject(client: TestClient, seeded_action: int) -> None:
    response = client.post(f"/api/v1/actions/{seeded_action}/reject", json={"reviewer": "ayush"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_double_review_conflicts(client: TestClient, seeded_action: int) -> None:
    client.post(f"/api/v1/actions/{seeded_action}/reject", json={})
    response = client.post(f"/api/v1/actions/{seeded_action}/approve", json={})
    assert response.status_code == 409


async def test_unknown_action_404(client: TestClient) -> None:
    assert client.post("/api/v1/actions/9999/approve", json={}).status_code == 404
