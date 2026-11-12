"""Owner-only maintenance behind ``/dev`` — one panel of reload, load, unload, sync and exec.

The panel's **Exec** button (like the old ``/dev exec``) runs arbitrary Python
**as the bot owner** — gated by :meth:`Bot.is_owner` on every path: the cog
check, the panel's ``interaction_check``, and the runner itself. Disable the
whole cog with ``BOT_DISABLED_EXTENSIONS='["admin"]'`` if you would rather not
ship it.

``/dev`` carries ``default_permissions`` of *nothing*, so Discord's command
picker hides it from everyone without admin in the guild; ``/help`` hides it too
via the cog's ``owner_only`` flag. It is also ``guild_only``: Discord ignores
``default_permissions`` in DMs, so without that it would show to *everyone* who
DMs the bot. To pin it to a single user, add a command override in
*Server Settings -> Integrations* (Discord offers no API for that).
"""

from __future__ import annotations

import contextlib
import io
import textwrap
import traceback
from functools import partial
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
_E_RELOAD = "\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}"
_E_LOAD = "\N{INBOX TRAY}"
_E_UNLOAD = "\N{OUTBOX TRAY}"
_E_EXEC = "\N{SNAKE}"
_E_SYNC = "\N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}"


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


# -- extension / sync actions (module-level so the panel and the tests share them) --


async def _do_load(bot: Bot, interaction: discord.Interaction, name: str) -> None:
    """Load a not-yet-loaded extension and report the outcome."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    resolved = _resolve(bot, name)
    try:
        await bot.load_extension(resolved)
    except commands.ExtensionError as exc:
        await interaction.followup.send(f"could not load `{resolved}`: {exc}", ephemeral=True)
    else:
        await interaction.followup.send(f"loaded `{resolved}`", ephemeral=True)


async def _do_unload(bot: Bot, interaction: discord.Interaction, name: str) -> None:
    """Unload a loaded extension and report the outcome."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    resolved = _resolve(bot, name)
    try:
        await bot.unload_extension(resolved)
    except commands.ExtensionError as exc:
        await interaction.followup.send(f"could not unload `{resolved}`: {exc}", ephemeral=True)
    else:
        await interaction.followup.send(f"unloaded `{resolved}`", ephemeral=True)


async def _do_sync(bot: Bot, interaction: discord.Interaction, scope: Literal["guild", "global"]) -> None:
    """Push the current command tree to this server (instant) or globally (slow)."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    if scope == "guild":
        if interaction.guild is None:
            await interaction.followup.send("run this in a server for guild scope", ephemeral=True)
            return
        bot.tree.copy_global_to(guild=interaction.guild)
        synced = await bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send(f"synced {len(synced)} command(s) to this server", ephemeral=True)
    else:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"synced {len(synced)} global command(s)", ephemeral=True)


# -- modals -------------------------------------------------------------------------


class _ExecModal(discord.ui.Modal, title="exec"):
    """A multi-line text box for the panel's **Exec** button."""

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


class _ExtModal(discord.ui.Modal):
    """A one-line extension-name box for the **Load** / **Unload** buttons."""

    name: discord.ui.TextInput = discord.ui.TextInput(
        label="Extension",
        placeholder="meta    ·    botbase.ext.meta",
        required=True,
        max_length=200,
    )

    def __init__(
        self,
        op: Literal["load", "unload"],
        runner: Callable[[discord.Interaction, str], Awaitable[None]],
    ) -> None:
        super().__init__(title=op)
        self._runner = runner

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Run the load / unload with the typed name."""
        await self._runner(interaction, self.name.value)


# -- reload picker ----------------------------------------------------------------


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
    """Ephemeral picker opened by the panel's **Reload** button."""

    def __init__(self, bot: Bot) -> None:
        super().__init__(timeout=120)
        self.add_item(_ReloadSelect(bot))


# -- the panel ------------------------------------------------------------------------


def _panel_embed() -> discord.Embed:
    return discord.Embed(
        title="Dev tools",
        description="Owner-only maintenance — reload, load / unload, sync, exec.",
        colour=discord.Colour.blurple(),
    )


class DevPanel(discord.ui.View):
    """Ephemeral, owner-only launcher shown by ``/dev``."""

    def __init__(self, bot: Bot, eval_runner: Callable[[discord.Interaction, str], Awaitable[None]]) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self._eval_runner = eval_runner
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Gate every button to the bot owner(s)."""
        if await self.bot.is_owner(interaction.user):  # ty: ignore[invalid-argument-type]
            return True
        await interaction.response.send_message("This command is owner-only.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        """Disable every button when the panel expires."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)

    @discord.ui.button(label="Reload", style=discord.ButtonStyle.primary, emoji=_E_RELOAD)
    async def reload(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Open the extension-reload picker."""
        await interaction.response.send_message(
            "pick extensions to reload:", view=_ReloadView(self.bot), ephemeral=True
        )

    @discord.ui.button(label="Load", style=discord.ButtonStyle.secondary, emoji=_E_LOAD)
    async def load(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Prompt for an extension to load."""
        await interaction.response.send_modal(_ExtModal("load", partial(_do_load, self.bot)))

    @discord.ui.button(label="Unload", style=discord.ButtonStyle.secondary, emoji=_E_UNLOAD)
    async def unload(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Prompt for an extension to unload."""
        await interaction.response.send_modal(_ExtModal("unload", partial(_do_unload, self.bot)))

    @discord.ui.button(label="Exec", style=discord.ButtonStyle.danger, emoji=_E_EXEC)
    async def exec_(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Open the Python editor."""
        await interaction.response.send_modal(_ExecModal(self._eval_runner))

    @discord.ui.button(label="Sync — server", style=discord.ButtonStyle.secondary, emoji=_E_SYNC, row=1)
    async def sync_guild(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Sync the command tree to this server."""
        await _do_sync(self.bot, interaction, "guild")

    @discord.ui.button(label="Sync — global", style=discord.ButtonStyle.secondary, emoji=_RELOAD_ALL, row=1)
    async def sync_global(self, interaction: discord.Interaction, _button: discord.ui.Button[DevPanel]) -> None:
        """Sync the command tree globally."""
        await _do_sync(self.bot, interaction, "global")


class Admin(BaseCog):
    """Owner-only extension management and a Python eval, behind ``/dev``."""

    owner_only = True

    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self._last_eval: object = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Gate every command in this cog to the bot owner(s)."""
        if await self.bot.is_owner(interaction.user):  # ty: ignore[invalid-argument-type]
            return True
        msg = "This command is owner-only."
        raise app_commands.CheckFailure(msg)

    @app_commands.command(name="dev", description="Owner-only maintenance tools.")
    @app_commands.default_permissions()
    @app_commands.guild_only()  # default_permissions doesn't apply in DMs — keep it out of them
    async def dev(self, interaction: discord.Interaction) -> None:
        """Open the owner maintenance panel."""
        panel = DevPanel(self.bot, self._run_eval)
        await interaction.response.send_message(embed=_panel_embed(), view=panel, ephemeral=True)
        panel.message = await interaction.original_response()

    # -- eval ---------------------------------------------------------------------

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
