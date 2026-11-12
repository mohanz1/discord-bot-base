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


async def test_auto_create_runs_after_extensions_load(tmp_path: object) -> None:
    """A model imported only by an extension still gets its table (auto_create)."""
    from sqlmodel import select

    from botbase.app import Bot
    from botbase.config import Settings

    url = f"sqlite+aiosqlite:///{tmp_path}/auto.sqlite3"
    bot = Bot(
        Settings(
            _env_file=None,
            token=None,
            sync_commands_on_startup=False,
            extension_packages=["tests.fixtures.dbext"],
            database={"url": url},
        )
    )
    await bot.setup_hook()
    from tests.fixtures.dbext_models import FixtureNote

    async with bot.session() as s:
        s.add(FixtureNote(key="k", value="v"))
        await s.commit()
        assert (await s.exec(select(FixtureNote))).one().value == "v"
    await bot.close()


async def test_setup_hook_order(monkeypatch: object) -> None:
    from botbase.app import Bot
    from botbase.config import Settings

    bot = Bot(
        Settings(
            _env_file=None,
            token=None,
            sync_commands_on_startup=False,
            database={"url": "sqlite+aiosqlite:///:memory:"},
        )
    )
    loaded_at_create: list[set[str]] = []

    async def fake_create_tables() -> None:
        loaded_at_create.append(set(bot.extensions))

    monkeypatch.setattr(bot, "_create_tables", fake_create_tables)  # type: ignore[attr-defined]
    await bot.setup_hook()
    assert loaded_at_create
    assert "botbase.ext.meta" in loaded_at_create[0]
    await bot.close()


async def test_run_migrations_passes_bot_url_and_skips_create_all(monkeypatch: object) -> None:
    from botbase.app import Bot
    from botbase.config import Settings

    url = "sqlite+aiosqlite:///:memory:"
    bot = Bot(
        Settings(
            _env_file=None,
            token=None,
            sync_commands_on_startup=False,
            extension_packages=[],
            database={"url": url, "run_migrations": True},
        )
    )
    upgrades: list[tuple[str, str | None]] = []
    created: list[bool] = []

    def fake_upgrade(revision: str = "head", *, url: str | None = None) -> None:
        upgrades.append((revision, url))

    async def fake_create_tables() -> None:
        created.append(True)

    monkeypatch.setattr("botbase.database.migrations.upgrade", fake_upgrade)  # type: ignore[attr-defined]
    monkeypatch.setattr(bot, "_create_tables", fake_create_tables)  # type: ignore[attr-defined]
    await bot.setup_hook()
    assert upgrades == [("head", url)]
    assert created == []
    await bot.close()


def test_config_carries_explicit_url(tmp_path: object, monkeypatch: object) -> None:
    from pathlib import Path

    from botbase.database.migrations import URL_ATTRIBUTE, _config

    ini = Path(str(tmp_path)) / "alembic.ini"
    ini.write_text("[alembic]\nscript_location = alembic\n")
    assert URL_ATTRIBUTE not in _config(ini).attributes
    assert _config(ini, url="sqlite://").attributes[URL_ATTRIBUTE] == "sqlite://"


@pytest.mark.parametrize("explicit", [False, True])
def test_env_py_resolves_url_like_the_bot(tmp_path: object, explicit: bool) -> None:
    """Root alembic/env.py: explicit URL wins, else BOT_DATABASE__URL from .env."""
    import shutil
    from pathlib import Path

    from botbase.database import migrations

    repo = Path(__file__).resolve().parents[1]
    work = Path(str(tmp_path))  # also the cwd (see the _isolated_env fixture)
    shutil.copytree(repo / "alembic", work / "alembic")
    (work / "alembic" / "versions").mkdir(exist_ok=True)
    shutil.copy(repo / "alembic.ini", work / "alembic.ini")
    (work / ".env").write_text("BOT_DATABASE__URL=sqlite+aiosqlite:///from_dotenv.sqlite3\n")

    if explicit:
        migrations.upgrade("head", url="sqlite+aiosqlite:///explicit.sqlite3")
        expected, absent = "explicit.sqlite3", "from_dotenv.sqlite3"
    else:
        migrations.upgrade("head")
        expected, absent = "from_dotenv.sqlite3", "explicit.sqlite3"
    assert (work / expected).exists()
    assert not (work / absent).exists()
    assert not (work / "bot.sqlite3").exists()
