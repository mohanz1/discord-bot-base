from __future__ import annotations

from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    msg = "boom"
    raise RuntimeError(msg)
