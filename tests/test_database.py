"""Database-layer tests. Require the ``[db]`` extra (``uv sync --extra db``)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db


async def test_engine_roundtrip_in_memory() -> None:
    from sqlmodel import Field, SQLModel, select

    from botbase.config import DatabaseSettings
    from botbase.database import build_engine, init_models, make_sessionmaker, session

    class _KV(SQLModel, table=True):
        __tablename__ = "kv_roundtrip_test"
        key: str = Field(primary_key=True)
        value: str

    engine = build_engine(DatabaseSettings(url="sqlite+aiosqlite:///:memory:"))
    await init_models(engine)
    sessionmaker = make_sessionmaker(engine)

    async with session(sessionmaker) as s:
        s.add(_KV(key="greeting", value="hi"))
        await s.commit()

    async with session(sessionmaker) as s:
        row = (await s.exec(select(_KV).where(_KV.key == "greeting"))).one()
        assert row.value == "hi"

    await engine.dispose()


async def test_bot_session_helper() -> None:
    from botbase.app import Bot
    from botbase.config import Settings

    settings = Settings(
        _env_file=None,
        token=None,
        sync_commands_on_startup=False,
        database={"url": "sqlite+aiosqlite:///:memory:"},
    )
    bot = Bot(settings)
    await bot.setup_hook()
    async with bot.session() as s:
        assert s is not None
    await bot.close()
