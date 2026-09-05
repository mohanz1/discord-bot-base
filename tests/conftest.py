from __future__ import annotations

import os
import sys

import discord
import pytest

import botbase.ext.admin as _admin_mod
import botbase.ext.errors as _errors_mod
import botbase.ext.meta as _meta_mod
from botbase.app import Bot
from botbase.config import Settings, get_settings

_CANONICAL_EXT_MODULES = {m.__name__: m for m in (_admin_mod, _errors_mod, _meta_mod)}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Never read the developer's real .env or BOT_* variables during tests."""
    for key in list(os.environ):
        if key.startswith("BOT_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _stable_ext_modules() -> None:
    """discord.py's ``load_extension`` swaps ``sys.modules`` entries for a fresh
    module object; restore the canonical ones so class identity is stable across
    tests (otherwise ``isinstance`` checks against reloaded classes fail).
    """
    yield
    for name, module in _CANONICAL_EXT_MODULES.items():
        sys.modules[name] = module


@pytest.fixture
def settings() -> Settings:
    """A minimal, token-less Settings that never touches a real .env file."""
    return Settings(
        _env_file=None,
        token=None,
        sync_commands_on_startup=False,
        extension_packages=["botbase.ext"],
    )


@pytest.fixture
async def bot(settings: Settings) -> Bot:
    """An unconnected Bot instance. Safe for extension/cog tests."""
    instance = Bot(settings)
    yield instance
    if not instance.is_closed():
        await instance.close()


class FakeResponse:
    """Stand-in for ``interaction.response``."""

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.modals: list[object] = []
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: str | None = None, **kwargs: object) -> None:
        self._done = True
        self.messages.append({"content": content, **kwargs})

    async def defer(self, **kwargs: object) -> None:
        self._done = True
        self.messages.append({"deferred": True, **kwargs})

    async def send_modal(self, modal: object) -> None:
        self._done = True
        self.modals.append(modal)

    async def edit_message(self, **kwargs: object) -> None:
        self._done = True
        self.messages.append({"edit_message": True, **kwargs})


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, content: str | None = None, **kwargs: object) -> None:
        self.messages.append({"content": content, **kwargs})


class FakeMessage:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit(self, **kwargs: object) -> None:
        self.edits.append(kwargs)


class FakeUser:
    def __init__(self, user_id: int = 1) -> None:
        self.id = user_id
        self.mention = f"<@{user_id}>"
        self.display_name = "tester"


class FakeInteraction:
    """Enough of ``discord.Interaction`` for the built-in extensions."""

    def __init__(
        self,
        *,
        command_name: str | None = "test",
        user_id: int = 1,
        client: object | None = None,
    ) -> None:
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.edited: list[dict[str, object]] = []
        self.created_at = discord.utils.utcnow()
        self.user = FakeUser(user_id)
        self.client = client
        self.channel: object | None = None
        self.guild: object | None = None
        self._original = FakeMessage()
        self.command = discord.Object(id=1) if command_name is None else _NamedCommand(command_name)

    async def edit_original_response(self, **kwargs: object) -> None:
        self.edited.append(kwargs)

    async def original_response(self) -> FakeMessage:
        return self._original


class _NamedCommand:
    def __init__(self, name: str) -> None:
        self.name = name


@pytest.fixture
def interaction() -> FakeInteraction:
    return FakeInteraction()
