"""``botbase`` command-line entry point."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def _version_table() -> str:
    import discord

    from botbase import __version__

    rows = [
        ("discord-bot-base", __version__),
        ("discord.py", discord.__version__),
        ("Python", platform.python_version()),
        ("Platform", platform.platform()),
    ]
    width = max(len(key) for key, _ in rows)
    return "\n".join(f"{key:<{width}}  {value}" for key, value in rows)


def _cmd_version(_args: argparse.Namespace) -> int:
    print(_version_table())  # noqa: T201 - CLI output
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from botbase.app import run
    from botbase.config import Settings

    settings = Settings(_env_file=str(args.env_file)) if args.env_file else None
    run(settings)
    return 0


def _cmd_ext_list(_args: argparse.Namespace) -> int:
    from botbase.config import get_settings
    from botbase.extensions import discover_extensions

    settings = get_settings()
    for package in settings.extension_packages:
        for name in discover_extensions(package):
            disabled = name in settings.disabled_extensions or name.rpartition(".")[2] in settings.disabled_extensions
            print(f"{name}{'  (disabled)' if disabled else ''}")  # noqa: T201 - CLI output
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    import asyncio

    import discord

    from botbase.app import Bot
    from botbase.config import get_settings
    from botbase.logs import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    async def _run() -> None:  # pragma: no cover - needs a live gateway
        token = settings.require_token()
        # login() already runs setup_hook (which loads the extensions); suppress its
        # automatic startup sync so this command is the only thing touching the tree.
        bot = Bot(settings.model_copy(update={"sync_commands_on_startup": False}))
        async with bot:
            await bot.login(token)
            scopes: list[discord.abc.Snowflake | None]
            scopes = [discord.Object(id=g) for g in args.guild] if args.guild else [None]
            for scope in scopes:
                where = "global" if scope is None else f"guild {scope.id}"
                if args.clear:
                    bot.tree.clear_commands(guild=scope)
                    await bot.tree.sync(guild=scope)
                    print(f"cleared all commands [{where}]")  # noqa: T201 - CLI output
                    continue
                if scope is not None:
                    bot.tree.copy_global_to(guild=scope)
                synced = await bot.tree.sync(guild=scope)
                print(f"synced {len(synced)} command(s) [{where}]")  # noqa: T201 - CLI output

    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 - surface the message, not a traceback
        print(exc)  # noqa: T201 - CLI output
        return 1
    return 0


def _cmd_db(args: argparse.Namespace) -> int:
    try:
        from botbase.database import migrations

        match args.db_action:
            case "upgrade":
                migrations.upgrade(args.revision)
            case "downgrade":
                migrations.downgrade(args.revision)
            case "revision":
                migrations.revision(args.message, autogenerate=not args.no_autogenerate)
            case "current":
                migrations.current()
    except Exception as exc:  # noqa: BLE001 - surface the actionable message, not a traceback
        print(exc)  # noqa: T201 - CLI output
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="botbase", description="discord-bot-base command line")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="start the bot")
    run_parser.add_argument("--env-file", type=Path, default=None, help="path to a .env file")
    run_parser.set_defaults(func=_cmd_run)

    version_parser = sub.add_parser("version", help="print version information")
    version_parser.set_defaults(func=_cmd_version)

    sync_parser = sub.add_parser("sync", help="push (or clear) slash commands on Discord")
    sync_parser.add_argument(
        "--guild",
        type=int,
        action="append",
        default=[],
        metavar="ID",
        help="target this guild (repeatable); default is a global sync",
    )
    sync_parser.add_argument(
        "--clear",
        action="store_true",
        help="remove all commands from the target scope instead of syncing",
    )
    sync_parser.set_defaults(func=_cmd_sync)

    ext_parser = sub.add_parser("ext", help="extension utilities")
    ext_sub = ext_parser.add_subparsers(dest="ext_action", required=True)
    ext_list = ext_sub.add_parser("list", help="list discoverable extensions")
    ext_list.set_defaults(func=_cmd_ext_list)

    db_parser = sub.add_parser("db", help="database migrations (needs the [db] extra)")
    db_parser.set_defaults(func=_cmd_db)
    db_sub = db_parser.add_subparsers(dest="db_action", required=True)
    db_up = db_sub.add_parser("upgrade", help="alembic upgrade")
    db_up.add_argument("revision", nargs="?", default="head")
    db_down = db_sub.add_parser("downgrade", help="alembic downgrade")
    db_down.add_argument("revision")
    db_rev = db_sub.add_parser("revision", help="create a new migration")
    db_rev.add_argument("message")
    db_rev.add_argument("--no-autogenerate", action="store_true")
    db_sub.add_parser("current", help="show the current revision")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and dispatch. Returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        return _cmd_version(args)
    return int(args.func(args) or 0)
