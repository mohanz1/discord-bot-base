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
    await bot.tree.on_error(None, err)  # type: ignore[arg-type]
    assert seen == [err]


async def test_on_error_falls_back_to_default(bot: Bot, caplog: object) -> None:
    class _NoCommand:
        command = None

    with caplog.at_level(logging.ERROR):
        await bot.tree.on_error(_NoCommand(), app_commands.AppCommandError("boom"))  # type: ignore[arg-type]
    assert any("command tree" in r.message for r in caplog.records)
