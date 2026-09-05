"""Async engine and session helpers."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from botbase.config import DatabaseSettings


def build_engine(cfg: DatabaseSettings) -> AsyncEngine:
    """Create an :class:`~sqlalchemy.ext.asyncio.AsyncEngine` from settings."""
    return create_async_engine(cfg.url, echo=cfg.echo, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an ``async_sessionmaker`` bound to ``engine``."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create every table registered on :data:`SQLModel.metadata` that is missing."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@contextlib.asynccontextmanager
async def session(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """``async with session(sm) as s: ...`` — a scoped session."""
    async with sessionmaker() as active:
        yield active
