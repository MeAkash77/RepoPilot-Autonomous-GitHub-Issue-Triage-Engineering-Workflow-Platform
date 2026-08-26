"""HITL approval queue API.

Approve executes immediately (the human IS the gate); reject only
records; edit replaces the payload then executes. Every decision becomes
a feedback_events row — the seed corpus for future evals.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from repopilot_api.deps import CallerCtx, DbSession
from repopilot_api.scoping import scoped_repo_ids
from repopilot_core.db import FeedbackEvent, Installation, Issue, ProposedAction, Repo, TriageRun
from repopilot_core.db.models import ActionStatus, FeedbackVerdict
from repopilot_core.settings import get_settings
from repopilot_github.client import GitHubAppClient
from repopilot_github.executor import execute_and_record

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


class ActionOut(BaseModel):
    id: int
    triage_run_id: int
    issue_number: int
    repo_full_name: str
    action_type: str
    payload: dict[str, Any]
    risk: str
    status: str
    created_at: datetime


class ReviewRequest(BaseModel):
    reviewer: str = "dashboard"
    edited_payload: dict[str, Any] | None = None


class ReviewResponse(BaseModel):
    id: int
    status: str
    github_result: dict[str, Any] | None


async def _load_action_context(
    db: DbSession, action_id: int
) -> tuple[ProposedAction, Issue, Repo, Installation]:
    action = await db.get(ProposedAction, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="action not found")
    run = await db.get(TriageRun, action.triage_run_id)
    assert run is not None
    issue = await db.get(Issue, run.issue_id)
    assert issue is not None
    repo = await db.get(Repo, issue.repo_id)
    assert repo is not None
    installation = await db.get(Installation, repo.installation_id)
    assert installation is not None
    return action, issue, repo, installation


@router.get("/pending", response_model=list[ActionOut])
async def list_pending(
    caller: CallerCtx, db: DbSession, repo: str | None = None
) -> list[ActionOut]:
    ids = await scoped_repo_ids(db, caller)
    query = (
        select(ProposedAction, Issue, Repo)
        .join(TriageRun, ProposedAction.triage_run_id == TriageRun.id)
        .join(Issue, TriageRun.issue_id == Issue.id)
        .join(Repo, Issue.repo_id == Repo.id)
        .where(ProposedAction.status == ActionStatus.PENDING)
        .order_by(ProposedAction.created_at.desc())
        .limit(200)
    )
    if repo:
        query = query.where(Repo.full_name == repo)
    if ids is not None:
        query = query.where(Repo.id.in_(ids))
    rows = (await db.execute(query)).all()
    return [
        ActionOut(
            id=action.id,
            triage_run_id=action.triage_run_id,
            issue_number=issue.github_issue_number,
            repo_full_name=repo_row.full_name,
            action_type=action.action_type.value,
            payload=action.payload,
            risk=action.risk.value,
            status=action.status.value,
            created_at=action.created_at,
        )
        for action, issue, repo_row in rows
    ]


def _require_pending(action: ProposedAction) -> None:
    if action.status != ActionStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"action is {action.status.value}, not pending")


@router.post("/{action_id}/approve", response_model=ReviewResponse)
async def approve_action(
    action_id: int, body: ReviewRequest, caller: CallerCtx, db: DbSession
) -> ReviewResponse:
    action, issue, repo, installation = await _load_action_context(db, action_id)
    ids = await scoped_repo_ids(db, caller)
    if ids is not None and repo.id not in ids:
        raise HTTPException(status_code=404, detail="action not found")
    _require_pending(action)

    verdict = FeedbackVerdict.APPROVED
    if body.edited_payload is not None and body.edited_payload != action.payload:
        action.payload = body.edited_payload
        verdict = FeedbackVerdict.EDITED

    action.status = ActionStatus.APPROVED
    action.reviewed_by = body.reviewer
    action.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        FeedbackEvent(
            proposed_action_id=action.id,
            verdict=verdict,
            edited_payload=body.edited_payload if verdict == FeedbackVerdict.EDITED else None,
            reviewer=body.reviewer,
        )
    )

    if get_settings().github_app_id:
        github = GitHubAppClient()
        try:
            await execute_and_record(
                github,
                installation.github_installation_id,
                repo.full_name,
                issue.github_issue_number,
                action,
                auto=False,
            )
        finally:
            await github.aclose()
    await db.commit()
    return ReviewResponse(
        id=action.id, status=action.status.value, github_result=action.github_result
    )


@router.post("/{action_id}/reject", response_model=ReviewResponse)
async def reject_action(
    action_id: int, body: ReviewRequest, caller: CallerCtx, db: DbSession
) -> ReviewResponse:
    action, _issue, repo, _ = await _load_action_context(db, action_id)
    ids = await scoped_repo_ids(db, caller)
    if ids is not None and repo.id not in ids:
        raise HTTPException(status_code=404, detail="action not found")
    _require_pending(action)
    action.status = ActionStatus.REJECTED
    action.reviewed_by = body.reviewer
    action.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        FeedbackEvent(
            proposed_action_id=action.id,
            verdict=FeedbackVerdict.REJECTED,
            reviewer=body.reviewer,
        )
    )
    await db.commit()
    return ReviewResponse(id=action.id, status=action.status.value, github_result=None)
