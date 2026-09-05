"""Base class for extension cogs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from discord.ext import commands

if TYPE_CHECKING:
    from botbase.app import Bot
    from botbase.config import Settings


class BaseCog(commands.Cog):
    """Convenience base for cogs.

    Provides a namespaced logger plus quick access to the bot's :attr:`settings`
    and :attr:`db`.
    """

    owner_only: bool = False
    """Set ``True`` on a subclass whose commands only the bot owner may run.
    ``/help`` uses this to hide the cog's commands from everyone else. Still
    enforce it yourself with an ``interaction_check`` / ``is_owner`` call."""

    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self.log = logging.getLogger(f"botbase.ext.{type(self).__module__.rpartition('.')[2]}")

    @property
    def settings(self) -> Settings:
        """The running bot's settings."""
        return self.bot.settings

    @property
    def db(self) -> Any:
        """The bot's ``async_sessionmaker``. Raises if no database is configured."""
        return self.bot.db
