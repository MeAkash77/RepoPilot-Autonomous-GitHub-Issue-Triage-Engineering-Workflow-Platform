"""Liveness and readiness probes.

/healthz answers "is the process up" (always 200 while running).
/readyz performs live DB + Redis checks; returns 503 if a critical
dependency is unreachable so Fly.io auto-restarts the machine.
"""

import time
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from repopilot_api.deps import DbSession
from repopilot_core.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyzResponse(BaseModel):
    status: str
    checks: dict[str, Any]


@router.get("/healthz")
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", status_code=200)
async def readyz(db: DbSession, response: Response) -> ReadyzResponse:
    checks: dict[str, Any] = {}
    healthy = True

    # DB
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as exc:
        checks["postgres"] = {"status": "down", "error": str(exc)[:80]}
        healthy = False

    # Redis
    settings = get_settings()
    t0 = time.monotonic()
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(str(settings.redis_url), socket_connect_timeout=2)  # type: ignore[no-untyped-call]
        await client.ping()
        await client.aclose()
        checks["redis"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as exc:
        checks["redis"] = {"status": "down", "error": str(exc)[:80]}
        healthy = False

    if not healthy:
        response.status_code = 503

    return ReadyzResponse(status="ok" if healthy else "down", checks=checks)
