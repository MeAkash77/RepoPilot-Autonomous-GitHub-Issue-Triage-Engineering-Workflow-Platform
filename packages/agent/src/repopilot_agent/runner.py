"""Triage run orchestration: DB row lifecycle around graph execution.

queued → running → awaiting_review (success, actions pending) /
completed (no actions) / failed (exception, error captured).
"""

import time
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from repopilot_agent.graph import run_triage
from repopilot_agent.nodes import NodeDeps
from repopilot_agent.state import TriageState
from repopilot_agent.tracing import RunTracer
from repopilot_core.db import Issue, ProposedAction, Repo, TriageRun
from repopilot_core.db.models import (
    ActionRisk,
    ActionType,
    AutonomyLevel,
    TriageRunStatus,
)
from repopilot_github.executor import decide_gate, execute_and_record

logger = structlog.get_logger()


async def execute_triage_run(
    session: AsyncSession,
    deps: NodeDeps,
    run: TriageRun,
    issue: Issue,
    repo: Repo,
) -> TriageState:
    tracer = RunTracer()
    run.status = TriageRunStatus.RUNNING
    run.langfuse_trace_id = tracer.trace_id
    await session.commit()

    initial = TriageState(
        repo_id=repo.id,
        repo_full_name=repo.full_name,
        issue_number=issue.github_issue_number,
        issue_title=issue.title,
        issue_body=issue.body,
        issue_author=issue.author_login,
        autonomy_level=repo.autonomy_level.value,
    )
    started = time.monotonic()
    try:
        final = await run_triage(deps, initial, thread_id=f"triage-{run.id}")
    except Exception as exc:
        run.status = TriageRunStatus.FAILED
        run.error = repr(exc)
        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        tracer.record_run(initial, int((time.monotonic() - started) * 1000), error=repr(exc))
        logger.exception("triage.failed", run_id=run.id)
        raise

    latency_ms = int((time.monotonic() - started) * 1000)
    run.graph_state = final.model_dump(mode="json")
    run.classification = (
        final.classification.model_dump(mode="json") if final.classification else None
    )
    run.duplicates = [d.model_dump(mode="json") for d in final.duplicates]
    run.missing_info = final.missing_info.model_dump(mode="json") if final.missing_info else None
    run.related_files = list(final.related_files)
    run.suggested_assignees = [s.model_dump(mode="json") for s in final.assignee_suggestions]
    run.total_tokens = final.total_tokens
    run.cost_usd = final.total_cost_usd
    run.latency_ms = latency_ms
    run.model_routing = [c.model_dump(mode="json") for c in final.node_costs]
    # Persist guardrail-approved actions; auto-execute what the repo's
    # autonomy level (possibly downgraded by the injection screen) allows.
    effective_autonomy = AutonomyLevel(final.autonomy_level)
    pending = 0
    for draft in final.proposed_actions:
        action = ProposedAction(
            triage_run_id=run.id,
            action_type=ActionType(draft.action_type),
            payload=draft.payload,
            risk=ActionRisk(draft.risk),
        )
        session.add(action)
        await session.flush()
        if (
            decide_gate(effective_autonomy, action.risk)
            and deps.github is not None
            and deps.installation_id is not None
        ):
            await execute_and_record(
                deps.github,
                deps.installation_id,
                repo.full_name,
                issue.github_issue_number,
                action,
                auto=True,
            )
        else:
            pending += 1

    run.status = TriageRunStatus.AWAITING_REVIEW if pending else TriageRunStatus.COMPLETED
    run.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()

    tracer.record_run(final, latency_ms)
    logger.info(
        "triage.done",
        run_id=run.id,
        status=run.status.value,
        cost_usd=round(final.total_cost_usd, 6),
        tokens=final.total_tokens,
        latency_ms=latency_ms,
        actions=len(final.proposed_actions),
    )
    return final
