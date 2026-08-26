"""Aggregate analytics for the dashboard overview and analytics pages."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from repopilot_api.deps import CallerCtx, DbSession
from repopilot_api.scoping import scoped_repo_ids
from repopilot_core.db import Issue, ProposedAction, TriageRun
from repopilot_core.db.models import ActionStatus, TriageRunStatus

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class Overview(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    awaiting_review: int
    total_cost_usd: float
    mean_cost_usd: float
    mean_latency_ms: float
    pending_actions: int
    approval_rate_by_type: dict[str, Any]
    classification_distribution: dict[str, int]


def _scoped_run_ids_subquery(ids: frozenset[int] | None) -> Any:
    """Return a subquery of TriageRun.id scoped to the caller's repos, or None."""
    if ids is None:
        return None
    return (
        select(TriageRun.id)
        .join(Issue, TriageRun.issue_id == Issue.id)
        .where(Issue.repo_id.in_(ids))
        .scalar_subquery()
    )


@router.get("/overview", response_model=Overview)
async def overview(caller: CallerCtx, db: DbSession) -> Overview:
    ids = await scoped_repo_ids(db, caller)
    run_ids_sq = _scoped_run_ids_subquery(ids)

    # Total runs
    count_q = select(func.count(TriageRun.id))
    if run_ids_sq is not None:
        count_q = count_q.where(TriageRun.id.in_(run_ids_sq))
    total = (await db.execute(count_q)).scalar_one()

    # Status distribution
    status_q = select(TriageRun.status, func.count()).group_by(TriageRun.status)
    if run_ids_sq is not None:
        status_q = status_q.where(TriageRun.id.in_(run_ids_sq))
    status_rows = (await db.execute(status_q)).all()
    by_status: dict[TriageRunStatus, int] = {status: count for status, count in status_rows}

    # Cost + latency aggregates
    cost_q = select(
        func.coalesce(func.sum(TriageRun.cost_usd), 0.0),
        func.coalesce(func.avg(TriageRun.cost_usd), 0.0),
        func.coalesce(func.avg(TriageRun.latency_ms), 0.0),
    ).where(TriageRun.status != TriageRunStatus.FAILED)
    if run_ids_sq is not None:
        cost_q = cost_q.where(TriageRun.id.in_(run_ids_sq))
    cost_sum, cost_avg, latency_avg = (await db.execute(cost_q)).one()

    # Pending actions — scope via run_ids
    pending_q = select(func.count(ProposedAction.id)).where(
        ProposedAction.status == ActionStatus.PENDING
    )
    if run_ids_sq is not None:
        pending_q = pending_q.where(ProposedAction.triage_run_id.in_(run_ids_sq))
    pending = (await db.execute(pending_q)).scalar_one()

    # Approval rate per action type
    decisions_q = (
        select(ProposedAction.action_type, ProposedAction.status, func.count())
        .where(
            ProposedAction.status.in_(
                [ActionStatus.APPROVED, ActionStatus.REJECTED, ActionStatus.EXECUTED]
            )
        )
        .group_by(ProposedAction.action_type, ProposedAction.status)
    )
    if run_ids_sq is not None:
        decisions_q = decisions_q.where(ProposedAction.triage_run_id.in_(run_ids_sq))
    decisions = (await db.execute(decisions_q)).all()
    rate: dict[str, dict[str, int]] = {}
    for action_type, status, count in decisions:
        bucket = rate.setdefault(action_type.value, {"approved": 0, "rejected": 0})
        if status == ActionStatus.REJECTED:
            bucket["rejected"] += count
        else:
            bucket["approved"] += count
    approval_rate = {
        action_type: {
            **counts,
            "rate": counts["approved"] / (counts["approved"] + counts["rejected"])
            if counts["approved"] + counts["rejected"]
            else None,
        }
        for action_type, counts in rate.items()
    }

    # Classification distribution
    class_q = select(TriageRun.classification).where(TriageRun.classification.is_not(None))
    if run_ids_sq is not None:
        class_q = class_q.where(TriageRun.id.in_(run_ids_sq))
    classified = (await db.execute(class_q)).scalars()
    distribution: dict[str, int] = {}
    for classification in classified:
        label = (classification or {}).get("type", "unknown")
        distribution[label] = distribution.get(label, 0) + 1

    return Overview(
        total_runs=total,
        completed_runs=by_status.get(TriageRunStatus.COMPLETED, 0),
        failed_runs=by_status.get(TriageRunStatus.FAILED, 0),
        awaiting_review=by_status.get(TriageRunStatus.AWAITING_REVIEW, 0),
        total_cost_usd=float(cost_sum),
        mean_cost_usd=float(cost_avg),
        mean_latency_ms=float(latency_avg),
        pending_actions=pending,
        approval_rate_by_type=approval_rate,
        classification_distribution=distribution,
    )
