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
    from collections.abc import Callable, Iterable

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


def discover_extensions(
    package: str,
    *,
    recursive: bool = True,
    skip: Callable[[str], bool] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[str]:
    """Return the dotted paths of every extension module inside ``package``.

    Modules (and sub-packages) whose leaf name starts with ``_`` are ignored, so
    helpers like ``_shared.py`` can live alongside real extensions.

    Parameters
    ----------
    package:
        Importable dotted package name, e.g. ``"mybot.ext"``.
    recursive:
        Also descend into sub-packages.
    skip:
        Called with each sub-package's dotted name before it is imported; return
        ``True`` to leave that sub-package (and everything under it) out.
    on_error:
        Called with ``(name, exception)`` when ``package`` or a sub-package fails
        to import; that branch is then left out. If ``None``, the error propagates.
    """
    try:
        module = importlib.import_module(package)
    except Exception as exc:
        if on_error is None:
            raise
        on_error(package, exc)
        return []
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
            if recursive and not (skip is not None and skip(info.name)):
                found.extend(discover_extensions(info.name, recursive=True, skip=skip, on_error=on_error))
            continue
        found.append(info.name)
    return sorted(found)


def _is_disabled(dotted: str, disabled: Iterable[str]) -> bool:
    leaf = dotted.rpartition(".")[2]
    disabled_set = set(disabled)
    return dotted in disabled_set or leaf in disabled_set


def _root_cause(exc: BaseException) -> BaseException:
    # discord.py wraps setup() errors in ExtensionFailed; keep the root cause.
    return getattr(exc, "original", None) or exc


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
        Names to skip; matches the full dotted path or the bare leaf name. A
        disabled sub-package is skipped whole, without being imported.
    strict:
        If any extension (or extension package) raises, re-raise as
        :class:`~botbase.errors.ExtensionLoadError` once loading finishes.
        Otherwise failures are only logged.
    """
    disabled = list(disabled)
    report = LoadReport()
    seen: set[str] = set()

    def skip_package(name: str) -> bool:
        if not _is_disabled(name, disabled):
            return False
        _log.info("skipping disabled extension package %s", name)
        report.skipped.append(name)
        return True

    def discovery_failed(name: str, exc: Exception) -> None:
        _log.error("failed to import extension package %s", name, exc_info=exc)
        report.failed[name] = exc

    for package in packages:
        for dotted in discover_extensions(package, skip=skip_package, on_error=discovery_failed):
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
                report.failed[dotted] = _root_cause(exc)
            else:
                _log.info("loaded extension %s", dotted)
                report.loaded.append(dotted)

    if report.failed and strict:
        group = BaseExceptionGroup("extension load failures", list(report.failed.values()))
        raise ExtensionLoadError(report.failed) from group
    return report


async def reload_all(bot: commands.Bot) -> LoadReport:
    """Reload every currently loaded extension. Handy during development."""
    report = LoadReport()
    for name in list(bot.extensions):
        try:
            await bot.reload_extension(name)
        except Exception as exc:  # noqa: BLE001 - aggregate, report at the end
            _log.exception("failed to reload extension %s", name)
            report.failed[name] = _root_cause(exc)
        else:
            report.loaded.append(name)
    return report
