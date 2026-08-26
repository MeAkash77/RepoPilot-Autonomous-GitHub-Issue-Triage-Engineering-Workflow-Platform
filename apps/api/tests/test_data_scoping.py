"""IDOR / tenant-isolation tests.

Two installations (login A, login B) with separate repos and runs. Verify:
- A sees only A's runs/repos/actions.
- A's request for B's run_id → 404 (not 403, to avoid existence disclosure).
- Dev caller (no login) sees all.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repopilot_api.deps import get_db
from repopilot_api.main import create_app
from repopilot_core.db import Installation, Issue, ProposedAction, Repo, TriageRun
from repopilot_core.db.models import ActionRisk, ActionType
from repopilot_core.settings import get_settings

KEY = "scoping-test-key"


@pytest.fixture
def client(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("INTERNAL_API_KEY", KEY)
    monkeypatch.setenv("GITHUB_APP_ID", "")
    get_settings.cache_clear()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    get_settings.cache_clear()


@pytest.fixture
async def two_tenant_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Seed two installations with one run each. Returns {a_run_id, b_run_id, a_action_id}."""
    async with session_factory() as session:
        inst_a = Installation(github_installation_id=101, account_login="alice")
        inst_b = Installation(github_installation_id=102, account_login="bob")
        session.add_all([inst_a, inst_b])
        await session.flush()

        repo_a = Repo(installation_id=inst_a.id, github_repo_id=201, full_name="alice/proj")
        repo_b = Repo(installation_id=inst_b.id, github_repo_id=202, full_name="bob/proj")
        session.add_all([repo_a, repo_b])
        await session.flush()

        issue_a = Issue(repo_id=repo_a.id, github_issue_number=1, title="A issue", body="")
        issue_b = Issue(repo_id=repo_b.id, github_issue_number=1, title="B issue", body="")
        session.add_all([issue_a, issue_b])
        await session.flush()

        run_a = TriageRun(issue_id=issue_a.id)
        run_b = TriageRun(issue_id=issue_b.id)
        session.add_all([run_a, run_b])
        await session.flush()

        action_a = ProposedAction(
            triage_run_id=run_a.id,
            action_type=ActionType.ADD_LABELS,
            payload={"labels": ["bug"]},
            risk=ActionRisk.LOW,
        )
        session.add(action_a)
        await session.commit()
        return {
            "a_run_id": run_a.id,
            "b_run_id": run_b.id,
            "a_action_id": action_a.id,
        }


def _headers(login: str | None = None) -> dict[str, str]:
    h = {"X-Internal-Key": KEY}
    if login:
        h["X-User-Login"] = login
    return h


# ── Runs ──────────────────────────────────────────────────────────────────────


async def test_alice_sees_only_her_runs(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get("/api/v1/runs", headers=_headers("alice"))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["repo_full_name"] == "alice/proj"


async def test_alice_cannot_see_bob_run(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get(f"/api/v1/runs/{two_tenant_seed['b_run_id']}", headers=_headers("alice"))
    assert r.status_code == 404


async def test_dev_caller_sees_all_runs(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get("/api/v1/runs", headers=_headers(None))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


# ── Repos ─────────────────────────────────────────────────────────────────────


async def test_alice_sees_only_her_repos(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get("/api/v1/repos", headers=_headers("alice"))
    assert r.status_code == 200
    assert all(repo["full_name"].startswith("alice/") for repo in r.json())


async def test_dev_caller_sees_all_repos(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get("/api/v1/repos", headers=_headers(None))
    assert r.status_code == 200
    assert len(r.json()) == 2


# ── Actions ───────────────────────────────────────────────────────────────────


async def test_alice_sees_only_her_actions(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.get("/api/v1/actions/pending", headers=_headers("alice"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["repo_full_name"] == "alice/proj"


async def test_bob_cannot_approve_alice_action(client: TestClient, two_tenant_seed: dict) -> None:
    r = client.post(
        f"/api/v1/actions/{two_tenant_seed['a_action_id']}/approve",
        json={},
        headers=_headers("bob"),
    )
    assert r.status_code == 404


# ── Analytics ─────────────────────────────────────────────────────────────────


async def test_analytics_scoped_to_caller(client: TestClient, two_tenant_seed: dict) -> None:
    r_alice = client.get("/api/v1/analytics/overview", headers=_headers("alice"))
    r_bob = client.get("/api/v1/analytics/overview", headers=_headers("bob"))
    assert r_alice.status_code == 200
    assert r_bob.status_code == 200
    # Each user sees only their 1 run.
    assert r_alice.json()["total_runs"] == 1
    assert r_bob.json()["total_runs"] == 1

    r_dev = client.get("/api/v1/analytics/overview", headers=_headers(None))
    assert r_dev.json()["total_runs"] == 2
