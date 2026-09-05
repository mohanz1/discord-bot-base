from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from botbase.app import Bot
from botbase.ext.errors import ErrorHandler

if TYPE_CHECKING:
    from tests.conftest import FakeInteraction


async def test_installs_and_detaches_from_tree(bot: Bot) -> None:
    await bot.load_extension("botbase.ext.errors")
    assert bot.tree.error_handler is not None
    await bot.unload_extension("botbase.ext.errors")
    assert bot.tree.error_handler is None


async def test_user_facing_error_is_reported_verbatim(bot: Bot, interaction: FakeInteraction) -> None:
    cog = ErrorHandler(bot)
    err = app_commands.MissingPermissions(["manage_guild"])
    await cog._on_app_command_error(interaction, err)
    assert interaction.response.messages[0]["ephemeral"] is True
    assert "missing" in interaction.response.messages[0]["content"].lower()


async def test_command_not_found_is_silently_ignored(bot: Bot, interaction: FakeInteraction) -> None:
    cog = ErrorHandler(bot)
    await cog._on_app_command_error(interaction, app_commands.CommandNotFound("feedback", []))
    assert interaction.response.messages == []
    assert interaction.followup.messages == []


async def test_unknown_error_is_generic_and_logged(
    bot: Bot,
    interaction: FakeInteraction,
    caplog: object,
) -> None:
    cog = ErrorHandler(bot)
    err = app_commands.AppCommandError("kaboom")
    await cog._on_app_command_error(interaction, err)
    assert "went wrong" in interaction.response.messages[0]["content"]


async def test_reply_swallows_dead_interaction(bot: Bot, interaction: FakeInteraction) -> None:
    import discord

    async def boom(*_a: object, **_k: object) -> None:
        raise discord.NotFound(_FakeResp(), "Unknown interaction")

    interaction.response.send_message = boom  # type: ignore[method-assign]
    cog = ErrorHandler(bot)
    # Must not raise even though the apology can't be delivered.
    await cog._on_app_command_error(interaction, app_commands.AppCommandError("kaboom"))


class _FakeResp:
    status = 404
    reason = "Not Found"


async def test_followup_used_when_response_already_done(bot: Bot, interaction: FakeInteraction) -> None:
    cog = ErrorHandler(bot)
    await interaction.response.send_message("earlier")
    await cog._on_app_command_error(interaction, app_commands.CheckFailure("nope"))
    assert interaction.followup.messages[0]["content"] == "nope"


class _FakeCtx:
    def __init__(self) -> None:
        self.command = "demo"
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        self.sent.append(content)


async def test_prefix_command_not_found_is_ignored(bot: Bot) -> None:
    cog = ErrorHandler(bot)
    ctx = _FakeCtx()
    await cog.on_command_error(ctx, commands.CommandNotFound())  # type: ignore[arg-type]
    assert ctx.sent == []


async def test_prefix_user_input_error_is_echoed(bot: Bot) -> None:
    cog = ErrorHandler(bot)
    ctx = _FakeCtx()
    await cog.on_command_error(ctx, commands.BadArgument("bad value"))  # type: ignore[arg-type]
    assert ctx.sent == ["bad value"]


async def test_prefix_unknown_error_is_generic(bot: Bot) -> None:
    cog = ErrorHandler(bot)
    ctx = _FakeCtx()
    await cog.on_command_error(ctx, commands.CommandError("kaboom"))  # type: ignore[arg-type]
    assert "went wrong" in ctx.sent[0]
