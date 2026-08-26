"""FastAPI dependency providers: db session, arq queue pool, BFF auth."""

import hmac
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from repopilot_core.db import get_session_factory
from repopilot_core.settings import get_settings


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


@dataclass
class Caller:
    """Who is making a dashboard request, per the BFF headers."""

    login: str | None  # GitHub login of the signed-in user, if any


def require_internal(
    x_internal_key: Annotated[str | None, Header()] = None,
    x_user_login: Annotated[str | None, Header()] = None,
) -> Caller:
    """Gate dashboard endpoints behind the BFF shared secret.

    When INTERNAL_API_KEY is configured, only requests carrying the matching
    `X-Internal-Key` are allowed — the browser can't reach the API directly,
    only the authenticated Next.js proxy can. When unset (pure local dev), the
    gate is open so the stack runs without auth wiring.
    """
    expected = get_settings().internal_api_key.get_secret_value()
    if expected and not hmac.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=401, detail="unauthorized")
    return Caller(login=x_user_login or None)


CallerCtx = Annotated[Caller, Depends(require_internal)]


async def get_queue(request: Request) -> ArqRedis:
    """arq pool created once per process and stored on app state."""
    pool: ArqRedis | None = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        pool = await create_pool(RedisSettings.from_dsn(str(get_settings().redis_url)))
        request.app.state.arq_pool = pool
    return pool


DbSession = Annotated[AsyncSession, Depends(get_db)]
Queue = Annotated[ArqRedis, Depends(get_queue)]
