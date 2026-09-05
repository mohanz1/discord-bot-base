from __future__ import annotations

import pytest

from botbase.config import DatabaseSettings, IntentsSettings, Settings, get_settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.token is None
    assert s.command_prefix == "!"
    assert s.extension_packages == ["botbase.ext"]
    assert s.log_format == "text"
    assert s.database is None


def test_env_prefix_and_nesting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "abc.def.ghi")
    monkeypatch.setenv("BOT_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("BOT_DEV_GUILD_IDS", "[1, 2, 3]")
    monkeypatch.setenv("BOT_DISABLED_EXTENSIONS", '["meta"]')
    monkeypatch.setenv("BOT_INTENTS__MESSAGE_CONTENT", "true")
    monkeypatch.setenv("BOT_DATABASE__URL", "sqlite+aiosqlite:///x.db")

    s = Settings(_env_file=None)

    assert s.token is not None
    assert s.token.get_secret_value() == "abc.def.ghi"
    assert s.log_level == "DEBUG"
    assert s.dev_guild_ids == [1, 2, 3]
    assert s.disabled_extensions == {"meta"}
    assert s.intents.message_content is True
    assert s.database is not None
    assert s.database.url == "sqlite+aiosqlite:///x.db"


def test_owner_ids_and_message_commands_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_OWNER_IDS", "[111, 222]")
    monkeypatch.setenv("BOT_MESSAGE_COMMANDS", "true")
    s = Settings(_env_file=None)
    assert s.owner_ids == {111, 222}
    assert s.message_commands is True


def test_message_commands_defaults_off() -> None:
    s = Settings(_env_file=None)
    assert s.message_commands is False
    assert s.owner_ids == set()


def test_require_token_raises_without_one() -> None:
    with pytest.raises(RuntimeError, match="No bot token"):
        Settings(_env_file=None).require_token()


def test_require_token_returns_value() -> None:
    s = Settings(_env_file=None, token="t.o.k")
    assert s.require_token() == "t.o.k"


def test_intents_mapping() -> None:
    intents = IntentsSettings(members=True, message_content=True, presences=False).to_intents()
    assert intents.members is True
    assert intents.message_content is True
    assert intents.presences is False
    # default=True keeps the discord.py default baseline (guilds on).
    assert intents.guilds is True


def test_intents_from_none_baseline() -> None:
    intents = IntentsSettings(default=False, reactions=False).to_intents()
    assert intents.guilds is False


def test_database_settings_defaults() -> None:
    cfg = DatabaseSettings()
    assert cfg.url.startswith("sqlite+aiosqlite")
    assert cfg.auto_create is True
    assert cfg.run_migrations is False


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
