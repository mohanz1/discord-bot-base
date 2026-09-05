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

    # ty (beta) flags this documented discord.py override on `self`/generic variance.
    async def on_error(  # ty: ignore[invalid-method-override]
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
        /,
    ) -> None:
        """Delegate to :attr:`error_handler` if set, else the default behaviour."""
        if self.error_handler is not None:
            await self.error_handler(interaction, error)
        else:
            await super().on_error(interaction, error)
