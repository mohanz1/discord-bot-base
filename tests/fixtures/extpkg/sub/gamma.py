from __future__ import annotations

from discord.ext import commands


class Gamma(commands.Cog):
    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gamma())
