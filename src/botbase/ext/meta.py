"""``/ping``, ``/about`` and ``/uptime`` — introspection commands."""

from __future__ import annotations

import asyncio
import contextlib
import gc
import math
import os
import platform
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands

from botbase.cog import BaseCog
from botbase.utils import humanize_timedelta, plural

if TYPE_CHECKING:
    from botbase.app import Bot

_METER_WIDTH = 20
_METER_SCALE_MS = 250.0  # a full bar ~= 250 ms
_GOOD_MS = 100.0
_OK_MS = 250.0
_LOOP_SAMPLES = 25
_LOOP_PROBE_S = 0.004  # 4 ms timer; we measure how late it actually fires
_LOOP_WARN_MS = 5.0  # only surface loop-lag detail once the tail gets this bad
_FULL = "\N{FULL BLOCK}"
_EMPTY = "\N{LIGHT SHADE}"

_ANSI_RESET = "\x1b[0m"
_ANSI_LABEL = "\x1b[1;37m"
_ANSI_GREEN = "\x1b[0;32m"
_ANSI_AMBER = "\x1b[0;33m"
_ANSI_RED = "\x1b[0;31m"
_ANSI_GREY = "\x1b[0;30m"


def _grade(ms: float) -> tuple[str, discord.Colour]:
    """Return an ANSI colour code and a matching embed colour for a latency."""
    if not math.isfinite(ms):
        return _ANSI_GREY, discord.Colour(0x99AAB5)  # unknown / not connected
    if ms < _GOOD_MS:
        return _ANSI_GREEN, discord.Colour(0x3BA55D)
    if ms < _OK_MS:
        return _ANSI_AMBER, discord.Colour(0xFAA61A)
    return _ANSI_RED, discord.Colour(0xED4245)


def _meter(ms: float) -> str:
    if not math.isfinite(ms):
        return _EMPTY * _METER_WIDTH
    ratio = min(max(ms, 0.0) / _METER_SCALE_MS, 1.0)
    filled = round(ratio * _METER_WIDTH)
    return _FULL * filled + _EMPTY * (_METER_WIDTH - filled)


def _rss_mib() -> float | None:
    """Return the current resident set size in MiB (stdlib only), or ``None``."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024  # kB -> MiB
    except OSError:
        pass
    try:
        import resource
    except ImportError:
        return None
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KiB on Linux, bytes on macOS
    return raw / 1024 if sys.platform != "darwin" else raw / 1024 / 1024


def _loop_impl() -> str:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover - always inside a loop here
        return "unknown"
    return type(loop).__module__.split(".")[0]


def _build_about_embed(bot: Bot, *, owner: bool) -> discord.Embed:
    """Assemble the ``/about`` embed. Owner-only fields are appended when ``owner``."""
    from botbase import __version__

    name = bot.user.name if bot.user else "bot"
    gateway_ms = bot.latency * 1000
    py = f"{platform.python_version()} ({platform.python_implementation()})"
    slash_cmds = sum(1 for _ in bot.tree.walk_commands())

    embed = discord.Embed(title=f"about {name}", colour=discord.Colour(0x5865F2))
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    # Safe for anyone: versions, uptime, this-server-visible latency.
    for field_name, value in (
        ("version", f"botbase `{__version__}`\ndiscord.py `{discord.__version__}`"),
        ("python", f"`{py}`"),
        ("event loop", f"`{_loop_impl()}`"),
        ("uptime", humanize_timedelta(bot.uptime)),
        ("gateway", f"{gateway_ms:.0f} ms" if math.isfinite(gateway_ms) else "n/a"),
        ("commands", plural(slash_cmds, "slash command")),
    ):
        embed.add_field(name=field_name, value=value)

    # Host internals + aggregate reach: owner only. Move a line up if you
    # deliberately want to show your bot's size publicly.
    if owner:
        rss = _rss_mib()
        members = sum((g.member_count or 0) for g in bot.guilds)
        channels = sum(len(g.channels) for g in bot.guilds)
        for field_name, value in (
            ("host", f"`{platform.system()} {platform.machine()}`"),
            ("memory", f"{rss:.0f} MiB" if rss is not None else "n/a"),
            ("process", f"pid `{os.getpid()}` · {plural(threading.active_count(), 'thread')}"),
            ("shards", str(bot.shard_count or 1)),
            ("guilds", f"{len(bot.guilds):,}"),
            ("members", f"~{members:,}"),
            ("users cached", f"{len(bot.users):,}"),
            ("channels", f"{channels:,}"),
            ("cogs / exts", f"{len(bot.cogs)} / {len(bot.extensions)}"),
            ("gc gen counts", " / ".join(str(n) for n in gc.get_count())),
        ):
            embed.add_field(name=field_name, value=value)
        embed.set_footer(text="extended stats shown to the bot owner only")

    embed.timestamp = discord.utils.utcnow()
    return embed


async def refresh_about(interaction: discord.Interaction, view: discord.ui.View) -> None:
    """Rebuild the ``/about`` embed with current numbers and edit the message."""
    bot = cast("Bot", interaction.client)
    owner = await bot.is_owner(interaction.user)  # ty: ignore[invalid-argument-type]
    await interaction.response.edit_message(embed=_build_about_embed(bot, owner=owner), view=view)


class _AboutView(discord.ui.View):
    """A ``/about`` embed with a live Refresh button (times out after 2 min)."""

    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.message: discord.Message | None = None

    @discord.ui.button(label="Refresh", emoji="\N{ANTICLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}")
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        """Re-render the embed with current numbers."""
        await refresh_about(interaction, self)

    async def on_timeout(self) -> None:
        """Grey out the button once the view expires."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)


