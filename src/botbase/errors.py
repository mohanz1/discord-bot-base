"""Exception hierarchy for the bot base."""

from __future__ import annotations


class BotBaseError(Exception):
    """Base class for every error raised by ``botbase`` itself."""


class MissingDependencyError(BotBaseError):
    """A feature was used whose optional dependency is not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        self.feature = feature
        self.extra = extra
        super().__init__(
            f"{feature} requires the optional '{extra}' dependencies. "
            f"Install them with: pip install 'discord-bot-base[{extra}]'"
        )


class ExtensionLoadError(BotBaseError):
    """One or more extensions failed to load during startup.

    The individual failures are attached as ``__cause__`` on the wrapped
    :class:`ExceptionGroup` and listed on :attr:`failures`.
    """

    def __init__(self, failures: dict[str, BaseException]) -> None:
        self.failures = failures
        names = ", ".join(sorted(failures))
        super().__init__(f"{len(failures)} extension(s) failed to load: {names}")
