"""Global error handling for slash commands and prefix commands.

Expected, user-facing errors become a short ephemeral reply; anything else is
logged with a traceback and the user gets a generic message.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from botbase.cog import BaseCog

if TYPE_CHECKING:
    from botbase.app import Bot

_USER_FACING: tuple[type[Exception], ...] = (
    app_commands.MissingRole,
    app_commands.MissingAnyRole,
    app_commands.MissingPermissions,
    app_commands.BotMissingPermissions,
    app_commands.CommandOnCooldown,
    app_commands.CheckFailure,
)

# Not real failures: usually a stale command registration on Discord's side.
_IGNORED: tuple[type[Exception], ...] = (app_commands.CommandNotFound,)


async def _reply(interaction: Interaction, message: str) -> None:
    # The interaction may already be dead (expired token, timed out); don't let a
    # failed apology raise a second, unhandled exception.
    with contextlib.suppress(discord.HTTPException):
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class ErrorHandler(BaseCog):
    """Global error handling for slash and prefix commands.

    Routes app-command errors through :attr:`BotTree.error_handler` and listens
    for prefix-command errors.
    """

    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        bot.tree.error_handler = self._on_app_command_error

    async def cog_unload(self) -> None:
        """Detach from the tree."""
        self.bot.tree.error_handler = None

    async def _on_app_command_error(
        self,
        interaction: Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, _IGNORED):
            self.log.debug("ignoring %s: %s", type(error).__name__, error)
            return
        original = getattr(error, "original", error)
        if isinstance(error, _USER_FACING):
            await _reply(interaction, str(error))
            return
        self.log.exception(
            "unhandled error in /%s",
            interaction.command.name if interaction.command else "?",
            exc_info=original,
        )
        await _reply(interaction, "Something went wrong. The error has been logged.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context[Bot], error: commands.CommandError) -> None:
        """Handle classic prefix-command errors."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, (commands.UserInputError, commands.CheckFailure, commands.CommandOnCooldown)):
            await ctx.send(str(error))
            return
        original = getattr(error, "original", error)
        self.log.exception("unhandled error in %s", ctx.command, exc_info=original)
        await ctx.send("Something went wrong. The error has been logged.")


async def setup(bot: Bot) -> None:
    """discord.py entry point."""
    await bot.add_cog(ErrorHandler(bot))
