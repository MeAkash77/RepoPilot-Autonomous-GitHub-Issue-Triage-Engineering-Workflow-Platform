"""Observability endpoints: metrics, health, trace waterfall, dead-letter queue."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text

from repopilot_api.deps import CallerCtx, DbSession
from repopilot_api.scoping import scoped_repo_ids
from repopilot_core.db import Issue, TriageRun
from repopilot_core.db.models import TriageRunStatus, WebhookDelivery, WebhookDeliveryStatus
from repopilot_core.settings import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

_WINDOWS = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}


# ── models ────────────────────────────────────────────────────────────────────


class LatencyPercentiles(BaseModel):
    p50: float
    p95: float
    p99: float


class MetricsWindow(BaseModel):
    window: str
    total_runs: int
    completed: int
    failed: int
    awaiting_review: int
    success_rate: float
    mean_cost_usd: float
    total_cost_usd: float
    mean_latency_ms: float
    latency_percentiles: LatencyPercentiles
    total_tokens: int


class ComponentHealth(BaseModel):
    name: str
    status: str  # "ok" | "degraded" | "down"
    latency_ms: float | None = None
    detail: str | None = None


class HealthStatus(BaseModel):
    status: str  # "ok" | "degraded" | "down"
    components: list[ComponentHealth]
    checked_at: datetime


class TraceSpan(BaseModel):
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


class RunTrace(BaseModel):
    run_id: int
    total_latency_ms: int
    total_cost_usd: float
    spans: list[TraceSpan]


class DeadLetterItem(BaseModel):
    id: int
    github_delivery_id: str
    event_type: str
    error: str | None
    received_at: datetime


class DeadLetterResponse(BaseModel):
    count: int
    items: list[DeadLetterItem]


# ── helpers ───────────────────────────────────────────────────────────────────


def _scoped_run_ids_subq(ids: frozenset[int] | None) -> Any:
    if ids is None:
        return None
    return (
        select(TriageRun.id)
        .join(Issue, TriageRun.issue_id == Issue.id)
        .where(Issue.repo_id.in_(ids))
        .scalar_subquery()
    )


# ── routes ────────────────────────────────────────────────────────────────────


@router.get("/metrics", response_model=MetricsWindow)
async def metrics(
    caller: CallerCtx,
    db: DbSession,
    window: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
) -> MetricsWindow:
    hours = _WINDOWS[window]
    since = (datetime.now(UTC) - timedelta(hours=hours)).replace(tzinfo=None)
    ids = await scoped_repo_ids(db, caller)
    run_ids_sq = _scoped_run_ids_subq(ids)

    base = select(TriageRun).where(TriageRun.created_at >= since)
    if run_ids_sq is not None:
        base = base.where(TriageRun.id.in_(run_ids_sq))

    # Counts by status
    status_q = (
        select(TriageRun.status, func.count())
        .where(TriageRun.created_at >= since)
        .group_by(TriageRun.status)
    )
    if run_ids_sq is not None:
        status_q = status_q.where(TriageRun.id.in_(run_ids_sq))
    status_rows = (await db.execute(status_q)).all()
    by_status: dict[TriageRunStatus, int] = {s: c for s, c in status_rows}

    total = sum(by_status.values())
    completed = by_status.get(TriageRunStatus.COMPLETED, 0)
    failed = by_status.get(TriageRunStatus.FAILED, 0)
    awaiting = by_status.get(TriageRunStatus.AWAITING_REVIEW, 0)

    # Cost + mean latency
    agg_q = select(
        func.coalesce(func.sum(TriageRun.cost_usd), 0.0),
        func.coalesce(func.avg(TriageRun.cost_usd), 0.0),
        func.coalesce(func.avg(TriageRun.latency_ms), 0.0),
        func.coalesce(func.sum(TriageRun.total_tokens), 0),
    ).where(
        TriageRun.created_at >= since,
        TriageRun.status != TriageRunStatus.FAILED,
    )
    if run_ids_sq is not None:
        agg_q = agg_q.where(TriageRun.id.in_(run_ids_sq))
    cost_total, cost_mean, latency_mean, tokens = (await db.execute(agg_q)).one()

    # Latency percentiles via Postgres percentile_cont
    pct_q = select(
        func.percentile_cont(0.50).within_group(TriageRun.latency_ms),
        func.percentile_cont(0.95).within_group(TriageRun.latency_ms),
        func.percentile_cont(0.99).within_group(TriageRun.latency_ms),
    ).where(
        TriageRun.created_at >= since,
        TriageRun.status == TriageRunStatus.COMPLETED,
    )
    if run_ids_sq is not None:
        pct_q = pct_q.where(TriageRun.id.in_(run_ids_sq))
    p50, p95, p99 = (await db.execute(pct_q)).one()

    return MetricsWindow(
        window=window,
        total_runs=total,
        completed=completed,
        failed=failed,
        awaiting_review=awaiting,
        success_rate=round(completed / total, 4) if total else 0.0,
        mean_cost_usd=round(float(cost_mean), 6),
        total_cost_usd=round(float(cost_total), 6),
        mean_latency_ms=round(float(latency_mean), 1),
        latency_percentiles=LatencyPercentiles(
            p50=float(p50 or 0),
            p95=float(p95 or 0),
            p99=float(p99 or 0),
        ),
        total_tokens=int(tokens or 0),
    )


@router.get("/health", response_model=HealthStatus)
async def health(db: DbSession) -> HealthStatus:
    components: list[ComponentHealth] = []
    worst = "ok"

    # DB check
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        db_ms = (time.monotonic() - t0) * 1000
        components.append(ComponentHealth(name="postgres", status="ok", latency_ms=round(db_ms, 1)))
    except Exception as exc:
        components.append(ComponentHealth(name="postgres", status="down", detail=str(exc)[:120]))
        worst = "down"

    # Redis check
    settings = get_settings()
    t0 = time.monotonic()
    try:
        import redis.asyncio as aioredis

        redis_url = str(settings.redis_url)
        client = aioredis.from_url(redis_url, socket_connect_timeout=2)  # type: ignore[no-untyped-call]
        await client.ping()
        await client.aclose()
        redis_ms = (time.monotonic() - t0) * 1000
        components.append(ComponentHealth(name="redis", status="ok", latency_ms=round(redis_ms, 1)))
    except Exception as exc:
        components.append(ComponentHealth(name="redis", status="down", detail=str(exc)[:120]))
        if worst != "down":
            worst = "down"

    # LLM provider key presence (fast, no network call)
    groq_ok = bool(settings.groq_api_key.get_secret_value())
    gemini_ok = bool(settings.google_api_key.get_secret_value())
    llm_status = "ok" if (groq_ok or gemini_ok) else "down"
    components.append(
        ComponentHealth(
            name="llm",
            status=llm_status,
            detail=f"groq={'ok' if groq_ok else 'missing'} gemini={'ok' if gemini_ok else 'missing'}",
        )
    )
    if llm_status == "down" and worst == "ok":
        worst = "degraded"

    return HealthStatus(
        status=worst,
        components=components,
        checked_at=datetime.now(UTC),
    )


@router.get("/traces/{run_id}", response_model=RunTrace)
async def trace_waterfall(run_id: int, caller: CallerCtx, db: DbSession) -> RunTrace:
    run = await db.get(TriageRun, run_id)
    if run is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="run not found")

    spans = [
        TraceSpan(
            node=n.get("node", ""),
            model=n.get("model", ""),
            input_tokens=n.get("input_tokens", 0),
            output_tokens=n.get("output_tokens", 0),
            cost_usd=n.get("cost_usd", 0.0),
            latency_ms=n.get("latency_ms", 0),
        )
        for n in (run.model_routing or [])
    ]

    return RunTrace(
        run_id=run_id,
        total_latency_ms=run.latency_ms,
        total_cost_usd=run.cost_usd,
        spans=spans,
    )


@router.get("/dead-letter", response_model=DeadLetterResponse)
async def dead_letter(
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
) -> DeadLetterResponse:
    since = (datetime.now(UTC) - timedelta(hours=24)).replace(tzinfo=None)
    count_q = select(func.count(WebhookDelivery.id)).where(
        WebhookDelivery.status == WebhookDeliveryStatus.FAILED,
        WebhookDelivery.received_at >= since,
    )
    total = (await db.execute(count_q)).scalar_one()

    rows_q = (
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status == WebhookDeliveryStatus.FAILED,
            WebhookDelivery.received_at >= since,
        )
        .order_by(WebhookDelivery.received_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(rows_q)).scalars().all()

    return DeadLetterResponse(
        count=total,
        items=[
            DeadLetterItem(
                id=r.id,
                github_delivery_id=r.github_delivery_id,
                event_type=r.event_type,
                error=r.error,
                received_at=r.received_at,
            )
            for r in rows
        ],
    )
