"""Alembic environment — async engine, SQLModel metadata, SQLite batch mode."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from botbase.config import DatabaseSettings, Settings

# Import your bot's models here so their tables register on SQLModel.metadata.
from botbase.database import SQLModel
from botbase.database.migrations import URL_ATTRIBUTE

config = context.config


def _resolve_url() -> str:
    # 1. The URL the running bot handed over (BOT_DATABASE__RUN_MIGRATIONS).
    # 2. The bot's own settings: BOT_DATABASE__URL from the environment or .env.
    #    Use your bot's Settings subclass here if it changes the defaults.
    explicit = config.attributes.get(URL_ATTRIBUTE)
    if explicit:
        return explicit
    return (Settings().database or DatabaseSettings()).url


_url = _resolve_url()
config.set_main_option("sqlalchemy.url", _url)

target_metadata = SQLModel.metadata


def _run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # required for SQLite ALTER support
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
