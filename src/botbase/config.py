"""Typed, env-first configuration for a bot.

Everything is driven by environment variables (optionally via a ``.env`` file).
Variables are prefixed with ``BOT_`` and nested models use ``__`` as a separator,
e.g. ``BOT_TOKEN``, ``BOT_LOG_LEVEL``, ``BOT_INTENTS__MESSAGE_CONTENT=true``,
``BOT_DATABASE__URL=sqlite+aiosqlite:///bot.sqlite3``.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    import discord

LogFormat = Literal["text", "rich", "json"]


class IntentsSettings(BaseModel):
    """Toggles for the gateway intents the bot requests.

    The three privileged intents (``members``, ``message_content``,
    ``presences``) must also be enabled in the Discord Developer Portal.
    """

    default: bool = True
    """Start from :meth:`discord.Intents.default` (vs :meth:`discord.Intents.none`)."""

    members: bool = False
    message_content: bool = False
    presences: bool = False
    reactions: bool = True
    voice_states: bool = False
    typing: bool = False

    def to_intents(self) -> discord.Intents:
        """Build a :class:`discord.Intents` from these toggles."""
        import discord

        intents = discord.Intents.default() if self.default else discord.Intents.none()
        intents.members = self.members
        intents.message_content = self.message_content
        intents.presences = self.presences
        intents.reactions = self.reactions
        intents.voice_states = self.voice_states
        intents.typing = self.typing
        return intents


class DatabaseSettings(BaseModel):
    """Optional database configuration (requires the ``[db]`` extra)."""

    url: str = "sqlite+aiosqlite:///bot.sqlite3"
    """SQLAlchemy async URL. Use an ``+aiosqlite`` / ``+asyncpg`` driver."""

    echo: bool = False
    """Echo emitted SQL to the logger."""

    auto_create: bool = True
    """On startup, create any missing tables from the SQLModel metadata.

    Convenient for development. Set to ``False`` and use ``run_migrations`` once
    a bot has real schema history.
    """

    run_migrations: bool = False
    """On startup, run Alembic ``upgrade head``. Takes precedence over ``auto_create``."""


class Settings(BaseSettings):
    """Top-level bot settings, populated from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    token: SecretStr | None = None
    """Bot token. Required to actually connect; left optional so tooling
    (``botbase version``, ``botbase ext list``, tests) works without one."""

    application_id: int | None = None

    owner_ids: set[int] = Field(default_factory=set)
    """Users treated as bot owners by ``bot.is_owner`` (and the ``/dev`` commands).
    If empty, discord.py falls back to the application / team owner. Overrides it
    when set (e.g. ``BOT_OWNER_IDS=[209081432956600320]``)."""

    message_commands: bool = False
    """Enable classic ``prefix`` message commands. When ``False`` (default) the bot
    is slash-only and only responds to an @mention prefix, so the privileged
    message-content intent is not needed. When ``True``, also set
    ``BOT_INTENTS__MESSAGE_CONTENT=true``."""

    command_prefix: str = "!"
    """Message-command prefix, used only when ``message_commands`` is ``True``."""

    dev_guild_ids: list[int] = Field(default_factory=list)
    """If set, commands are copied to and synced per guild on startup (instant),
    instead of a slow global sync."""

    sync_commands_on_startup: bool = True

    extension_packages: list[str] = Field(default_factory=lambda: ["botbase.ext"])
    """Dotted packages to recursively discover extensions in."""

    disabled_extensions: set[str] = Field(default_factory=set)
    """Extension names to skip. Matches either the full dotted path or the bare
    leaf module name (e.g. ``botbase.ext.meta`` or ``meta``)."""

    strict_extension_loading: bool = False
    """Raise if any extension fails to load (vs. log and continue)."""

    log_level: str = "INFO"
    log_format: LogFormat = "text"

    presence_text: str | None = None
    """Optional "Playing ..." status text."""

    intents: IntentsSettings = Field(default_factory=IntentsSettings)
    database: DatabaseSettings | None = None

    def require_token(self) -> str:
        """Return the token string, or raise a clear error if it is missing."""
        if self.token is None:
            msg = "No bot token configured. Set BOT_TOKEN in the environment or a .env file (see .env.example)."
            raise RuntimeError(msg)
        return self.token.get_secret_value()


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()
