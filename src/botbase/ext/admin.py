"""Owner-only maintenance commands: ``/dev reload|load|unload|sync|exec``.

``/dev exec`` runs arbitrary Python **as the bot owner** — it is gated by
:meth:`Bot.is_owner` on every path (the cog check *and* the runner itself).
Disable the whole cog with ``BOT_DISABLED_EXTENSIONS='["admin"]'`` if you would
rather not ship it.

``/dev`` is a normal global command — anyone can see it, but only the bot owner
(or ``BOT_OWNER_IDS``) can run it; ``/help`` hides it from everyone else via the
cog's ``owner_only`` flag.
"""

from __future__ import annotations

import contextlib
import io
import textwrap
import traceback
from typing import TYPE_CHECKING, Literal, cast

import discord
from discord import app_commands
from discord.ext import commands

from botbase.cog import BaseCog
from botbase.extensions import LoadReport, discover_extensions, reload_all

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from botbase.app import Bot

_MAX_BLOCK = 1990
_RELOAD_ALL = "\N{GLOBE WITH MERIDIANS}"


async def _reload_named(bot: Bot, names: list[str]) -> LoadReport:
    """Reload each named extension, collecting failures."""
    report = LoadReport()
    for name in names:
        try:
            await bot.reload_extension(name)
        except commands.ExtensionError as exc:
            report.failed[name] = exc
        else:
            report.loaded.append(name)
    return report


def _summarise(report: LoadReport) -> str:
    summary = f"reloaded {len(report.loaded)}"
    if report.failed:
        names = ", ".join(f"`{n}`" for n in report.failed)
        summary += f" · **{len(report.failed)} failed**: {names}"
    return summary


def _cleanup_code(content: str) -> str:
    """Strip a ```` ```py ```` fence or stray backticks from pasted code."""
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:-1])
    return content.strip("` \n")


def _resolve(bot: Bot, name: str) -> str:
    """Map a leaf name or dotted path to a real extension path."""
    if name in bot.extensions:
        return name
    for loaded in bot.extensions:
        if loaded.rpartition(".")[2] == name:
            return loaded
    for package in bot.settings.extension_packages:
        for dotted in discover_extensions(package):
            if name in (dotted, dotted.rpartition(".")[2]):
                return dotted
    return name  # let discord.py raise a clear error


