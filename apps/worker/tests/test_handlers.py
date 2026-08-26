from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from repopilot_core.db import Base, Installation, Repo
from repopilot_worker.handlers import (
    handle_installation,
    handle_installation_repositories,
    handle_issues,
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _installation_payload(action: str, repos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "action": action,
        "installation": {"id": 42, "account": {"login": "ayush"}},
        "repositories": repos or [],
    }


REPO_A = {"id": 1001, "full_name": "ayush/project-a", "default_branch": "main"}
REPO_B = {"id": 1002, "full_name": "ayush/project-b", "default_branch": "develop"}


async def test_installation_created_persists_repos(session: AsyncSession) -> None:
    await handle_installation(session, _installation_payload("created", [REPO_A, REPO_B]))
    await session.commit()

    installation = await session.scalar(select(Installation))
    assert installation is not None
    assert installation.github_installation_id == 42

    repos = (await session.scalars(select(Repo).order_by(Repo.github_repo_id))).all()
    assert [r.full_name for r in repos] == ["ayush/project-a", "ayush/project-b"]
    assert repos[1].default_branch == "develop"


async def test_installation_deleted_removes_everything(session: AsyncSession) -> None:
    await handle_installation(session, _installation_payload("created", [REPO_A]))
    await session.commit()
    await handle_installation(session, _installation_payload("deleted"))
    await session.commit()

    assert (await session.scalars(select(Installation))).all() == []
    assert (await session.scalars(select(Repo))).all() == []


async def test_repositories_added_and_removed(session: AsyncSession) -> None:
    await handle_installation(session, _installation_payload("created", [REPO_A]))
    await session.commit()

    payload = {
        "installation": {"id": 42, "account": {"login": "ayush"}},
        "repositories_added": [REPO_B],
        "repositories_removed": [REPO_A],
    }
    await handle_installation_repositories(session, payload)
    await session.commit()

    repos = (await session.scalars(select(Repo))).all()
    assert [r.full_name for r in repos] == ["ayush/project-b"]


async def test_issue_opened_on_unconnected_repo_is_noop(session: AsyncSession) -> None:
    payload = {
        "action": "opened",
        "repository": {"id": 9999, "full_name": "stranger/repo"},
        "issue": {"number": 1},
    }
    await handle_issues(session, payload)  # must not raise


async def test_issue_non_opened_action_ignored(session: AsyncSession) -> None:
    payload = {"action": "closed", "repository": {"id": 1}, "issue": {"number": 1}}
    await handle_issues(session, payload)  # must not raise
