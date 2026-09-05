from __future__ import annotations

import datetime as dt

import pytest
from discord.ext import commands

from botbase.app import Bot, _install_fast_event_loop, run
from botbase.config import Settings
from botbase.tree import BotTree


def test_bot_wires_settings(settings: Settings) -> None:
    bot = Bot(settings)
    assert bot.settings is settings
    assert isinstance(bot.tree, BotTree)
    assert bot.help_command is None


def test_bot_applies_intents() -> None:
    s = Settings(_env_file=None, token=None)
    s.intents.members = True
    bot = Bot(s)
    assert bot.intents.members is True


def test_owner_ids_passed_through() -> None:
    bot = Bot(Settings(_env_file=None, token=None, owner_ids={7, 8}))
    assert bot.owner_ids == {7, 8}


def test_slash_only_prefix_is_mention_only() -> None:
    bot = Bot(Settings(_env_file=None, token=None, message_commands=False))
    assert bot.command_prefix is commands.when_mentioned


def test_message_commands_enable_text_prefix() -> None:
    bot = Bot(Settings(_env_file=None, token=None, message_commands=True))
    assert bot.command_prefix is not commands.when_mentioned


def test_uptime_zero_before_start(bot: Bot) -> None:
    assert bot.uptime == dt.timedelta(0)


def test_db_property_raises_when_unconfigured(bot: Bot) -> None:
    with pytest.raises(RuntimeError, match="Database not configured"):
        _ = bot.db


async def test_setup_hook_loads_builtin_extensions(settings: Settings) -> None:
    bot = Bot(settings)
    await bot.setup_hook()
    assert "botbase.ext.meta" in bot.extensions
    assert "botbase.ext.errors" in bot.extensions
    assert bot.uptime > dt.timedelta(0)
    await bot.close()


def test_run_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("botbase.app._install_fast_event_loop", lambda: None)
    with pytest.raises(RuntimeError, match="No bot token"):
        run(Settings(_env_file=None, token=None))


async def test_sync_commands_noop_when_disabled(settings: Settings) -> None:
    bot = Bot(settings)  # settings fixture has sync_commands_on_startup=False
    await bot._sync_commands()  # must not touch the network / raise
    await bot.close()


async def test_sync_commands_global(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = Bot(Settings(_env_file=None, token=None, sync_commands_on_startup=True))
    seen: list[object] = []

    async def fake_sync(*, guild: object = None) -> list[object]:
        seen.append(guild)
        return []

    monkeypatch.setattr(bot.tree, "sync", fake_sync)
    await bot._sync_commands()
    assert seen == [None]
    await bot.close()


async def test_sync_commands_per_dev_guild(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = Bot(Settings(_env_file=None, token=None, sync_commands_on_startup=True, dev_guild_ids=[10, 20]))
    synced: list[int] = []

    async def fake_sync(*, guild: object) -> list[object]:
        synced.append(guild.id)  # type: ignore[attr-defined]
        return []

    monkeypatch.setattr(bot.tree, "sync", fake_sync)
    monkeypatch.setattr(bot.tree, "copy_global_to", lambda *, guild: None)
    await bot._sync_commands()
    assert synced == [10, 20]
    await bot.close()


async def test_on_ready_logs_and_sets_presence(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.conftest import FakeUser

    bot = Bot(Settings(_env_file=None, token=None, presence_text="cogs"))
    monkeypatch.setattr(bot._connection, "user", FakeUser(42), raising=False)
    presence: list[dict[str, object]] = []

    async def fake_presence(**kwargs: object) -> None:
        presence.append(kwargs)

    monkeypatch.setattr(bot, "change_presence", fake_presence)
    with caplog.at_level("INFO", logger="botbase"):
        await bot.on_ready()
    assert any("ready as" in r.message for r in caplog.records)
    assert "activity" in presence[0]
    await bot.close()


def test_install_fast_event_loop_is_safe() -> None:
    _install_fast_event_loop()  # must not raise regardless of what's installed
