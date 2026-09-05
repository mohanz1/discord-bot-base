"""The :class:`Bot` subclass and the :func:`run` entry point."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import signal
import time
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from botbase.config import Settings, get_settings
from botbase.extensions import LoadReport, load_extensions
from botbase.logs import configure_logging
from botbase.tree import BotTree

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from botbase.config import DatabaseSettings

_log = logging.getLogger("botbase")


class Bot(commands.Bot):
    """A :class:`discord.ext.commands.Bot` wired up from :class:`~botbase.config.Settings`.

    Adds: intents/prefix/tree from config, dynamic extension loading in
    :meth:`setup_hook`, an optional async database engine, command syncing, and
    an :attr:`uptime` helper.
    """

    if TYPE_CHECKING:
        # discord.py types ``tree`` as ``CommandTree``; we always use ``BotTree``.
        tree: BotTree

    def __init__(self, settings: Settings | None = None, *, tree_cls: type[BotTree] = BotTree) -> None:
        self.settings: Settings = settings or get_settings()
        self.log = _log
        self.load_report: LoadReport = LoadReport()
        self._engine: Any | None = None
        self._sessionmaker: Any | None = None
        self._started_monotonic: float | None = None

        optional: dict[str, Any] = {}
        if self.settings.application_id is not None:
            optional["application_id"] = self.settings.application_id
        if self.settings.owner_ids:
            optional["owner_ids"] = set(self.settings.owner_ids)

        if self.settings.message_commands:
            prefix = commands.when_mentioned_or(self.settings.command_prefix)
        else:
            # @mention-only prefix works without the privileged message-content intent.
            prefix = commands.when_mentioned

        super().__init__(
            command_prefix=prefix,
            intents=self.settings.intents.to_intents(),
            tree_cls=tree_cls,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
            **optional,
        )

    # -- lifecycle -------------------------------------------------------------

    async def setup_hook(self) -> None:
        """Run once, after login but before the gateway connection is ready."""
        self._started_monotonic = time.monotonic()

        if self.settings.database is not None:
            await self._init_database(self.settings.database)

        self.load_report = await load_extensions(
            self,
            packages=self.settings.extension_packages,
            disabled=self.settings.disabled_extensions,
            strict=self.settings.strict_extension_loading,
        )

        await self._sync_commands()

    async def close(self) -> None:
        """Dispose the database engine (if any) and disconnect."""
        if self._engine is not None:
            await self._engine.dispose()
        await super().close()

    async def on_ready(self) -> None:
        """Log identity and optionally set a presence."""
        if self.user is None:  # pragma: no cover - defensive
            return
        self.log.info(
            "ready as %s (id=%s) in %d guild(s), %d extension(s)",
            self.user,
            self.user.id,
            len(self.guilds),
            len(self.extensions),
        )
        if self.settings.presence_text:
            await self.change_presence(activity=discord.Game(name=self.settings.presence_text))

    # -- database -----------------------------------------------------------------

    @property
    def uptime(self) -> dt.timedelta:
        """How long since :meth:`setup_hook` ran."""
        if self._started_monotonic is None:
            return dt.timedelta(0)
        return dt.timedelta(seconds=time.monotonic() - self._started_monotonic)

    @property
    def db(self) -> Any:
        """The ``async_sessionmaker``. Raises if no database is configured."""
        if self._sessionmaker is None:
            msg = "Database not configured. Set BOT_DATABASE__URL (needs the [db] extra)."
            raise RuntimeError(msg)
        return self._sessionmaker

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        """``async with bot.session() as s: ...`` — a scoped DB session."""
        async with self.db() as session:
            yield session

    async def _init_database(self, cfg: DatabaseSettings) -> None:
        from botbase.database import build_engine, init_models, make_sessionmaker

        self._engine = build_engine(cfg)
        self._sessionmaker = make_sessionmaker(self._engine)

        if cfg.run_migrations:
            from botbase.database.migrations import upgrade

            await asyncio.to_thread(upgrade, "head")
            self.log.info("database migrations applied (alembic upgrade head)")
        elif cfg.auto_create:
            await init_models(self._engine)
            self.log.info("database tables ensured (auto_create)")

    # -- command syncing --------------------------------------------------------

    async def _sync_commands(self) -> None:
        if not self.settings.sync_commands_on_startup:
            return
        if self.settings.dev_guild_ids:
            for guild_id in self.settings.dev_guild_ids:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                self.log.info("synced %d command(s) to dev guild %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            self.log.info("synced %d global command(s)", len(synced))


def _install_fast_event_loop() -> None:
    """Best-effort install of uvloop (POSIX) / winloop (Windows).

    Never fatal: a missing or incompatible accelerator just falls back to the
    stdlib event loop.
    """
    for name in ("uvloop", "winloop"):
        try:
            module = __import__(name)
            module.install()
        except ModuleNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - accelerator is optional  # pragma: no cover
            _log.warning("could not install %s event loop: %s", name, exc)
            return
        else:
            _log.debug("using %s event loop", name)
            return


def _request_stop(bot: Bot, sig: signal.Signals) -> None:  # pragma: no cover - signal path
    _log.info("received %s, shutting down", sig.name)
    bot.loop.create_task(bot.close())


def run(settings: Settings | None = None) -> None:
    """Configure logging, then connect and run the bot until interrupted."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    _install_fast_event_loop()

    token = settings.require_token()

    async def _amain() -> None:  # pragma: no cover - needs a live gateway
        async with Bot(settings) as bot:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                with contextlib.suppress(NotImplementedError):  # not on Windows
                    loop.add_signal_handler(sig, lambda s=sig: _request_stop(bot, s))
            await bot.start(token)

    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        _log.info("shutting down")
    except discord.LoginFailure:  # pragma: no cover - needs a real (bad) token
        _log.critical("login failed: the bot token is invalid. Check BOT_TOKEN / .env.")
        raise SystemExit(1) from None
