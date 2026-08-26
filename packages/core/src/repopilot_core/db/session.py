"""Async engine and session factory.

Created lazily per process; api and worker each own one engine. No global
session — callers manage transaction scope explicitly.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from repopilot_core.settings import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(
        str(get_settings().database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
