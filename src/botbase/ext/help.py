"""``/help`` — a command reference generated from the live command tree.

Text comes from each command's ``description=`` / ``describe()`` strings, so there
is nothing extra to maintain. Commands the caller cannot use are hidden: cogs with
``owner_only = True`` (see :class:`~botbase.cog.BaseCog`) and anything gated by
``default_permissions`` the caller lacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from botbase.cog import BaseCog

if TYPE_CHECKING:
    from discord.ext import commands

    from botbase.app import Bot

AppCommand = app_commands.Command | app_commands.Group
_BLURPLE = discord.Colour.blurple()
_FIELD_LIMIT = 1024
_CHAT_INPUT = discord.AppCommandType.chat_input


def _cog_of(bot: Bot, command: AppCommand) -> commands.Cog | None:
    """Owning cog of a command or group (``Group.binding`` isn't always set)."""
    top = command.root_parent or command
    for cog in bot.cogs.values():
        if top in cog.get_app_commands():
            return cog
    return getattr(command, "binding", None)


def _category(bot: Bot, command: AppCommand) -> str:
    """Group label for a command: its cog's ``help_category`` or class name."""
    cog = _cog_of(bot, command)
    if cog is None:
        return "General"
    return getattr(type(cog), "help_category", type(cog).__name__)


def _owner_only(bot: Bot, command: AppCommand) -> bool:
    """Return ``True`` if the command's cog is marked ``owner_only``."""
    return bool(getattr(type(_cog_of(bot, command)), "owner_only", False))


async def _visible_to(bot: Bot, interaction: discord.Interaction, command: AppCommand) -> bool:
    """Hide what the caller can't run: owner-only cogs and ``default_permissions``."""
    is_owner = await bot.is_owner(interaction.user)  # ty: ignore[invalid-argument-type]
    if _owner_only(bot, command):
        return is_owner
    perms = command.default_permissions
    if perms is None:
        return True
    if is_owner:
        return True
    have = getattr(interaction.user, "guild_permissions", None)
    return have is not None and have.is_superset(perms)


def _resolve(tree: app_commands.CommandTree, qualified: str) -> AppCommand | None:
    parts = qualified.split()
    root = tree.get_command(parts[0], type=_CHAT_INPUT)
    node: AppCommand | None = root if isinstance(root, (app_commands.Command, app_commands.Group)) else None
    for part in parts[1:]:
        if not isinstance(node, app_commands.Group):
            return None
        node = node.get_command(part)
    return node


def _param_lines(command: app_commands.Command) -> str:
    out: list[str] = []
    for param in command.parameters:
        tail = "" if param.required else " *(optional)*"
        desc = f" — {param.description}" if param.description and param.description != "\N{HORIZONTAL ELLIPSIS}" else ""
        out.append(f"`{param.name}`{tail}{desc}")
    return "\n".join(out)


class Help(BaseCog):
    """The generated command reference."""

    help_category = "Meta"

    @app_commands.command(name="help", description="List commands, or explain one in detail.")
    @app_commands.describe(command="a command name, e.g. 'ping' or 'dev exec'")
    async def help_cmd(self, interaction: discord.Interaction, command: str | None = None) -> None:
        """Show every usable command, or the details of one."""
        if command:
            await self._detail(interaction, command)
        else:
            await self._overview(interaction)

    async def _overview(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        by_category: dict[str, list[str]] = {}
        for cmd in sorted(bot.tree.get_commands(type=_CHAT_INPUT), key=lambda c: c.qualified_name):
            if not await _visible_to(bot, interaction, cmd):
                continue
            bucket = by_category.setdefault(_category(bot, cmd), [])
            if isinstance(cmd, app_commands.Group):
                bucket += [f"`/{sub.qualified_name}` — {sub.description}" for sub in cmd.commands]
            else:
                bucket.append(f"`/{cmd.name}` — {cmd.description}")

        name = bot.user.name if bot.user else "bot"
        embed = discord.Embed(title=f"{name} · commands", colour=_BLURPLE)
        for category, lines in sorted(by_category.items()):
            embed.add_field(name=category, value="\n".join(lines)[:_FIELD_LIMIT], inline=False)
        embed.set_footer(text="/help <command> for details")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _detail(self, interaction: discord.Interaction, query: str) -> None:
        bot = self.bot
        node = _resolve(bot.tree, query.strip().removeprefix("/"))
        top = node.root_parent or node if node is not None else None
        if node is None or top is None or not await _visible_to(bot, interaction, top):
            await interaction.response.send_message(f"No command `{query}`.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"/{node.qualified_name}",
            description=node.description or "\N{EM DASH}",
            colour=_BLURPLE,
        )
        if isinstance(node, app_commands.Group):
            for sub in node.commands:
                embed.add_field(name=f"/{sub.qualified_name}", value=sub.description or "\N{EM DASH}", inline=False)
        else:
            params = _param_lines(node)
            if params:
                embed.add_field(name="parameters", value=params, inline=False)
        if _owner_only(bot, top):
            embed.add_field(name="access", value="bot owner only", inline=False)
        elif top.default_permissions is not None:  # gate may live on the parent group
            embed.add_field(name="access", value="server managers / bot owner only", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @help_cmd.autocomplete("command")
    async def _complete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        bot = self.bot
        needle = current.lower()
        names: set[str] = set()
        for cmd in bot.tree.walk_commands(type=_CHAT_INPUT):
            top = cmd.root_parent or cmd
            if needle in cmd.qualified_name.lower() and await _visible_to(bot, interaction, top):
                names.add(cmd.qualified_name)
        return [app_commands.Choice(name=n, value=n) for n in sorted(names)[:25]]


async def setup(bot: Bot) -> None:
    """discord.py entry point."""
    await bot.add_cog(Help(bot))
