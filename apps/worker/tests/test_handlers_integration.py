"""Integration: issues.opened webhook → worker handler → real Postgres.

Drives the full handle_issues path (persist issue, create run, execute the
graph, gate actions) against a real pgvector database with fake LLM/embedding
providers. Skipped when Postgres is unreachable; CI provides pgvector.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from repopilot_agent.graph import make_router
from repopilot_agent.nodes import NodeDeps
from repopilot_core.db import Installation, Issue, ProposedAction, Repo, TriageRun
from repopilot_core.db.models import TriageRunStatus
from repopilot_llm.embeddings import FakeEmbeddingProvider
from repopilot_llm.reranker import FakeReranker
from repopilot_llm.router import FakeChatProvider
from repopilot_worker import handlers

pytestmark = pytest.mark.integration

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://repopilot:repopilot@localhost:5432/repopilot"
)

FAKE_RESPONSES = {
    "Condense the GitHub issue": "upload crash large file",
    "issue classifier": (
        '{"type": "bug", "severity": 2, "confidence": 0.9,'
        ' "reasoning_summary": "Upload crashes on large files."}'
    ),
    "enough information": (
        '{"missing": ["version info"],'
        ' "asked_comment": "Could you share the app version you are using?"}'
    ),
}


@pytest.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect():
            pass
    except Exception:
        await engine.dispose()
        pytest.skip("postgres not reachable")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _fake_deps(
    session_factory: async_sessionmaker[AsyncSession], installation_id: int | None
) -> NodeDeps:
    fake = FakeChatProvider(responses=FAKE_RESPONSES, default="{}")
    return NodeDeps(
        session_factory=session_factory,
        router=make_router({"groq": fake, "gemini": fake}),
        embedder=FakeEmbeddingProvider(),
        reranker=FakeReranker(),
        github=None,  # no writes — actions stay pending
        installation_id=installation_id,
    )


async def test_issue_opened_runs_triage_and_persists_actions(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    async with factory() as session:
        installation = Installation(
            github_installation_id=int(suffix, 16), account_login=f"t-{suffix}"
        )
        session.add(installation)
        await session.flush()
        repo = Repo(
            installation_id=installation.id,
            github_repo_id=int(suffix, 16) + 1,
            full_name=f"test/{suffix}",
        )
        session.add(repo)
        await session.commit()
        repo_id, github_repo_id = repo.id, repo.github_repo_id

    monkeypatch.setattr(
        handlers,
        "build_default_deps",
        lambda installation_id=None: _fake_deps(factory, installation_id),
    )

    payload = {
        "action": "opened",
        "repository": {"id": github_repo_id, "full_name": f"test/{suffix}"},
        "issue": {
            "number": 1,
            "title": "Large file upload throws an error",
            "body": "Uploading a big file crashes the page with a TypeError about size.",
            "user": {"login": "reporter"},
            "state": "open",
            "labels": [],
        },
    }

    try:
        async with factory() as session:
            await handlers.handle_issues(session, payload)

        async with factory() as session:
            issue = await session.scalar(
                select(Issue).where(Issue.repo_id == repo_id, Issue.github_issue_number == 1)
            )
            assert issue is not None
            run = await session.scalar(select(TriageRun).where(TriageRun.issue_id == issue.id))
            assert run is not None
            # No GitHub client → low-risk actions cannot auto-execute, so the
            # run ends awaiting review with its proposed actions persisted.
            assert run.status == TriageRunStatus.AWAITING_REVIEW
            assert run.classification is not None
            assert run.classification["type"] == "bug"
            actions = (
                await session.scalars(
                    select(ProposedAction).where(ProposedAction.triage_run_id == run.id)
                )
            ).all()
            assert {a.action_type.value for a in actions} >= {"add_labels"}
    finally:
        # FKs are not ON DELETE CASCADE — remove children before parents.
        async with factory() as session:
            issue_ids = [
                i.id
                for i in (
                    await session.scalars(select(Issue).where(Issue.repo_id == repo_id))
                ).all()
            ]
            run_ids = [
                r.id
                for r in (
                    await session.scalars(
                        select(TriageRun).where(TriageRun.issue_id.in_(issue_ids or [-1]))
                    )
                ).all()
            ]
            if run_ids:
                await session.execute(
                    delete(ProposedAction).where(ProposedAction.triage_run_id.in_(run_ids))
                )
                await session.execute(delete(TriageRun).where(TriageRun.id.in_(run_ids)))
            if issue_ids:
                await session.execute(delete(Issue).where(Issue.id.in_(issue_ids)))
            await session.execute(delete(Repo).where(Repo.id == repo_id))
            await session.execute(
                delete(Installation).where(Installation.account_login == f"t-{suffix}")
            )
            await session.commit()
