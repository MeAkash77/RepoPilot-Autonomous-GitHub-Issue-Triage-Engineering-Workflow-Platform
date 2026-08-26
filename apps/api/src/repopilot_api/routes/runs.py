"""Triage run API: cursor-paginated list, detail, and SSE live stream.

The stream endpoint polls the run row and emits status/node-cost deltas
as SSE events — simple, stateless, and good enough for a triage run that
lives for seconds. A Redis pub/sub upgrade is mechanical if ever needed.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from repopilot_api.deps import CallerCtx, DbSession
from repopilot_api.scoping import scoped_repo_ids
from repopilot_core.db import Issue, Repo, TriageRun, get_session_factory
from repopilot_core.db.models import TriageRunStatus

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class RunSummary(BaseModel):
    id: int
    issue_number: int
    issue_title: str
    repo_full_name: str
    status: str
    cost_usd: float
    total_tokens: int
    latency_ms: int
    created_at: datetime


class RunDetail(RunSummary):
    classification: dict[str, Any] | None
    duplicates: list[Any]
    missing_info: dict[str, Any] | None
    related_files: list[Any]
    suggested_assignees: list[Any]
    model_routing: list[Any]
    graph_state: dict[str, Any] | None
    langfuse_trace_id: str | None
    error: str | None


class RunPage(BaseModel):
    items: list[RunSummary]
    next_cursor: int | None


def _summary(run: TriageRun, issue: Issue, repo: Repo) -> RunSummary:
    return RunSummary(
        id=run.id,
        issue_number=issue.github_issue_number,
        issue_title=issue.title,
        repo_full_name=repo.full_name,
        status=run.status.value,
        cost_usd=float(run.cost_usd),
        total_tokens=run.total_tokens,
        latency_ms=run.latency_ms,
        created_at=run.created_at,
    )


@router.get("", response_model=RunPage)
async def list_runs(
    caller: CallerCtx,
    db: DbSession,
    cursor: int | None = None,
    limit: int = 25,
    repo: str | None = None,
) -> RunPage:
    limit = min(limit, 100)
    ids = await scoped_repo_ids(db, caller)
    query = (
        select(TriageRun, Issue, Repo)
        .join(Issue, TriageRun.issue_id == Issue.id)
        .join(Repo, Issue.repo_id == Repo.id)
        .order_by(TriageRun.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        query = query.where(TriageRun.id < cursor)
    if repo:
        query = query.where(Repo.full_name == repo)
    if ids is not None:
        query = query.where(Repo.id.in_(ids))
    rows = (await db.execute(query)).all()
    items = [_summary(run, issue, repo_row) for run, issue, repo_row in rows[:limit]]
    next_cursor = items[-1].id if len(rows) > limit else None
    return RunPage(items=items, next_cursor=next_cursor)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, caller: CallerCtx, db: DbSession) -> RunDetail:
    run = await db.get(TriageRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    issue = await db.get(Issue, run.issue_id)
    assert issue is not None
    repo = await db.get(Repo, issue.repo_id)
    assert repo is not None

    # 404 (not 403) on out-of-scope access — avoids existence disclosure.
    ids = await scoped_repo_ids(db, caller)
    if ids is not None and repo.id not in ids:
        raise HTTPException(status_code=404, detail="run not found")

    return RunDetail(
        **_summary(run, issue, repo).model_dump(),
        classification=run.classification,
        duplicates=run.duplicates,
        missing_info=run.missing_info,
        related_files=run.related_files,
        suggested_assignees=run.suggested_assignees,
        model_routing=run.model_routing,
        graph_state=run.graph_state,
        langfuse_trace_id=run.langfuse_trace_id,
        error=run.error,
    )


TERMINAL = {TriageRunStatus.COMPLETED, TriageRunStatus.FAILED, TriageRunStatus.AWAITING_REVIEW}
POLL_INTERVAL_S = 0.5
STREAM_TIMEOUT_S = 120


@router.get("/{run_id}/stream")
async def stream_run(run_id: int, caller: CallerCtx, db: DbSession) -> StreamingResponse:
    # Ownership check before the stream opens.
    run_check = await db.get(TriageRun, run_id)
    if run_check is None:
        raise HTTPException(status_code=404, detail="run not found")
    issue_check = await db.get(Issue, run_check.issue_id)
    assert issue_check is not None
    repo_check = await db.get(Repo, issue_check.repo_id)
    assert repo_check is not None
    ids = await scoped_repo_ids(db, caller)
    if ids is not None and repo_check.id not in ids:
        raise HTTPException(status_code=404, detail="run not found")

    async def events() -> Any:
        factory = get_session_factory()
        seen_nodes = 0
        elapsed = 0.0
        while elapsed < STREAM_TIMEOUT_S:
            async with factory() as session:
                run = await session.get(TriageRun, run_id)
            if run is None:
                yield f"event: error\ndata: {json.dumps({'error': 'run not found'})}\n\n"
                return
            routing = run.model_routing or []
            for node in routing[seen_nodes:]:
                yield f"event: node\ndata: {json.dumps(node)}\n\n"
            seen_nodes = len(routing)
            yield (
                "event: status\n"
                f"data: {json.dumps({'status': run.status.value, 'cost_usd': float(run.cost_usd), 'total_tokens': run.total_tokens})}\n\n"
            )
            if run.status in TERMINAL:
                yield f"event: done\ndata: {json.dumps({'status': run.status.value})}\n\n"
                return
            await asyncio.sleep(POLL_INTERVAL_S)
            elapsed += POLL_INTERVAL_S

        yield f"event: error\ndata: {json.dumps({'error': 'stream timeout'})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