class _ExecModal(discord.ui.Modal, title="exec"):
    """A multi-line text box for ``/dev exec`` when called with no ``code``."""

    source: discord.ui.TextInput = discord.ui.TextInput(
        label="Python",
        style=discord.TextStyle.paragraph,
        placeholder="await channel.send('hi')\nreturn bot.latency",
        required=True,
        max_length=4000,
    )

    def __init__(self, runner: Callable[[discord.Interaction, str], Awaitable[None]]) -> None:
        super().__init__()
        self._runner = runner

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Run the submitted source."""
        await self._runner(interaction, self.source.value)


class _ReloadSelect(discord.ui.Select["_ReloadView"]):
    """A dropdown of loaded extensions to reload."""

    def __init__(self, bot: Bot) -> None:
        loaded = sorted(bot.extensions)
        options = [
            discord.SelectOption(label="all extensions", value=_RELOAD_ALL, emoji=_RELOAD_ALL),
            *(
                discord.SelectOption(label=name.rpartition(".")[2], value=name, description=name[:100])
                for name in loaded[:24]
            ),
        ]
        super().__init__(
            placeholder="choose extensions to reload\N{HORIZONTAL ELLIPSIS}",
            min_values=1,
            max_values=len(options),
            options=options,
        )
        self._bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        """Reload the selected extensions and report."""
        if not await self._bot.is_owner(interaction.user):  # ty: ignore[invalid-argument-type]
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        if _RELOAD_ALL in self.values:
            report = await reload_all(self._bot)
        else:
            report = await _reload_named(self._bot, self.values)
        self.disabled = True
        await interaction.response.edit_message(content=_summarise(report), view=self.view)


class _ReloadView(discord.ui.View):
    """Ephemeral picker shown by ``/dev reload`` with no argument."""

    def __init__(self, bot: Bot) -> None:
        super().__init__(timeout=120)
        self.add_item(_ReloadSelect(bot))


class Admin(BaseCog):
    """Owner-only extension management and a Python eval."""

    owner_only = True
    dev = app_commands.Group(name="dev", description="Owner-only maintenance.")

    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self._last_eval: object = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Gate every command in this cog to the bot owner(s)."""
        if await self.bot.is_owner(interaction.user):  # ty: ignore[invalid-argument-type]
            return True
        msg = "This command is owner-only."
        raise app_commands.CheckFailure(msg)

    # -- extension management --------------------------------------------------

    @dev.command(name="reload", description="Reload an extension, or pick from a menu if omitted.")
    @app_commands.describe(extension="dotted path or leaf name; omit to open a picker")
    async def reload(self, interaction: discord.Interaction, extension: str | None = None) -> None:
        """Hot-reload extensions without restarting the bot."""
        if extension is None:
            await interaction.response.send_message(
                "pick extensions to reload:",
                view=_ReloadView(self.bot),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        name = _resolve(self.bot, extension)
        try:
            await self.bot.reload_extension(name)
        except commands.ExtensionError as exc:
            await interaction.followup.send(f"could not reload `{name}`: {exc}", ephemeral=True)
        else:
            await interaction.followup.send(f"reloaded `{name}`", ephemeral=True)

    @dev.command(name="load", description="Load an extension.")
    async def load(self, interaction: discord.Interaction, extension: str) -> None:
        """Load a not-yet-loaded extension."""
        await interaction.response.defer(ephemeral=True)
        name = _resolve(self.bot, extension)
        try:
            await self.bot.load_extension(name)
        except commands.ExtensionError as exc:
            await interaction.followup.send(f"could not load `{name}`: {exc}", ephemeral=True)
        else:
            await interaction.followup.send(f"loaded `{name}`", ephemeral=True)

    @dev.command(name="unload", description="Unload an extension.")
    async def unload(self, interaction: discord.Interaction, extension: str) -> None:
        """Unload a loaded extension."""
        await interaction.response.defer(ephemeral=True)
        name = _resolve(self.bot, extension)
        try:
            await self.bot.unload_extension(name)
        except commands.ExtensionError as exc:
            await interaction.followup.send(f"could not unload `{name}`: {exc}", ephemeral=True)
        else:
            await interaction.followup.send(f"unloaded `{name}`", ephemeral=True)

    @dev.command(name="sync", description="Re-sync application commands.")
    @app_commands.describe(scope="'guild' (this server, instant) or 'global' (slow propagation)")
    async def sync(
        self,
        interaction: discord.Interaction,
        scope: Literal["guild", "global"] = "guild",
    ) -> None:
        """Push the current command tree to Discord."""
        await interaction.response.defer(ephemeral=True)
        if scope == "guild":
            if interaction.guild is None:
                await interaction.followup.send("run this in a server for guild scope", ephemeral=True)
                return
            self.bot.tree.copy_global_to(guild=interaction.guild)
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"synced {len(synced)} command(s) to this server", ephemeral=True)
        else:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"synced {len(synced)} global command(s)", ephemeral=True)

    # -- eval ---------------------------------------------------------------------

    @dev.command(name="exec", description="Execute Python as the bot owner.")
    @app_commands.describe(code="Python source; omit to open a multi-line editor")
    async def exec_(self, interaction: discord.Interaction, code: str | None = None) -> None:
        """Run Python. With no ``code`` argument, open a modal editor."""
        if code is None:
            await interaction.response.send_modal(_ExecModal(self._run_eval))
            return
        await self._run_eval(interaction, code)

    async def _run_eval(self, interaction: discord.Interaction, raw: str) -> None:
        if not await self.bot.is_owner(interaction.user):  # ty: ignore[invalid-argument-type]
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        env: dict[str, object] = {
            "bot": self.bot,
            "interaction": interaction,
            "discord": discord,
            "commands": commands,
            "channel": interaction.channel,
            "guild": interaction.guild,
            "author": interaction.user,
            "_": self._last_eval,
        }
        wrapped = "async def __evalfunc__():\n" + textwrap.indent(_cleanup_code(raw), "    ")
        try:
            exec(wrapped, env)  # noqa: S102 - owner-gated debug tooling, by design
        except SyntaxError:
            await self._send_result(interaction, traceback.format_exc())
            return

        func = cast("Callable[[], Awaitable[object]]", env["__evalfunc__"])
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                result = await func()
        except Exception:  # noqa: BLE001 - surface every error to the owner
            await self._send_result(interaction, stdout.getvalue() + traceback.format_exc())
            return

        self._last_eval = result
        out = stdout.getvalue() + (repr(result) if result is not None else "")
        await self._send_result(interaction, out or "(no output)")

    @staticmethod
    async def _send_result(interaction: discord.Interaction, text: str) -> None:
        block = f"```py\n{text}\n```"
        if len(block) <= _MAX_BLOCK:
            await interaction.followup.send(block, ephemeral=True)
        else:
            file = discord.File(io.BytesIO(text.encode()), filename="exec.txt")
            await interaction.followup.send("output too long:", file=file, ephemeral=True)


async def setup(bot: Bot) -> None:
    """discord.py entry point."""
    await bot.add_cog(Admin(bot))
