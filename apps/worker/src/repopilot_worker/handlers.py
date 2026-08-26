"""Webhook event handlers.

Each handler is a pure-ish async function taking (session, payload) so it
can be unit-tested without arq. process_webhook is the arq entrypoint: it
loads the ledgered delivery, dispatches, and records outcome.
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repopilot_agent.deps import build_default_deps
from repopilot_agent.runner import execute_triage_run
from repopilot_core.db import (
    Installation,
    Issue,
    Repo,
    TriageRun,
    WebhookDelivery,
    get_session_factory,
)
from repopilot_core.db.models import WebhookDeliveryStatus

logger = structlog.get_logger()


async def _get_or_create_installation(
    session: AsyncSession, github_installation_id: int, account_login: str
) -> Installation:
    installation = await session.scalar(
        select(Installation).where(Installation.github_installation_id == github_installation_id)
    )
    if installation is None:
        installation = Installation(
            github_installation_id=github_installation_id,
            account_login=account_login,
        )
        session.add(installation)
        await session.flush()
    return installation


async def _upsert_repo(
    session: AsyncSession, installation: Installation, repo_data: dict[str, Any]
) -> None:
    repo = await session.scalar(select(Repo).where(Repo.github_repo_id == repo_data["id"]))
    if repo is None:
        session.add(
            Repo(
                installation_id=installation.id,
                github_repo_id=repo_data["id"],
                full_name=repo_data["full_name"],
                default_branch=repo_data.get("default_branch", "main"),
            )
        )
    else:
        repo.full_name = repo_data["full_name"]
        repo.installation_id = installation.id


async def handle_installation(session: AsyncSession, payload: dict[str, Any]) -> None:
    action = payload["action"]
    inst_data = payload["installation"]
    if action in ("created", "unsuspend"):
        installation = await _get_or_create_installation(
            session, inst_data["id"], inst_data["account"]["login"]
        )
        for repo_data in payload.get("repositories", []):
            await _upsert_repo(session, installation, repo_data)
    elif action == "deleted":
        existing = await session.scalar(
            select(Installation).where(Installation.github_installation_id == inst_data["id"])
        )
        if existing is not None:
            for repo in await session.scalars(
                select(Repo).where(Repo.installation_id == existing.id)
            ):
                await session.delete(repo)
            await session.delete(existing)


async def handle_installation_repositories(session: AsyncSession, payload: dict[str, Any]) -> None:
    inst_data = payload["installation"]
    installation = await _get_or_create_installation(
        session, inst_data["id"], inst_data["account"]["login"]
    )
    for repo_data in payload.get("repositories_added", []):
        await _upsert_repo(session, installation, repo_data)
    for repo_data in payload.get("repositories_removed", []):
        repo = await session.scalar(select(Repo).where(Repo.github_repo_id == repo_data["id"]))
        if repo is not None:
            await session.delete(repo)


async def handle_issues(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Issue opened → persist issue, create a queued TriageRun, and run it.

    The triage run executes inline within this arq job (the job IS the
    background unit); a crash mid-run leaves status='running' which the
    arq retry resumes via the ledgered delivery.
    """
    if payload["action"] != "opened":
        return
    repo = await session.scalar(
        select(Repo).where(Repo.github_repo_id == payload["repository"]["id"])
    )
    if repo is None:
        logger.warning("issues.repo_not_connected", repo=payload["repository"]["full_name"])
        return

    issue_data = payload["issue"]
    issue = await session.scalar(
        select(Issue).where(
            Issue.repo_id == repo.id, Issue.github_issue_number == issue_data["number"]
        )
    )
    if issue is None:
        issue = Issue(
            repo_id=repo.id,
            github_issue_number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data.get("body") or "",
            author_login=(issue_data.get("user") or {}).get("login", ""),
            state=issue_data.get("state", "open"),
            github_labels=[label["name"] for label in issue_data.get("labels", [])],
        )
        session.add(issue)
        await session.flush()

    run = TriageRun(issue_id=issue.id)
    session.add(run)
    await session.commit()
    logger.info("issues.triage_queued", repo=repo.full_name, issue_number=issue.github_issue_number)

    installation = await session.get(Installation, repo.installation_id)
    deps = build_default_deps(
        installation_id=installation.github_installation_id if installation else None
    )
    await execute_triage_run(session, deps, run, issue, repo)


DISPATCH = {
    "installation": handle_installation,
    "installation_repositories": handle_installation_repositories,
    "issues": handle_issues,
}


async def process_webhook(ctx: dict[str, Any], delivery_id: int) -> None:
    """arq job: dispatch one ledgered webhook delivery."""
    async with get_session_factory()() as session:
        delivery = await session.get(WebhookDelivery, delivery_id)
        if delivery is None:
            logger.error("webhook.delivery_missing", delivery_id=delivery_id)
            return
        if delivery.status == WebhookDeliveryStatus.PROCESSED:
            return  # idempotent re-run

        handler = DISPATCH.get(delivery.event_type)
        if handler is None:
            delivery.status = WebhookDeliveryStatus.SKIPPED
            await session.commit()
            return

        try:
            await handler(session, delivery.payload)
            delivery.status = WebhookDeliveryStatus.PROCESSED
            await session.commit()
        except Exception as exc:
            await session.rollback()
            delivery = await session.get(WebhookDelivery, delivery_id)
            if delivery is not None:
                delivery.status = WebhookDeliveryStatus.FAILED
                delivery.error = repr(exc)
                await session.commit()
            logger.exception("webhook.processing_failed", delivery_id=delivery_id)
            raise  # let arq retry / dead-letter
