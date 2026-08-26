"""Alembic environment: async engine, autogenerate against Base.metadata."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from repopilot_core.db.base import Base
from repopilot_core.db.models import *  # noqa: F403 -- register all models on Base
from repopilot_core.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", str(get_settings().database_url))

target_metadata = Base.metadata

# Postgres-only objects managed by raw DDL in migrations, invisible to the ORM.
_MIGRATION_ONLY = {("column", "tsv"), ("index", "ix_chunks_tsv"), ("index", "ix_chunks_embedding")}


def include_object(obj: object, name: str | None, type_: str, *args: object) -> bool:
    return (type_, name) not in _MIGRATION_ONLY


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
