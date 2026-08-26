"""Live end-to-end against real GitHub + real LLMs.

Opt-in: set RUN_E2E=1 with a populated .env (GitHub App creds, LLM keys) and
the sandbox repo connected in the DB. Creates a throwaway issue, triages it,
asserts the agent posted a label back to GitHub, then closes the issue.

Kept out of the default suite so CI stays hermetic and free.
"""

import os

import pytest
from sqlalchemy import select

from repopilot_agent.deps import build_default_deps
from repopilot_agent.runner import execute_triage_run
from repopilot_core.db import Installation, Issue, Repo, TriageRun, get_session_factory
from repopilot_core.db.models import AutonomyLevel
from repopilot_github.client import GitHubAppClient

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.environ.get("RUN_E2E") != "1", reason="set RUN_E2E=1 to run"),
]

SANDBOX = os.environ.get("E2E_REPO", "AyushCoder9/repopilot-sandbox")


async def test_live_triage_posts_label_to_github() -> None:
    factory = get_session_factory()
    async with factory() as session:
        repo = await session.scalar(select(Repo).where(Repo.full_name == SANDBOX))
        if repo is None:
            pytest.skip(f"{SANDBOX} not connected in DB")
        installation = await session.get(Installation, repo.installation_id)
        assert installation is not None
        inst_id = installation.github_installation_id
        repo.autonomy_level = AutonomyLevel.AUTO_LOW_RISK
        await session.commit()

    client = GitHubAppClient()
    created = await client.request(
        inst_id,
        "POST",
        f"/repos/{SANDBOX}/issues",
        json={
            "title": "[e2e] login button crashes on mobile",
            "body": "Tapping login on iOS Safari throws a TypeError and the page goes blank. "
            "Stack: TypeError: undefined is not an object (evaluating 'session.token').",
        },
    )
    number = created["number"]

    try:
        async with factory() as session:
            repo = await session.scalar(select(Repo).where(Repo.full_name == SANDBOX))
            assert repo is not None
            issue = Issue(
                repo_id=repo.id,
                github_issue_number=number,
                title=created["title"],
                body=created["body"],
                author_login=created["user"]["login"],
                state="open",
            )
            session.add(issue)
            await session.flush()
            run = TriageRun(issue_id=issue.id)
            session.add(run)
            await session.commit()

            deps = build_default_deps(installation_id=inst_id)
            final = await execute_triage_run(session, deps, run, issue, repo)

        # The agent classified the report...
        assert final.classification is not None
        assert final.classification.type.value == "bug"
        # ...and a low-risk label auto-executed onto the live issue.
        live = await client.request(inst_id, "GET", f"/repos/{SANDBOX}/issues/{number}")
        label_names = {label["name"] for label in live.get("labels", [])}
        assert "bug" in label_names
    finally:
        await client.request(
            inst_id, "PATCH", f"/repos/{SANDBOX}/issues/{number}", json={"state": "closed"}
        )
        await client.aclose()
