"""Dynamic discovery and loading of discord.py extensions (cogs).

Unlike a directory scan, discovery here goes through :mod:`importlib`/:mod:`pkgutil`
so it works the same whether the package is installed, editable, or zipped.

Every extension module must expose the standard discord.py entry point::

    async def setup(bot: commands.Bot) -> None:
        await bot.add_cog(MyCog(bot))
"""

from __future__ import annotations

import dataclasses
import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from botbase.errors import ExtensionLoadError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from discord.ext import commands

_log = logging.getLogger("botbase.extensions")


@dataclasses.dataclass(slots=True)
class LoadReport:
    """Outcome of a :func:`load_extensions` call."""

    loaded: list[str] = dataclasses.field(default_factory=list)
    skipped: list[str] = dataclasses.field(default_factory=list)
    failed: dict[str, BaseException] = dataclasses.field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True if nothing failed to load."""
        return not self.failed


def discover_extensions(package: str, *, recursive: bool = True) -> list[str]:
    """Return the dotted paths of every extension module inside ``package``.

    Modules (and sub-packages) whose leaf name starts with ``_`` are ignored, so
    helpers like ``_shared.py`` can live alongside real extensions.

    Parameters
    ----------
    package:
        Importable dotted package name, e.g. ``"mybot.ext"``.
    recursive:
        Also descend into sub-packages.
    """
    module = importlib.import_module(package)
    search_paths = getattr(module, "__path__", None)
    if search_paths is None:
        # ``package`` is a plain module, not a package: treat it as one extension.
        return [package]

    found: list[str] = []
    for info in pkgutil.iter_modules(search_paths, prefix=f"{package}."):
        leaf = info.name.rpartition(".")[2]
        if leaf.startswith("_"):
            continue
        if info.ispkg:
            if recursive:
                found.extend(discover_extensions(info.name, recursive=True))
            continue
        found.append(info.name)
    return sorted(found)


def _is_disabled(dotted: str, disabled: Iterable[str]) -> bool:
    leaf = dotted.rpartition(".")[2]
    disabled_set = set(disabled)
    return dotted in disabled_set or leaf in disabled_set


async def load_extensions(
    bot: commands.Bot,
    *,
    packages: Iterable[str],
    disabled: Iterable[str] = (),
    strict: bool = False,
) -> LoadReport:
    """Discover and load every extension in ``packages``.

    Parameters
    ----------
    bot:
        The bot to load extensions into.
    packages:
        Dotted packages to scan (see :func:`discover_extensions`).
    disabled:
        Names to skip; matches the full dotted path or the bare leaf name.
    strict:
        If any extension raises, re-raise as :class:`~botbase.errors.ExtensionLoadError`
        once loading finishes. Otherwise failures are only logged.
    """
    disabled = list(disabled)
    report = LoadReport()
    seen: set[str] = set()

    for package in packages:
        for dotted in discover_extensions(package):
            if dotted in seen:
                continue
            seen.add(dotted)

            if _is_disabled(dotted, disabled):
                _log.info("skipping disabled extension %s", dotted)
                report.skipped.append(dotted)
                continue

            try:
                await bot.load_extension(dotted)
            except Exception as exc:  # noqa: BLE001 - deliberately aggregate every failure
                _log.exception("failed to load extension %s", dotted)
                # discord.py wraps setup() errors in ExtensionFailed; keep the root cause.
                report.failed[dotted] = getattr(exc, "original", None) or exc
            else:
                _log.info("loaded extension %s", dotted)
                report.loaded.append(dotted)

    if report.failed and strict:
        raise ExtensionLoadError(report.failed)
    return report


async def reload_all(bot: commands.Bot) -> LoadReport:
    """Reload every currently loaded extension. Handy during development."""
    report = LoadReport()
    for name in list(bot.extensions):
        try:
            await bot.reload_extension(name)
        except Exception as exc:  # noqa: BLE001 - aggregate, report at the end
            _log.exception("failed to reload extension %s", name)
            report.failed[name] = exc
        else:
            report.loaded.append(name)
    return report