class Meta(BaseCog):
    """Latency and build-info commands."""

    @app_commands.command(name="ping", description="Gateway, REST and event-loop latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Measure the three latencies that matter for a bot."""
        gateway_ms = self.bot.latency * 1000

        # Acknowledge first (3-second interaction window), then do the sampling.
        rest_start = time.perf_counter()
        await interaction.response.send_message("pinging\N{HORIZONTAL ELLIPSIS}")
        rest_ms = (time.perf_counter() - rest_start) * 1000

        # Event-loop lag: schedule a short timer, measure how late it actually fires.
        loop = asyncio.get_running_loop()
        samples: list[float] = []
        for _ in range(_LOOP_SAMPLES):
            start = loop.time()
            await asyncio.sleep(_LOOP_PROBE_S)
            samples.append(max(0.0, (loop.time() - start - _LOOP_PROBE_S) * 1000))
        samples.sort()
        loop_avg = sum(samples) / len(samples)
        loop_p95 = samples[min(len(samples) - 1, round(len(samples) * 0.95))]

        lines = ["```ansi"]
        for label, value in (("gateway", gateway_ms), ("rest", rest_ms), ("loop", loop_avg)):
            colour, _ = _grade(value)
            shown = f"{value:8.2f} ms" if math.isfinite(value) else "     n/a"
            lines.append(f"{_ANSI_LABEL}{label:<8}{_ANSI_RESET} {colour}{_meter(value)}{_ANSI_RESET} {shown}")
        if loop_p95 >= _LOOP_WARN_MS:
            lines.append(f"{_ANSI_AMBER}loop p95 {loop_p95:.2f} ms — event loop is under pressure{_ANSI_RESET}")
        lines.append("```")

        finite = [v for v in (gateway_ms, rest_ms) if math.isfinite(v)]
        _, embed_colour = _grade(max(finite) if finite else math.nan)
        embed = discord.Embed(title="pong", description="\n".join(lines), colour=embed_colour)
        embed.timestamp = interaction.created_at
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="about", description="Build and runtime info.")
    async def about(self, interaction: discord.Interaction) -> None:
        """Report build info publicly; infra + reach stats only to the bot owner."""
        bot: Bot = self.bot
        owner = await bot.is_owner(interaction.user)  # ty: ignore[invalid-argument-type]
        view = _AboutView()
        await interaction.response.send_message(embed=_build_about_embed(bot, owner=owner), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="uptime", description="How long the bot has been running.")
    async def uptime(self, interaction: discord.Interaction) -> None:
        """Report uptime as a human string."""
        await interaction.response.send_message(
            f"Up for **{humanize_timedelta(self.bot.uptime)}**.",
        )


async def setup(bot: Bot) -> None:
    """discord.py entry point."""
    await bot.add_cog(Meta(bot))
