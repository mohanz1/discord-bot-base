"""discord-bot-base: a modern, uv-first foundation for Discord bots.

The public surface is intentionally small. Downstream bots typically only need
:class:`~botbase.app.Bot`, :func:`~botbase.app.run`, :class:`~botbase.cog.BaseCog`
and :class:`~botbase.config.Settings`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from botbase.app import Bot, run
from botbase.cog import BaseCog
from botbase.config import DatabaseSettings, IntentsSettings, Settings, get_settings
from botbase.errors import (
    BotBaseError,
    ExtensionLoadError,
    MissingDependencyError,
)
from botbase.extensions import LoadReport, discover_extensions, load_extensions, reload_all

try:
    __version__ = version("discord-bot-base")
except PackageNotFoundError:  # pragma: no cover - only when running from a raw checkout
    __version__ = "0.0.0+unknown"

__all__ = [
    "BaseCog",
    "Bot",
    "BotBaseError",
    "DatabaseSettings",
    "ExtensionLoadError",
    "IntentsSettings",
    "LoadReport",
    "MissingDependencyError",
    "Settings",
    "__version__",
    "discover_extensions",
    "get_settings",
    "load_extensions",
    "reload_all",
    "run",
]
