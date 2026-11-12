"""Custom application-command tree.

The default behaviour is permissive. :meth:`BotTree.interaction_check` is the
single hook point for gating who may use the bot's slash commands (allow-list,
block-list, maintenance mode, ...). ``ext/errors.py`` sets :attr:`BotTree.error_handler`
at load time to route command errors through a single place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    AppErrorHandler = Callable[[discord.Interaction, app_commands.AppCommandError], Awaitable[None]]


class BotTree(app_commands.CommandTree):
    """A :class:`discord.app_commands.CommandTree` with a gate and a pluggable error handler."""

    def __init__(self, client: discord.Client, *, fallback_to_global: bool = True) -> None:
        super().__init__(client, fallback_to_global=fallback_to_global)
        self.error_handler: AppErrorHandler | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # noqa: ARG002
        """Return ``True`` to allow an interaction to run.

        Override in a subclass (and pass ``tree_cls=`` to :class:`~botbase.app.Bot`)
        to implement access control.
        """
        return True

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
        /,
    ) -> None:
        """Delegate to :attr:`error_handler` if set, else the default behaviour.

        Like discord.py's default, the global handler is skipped when the command
        already has its own error handler (``@cmd.error``, a group ``on_error`` or
        ``cog_app_command_error``) -- the tree calls this *after* those ran.
        """
        if self.error_handler is None:
            await super().on_error(interaction, error)
            return
        has_local = getattr(interaction.command, "_has_any_error_handlers", None)
        if callable(has_local) and has_local():
            return
        await self.error_handler(interaction, error)
