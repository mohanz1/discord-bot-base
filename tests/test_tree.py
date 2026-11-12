from __future__ import annotations

import logging

from discord import app_commands

from botbase.app import Bot


async def test_on_error_delegates_to_handler(bot: Bot) -> None:
    seen: list[app_commands.AppCommandError] = []

    async def handler(_interaction: object, error: app_commands.AppCommandError) -> None:
        seen.append(error)

    bot.tree.error_handler = handler
    err = app_commands.AppCommandError("x")
    await bot.tree.on_error(_Interaction(None), err)  # type: ignore[arg-type]
    assert seen == [err]


async def test_on_error_falls_back_to_default(bot: Bot, caplog: object) -> None:
    class _NoCommand:
        command = None

    with caplog.at_level(logging.ERROR):
        await bot.tree.on_error(_NoCommand(), app_commands.AppCommandError("boom"))  # type: ignore[arg-type]
    assert any("command tree" in r.message for r in caplog.records)


class _Cmd:
    def __init__(self, *, has_handlers: bool) -> None:
        self._has = has_handlers
        self.name = "cmd"

    def _has_any_error_handlers(self) -> bool:
        return self._has


class _Interaction:
    def __init__(self, command: object) -> None:
        self.command = command


async def test_on_error_skips_global_handler_when_command_has_its_own(bot: Bot) -> None:
    seen: list[object] = []

    async def handler(_interaction: object, error: app_commands.AppCommandError) -> None:
        seen.append(error)

    bot.tree.error_handler = handler
    await bot.tree.on_error(_Interaction(_Cmd(has_handlers=True)), app_commands.AppCommandError("x"))  # type: ignore[arg-type]
    assert seen == []

    err = app_commands.AppCommandError("y")
    await bot.tree.on_error(_Interaction(_Cmd(has_handlers=False)), err)  # type: ignore[arg-type]
    assert seen == [err]


async def test_local_error_handler_detected_on_real_command(bot: Bot) -> None:
    @app_commands.command()
    async def cmd(interaction: object) -> None: ...

    calls: list[object] = []

    async def handler(_interaction: object, error: app_commands.AppCommandError) -> None:
        calls.append(error)

    bot.tree.error_handler = handler
    await bot.tree.on_error(_Interaction(cmd), app_commands.AppCommandError("plain"))  # type: ignore[arg-type]
    assert len(calls) == 1

    @cmd.error
    async def _local(interaction: object, error: app_commands.AppCommandError) -> None: ...

    await bot.tree.on_error(_Interaction(cmd), app_commands.AppCommandError("handled"))  # type: ignore[arg-type]
    assert len(calls) == 1
