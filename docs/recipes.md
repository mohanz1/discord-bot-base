# Recipes

Short, copy-pasteable patterns. All assume a cog that extends `BaseCog`.

## Command groups

```python
from discord import app_commands

from botbase.cog import BaseCog


class Tags(BaseCog):
    group = app_commands.Group(name="tag", description="Manage tags.")

    @group.command(name="get")
    async def get(self, interaction, name: str) -> None:
        await interaction.response.send_message(f"tag {name}")

    @group.command(name="set")
    async def set_(self, interaction, name: str, content: str) -> None:
        await interaction.response.send_message(f"set {name}", ephemeral=True)
```

## Background tasks

```python
from discord.ext import tasks

from botbase.cog import BaseCog


class Cleaner(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.sweep.start()

    async def cog_unload(self) -> None:
        self.sweep.cancel()

    @tasks.loop(minutes=30)
    async def sweep(self) -> None:
        self.log.info("sweeping")

    @sweep.before_loop
    async def _wait(self) -> None:
        await self.bot.wait_until_ready()
```

## A persistent view

Register it once in `setup()` so buttons keep working across restarts.

```python
import discord

from botbase.cog import BaseCog


class Confirm(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="OK", style=discord.ButtonStyle.green, custom_id="confirm:ok")
    async def ok(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_message("confirmed", ephemeral=True)


class Panel(BaseCog):
    @discord.app_commands.command()
    async def panel(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("choose:", view=Confirm())


async def setup(bot) -> None:
    bot.add_view(Confirm())  # re-attach handlers on startup
    await bot.add_cog(Panel(bot))
```

## A custom command-tree gate

Block everyone except a set of guilds while you're testing:

```python
import discord
from discord import app_commands

from botbase.app import Bot
from botbase.tree import BotTree
from botbase.config import get_settings


class GatedTree(BotTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed = {123456789012345678}
        if interaction.guild_id in allowed:
            return True
        await interaction.response.send_message("Not available here yet.", ephemeral=True)
        return False


bot = Bot(get_settings(), tree_cls=GatedTree)
```

## Multiple extension packages

```dotenv
BOT_EXTENSION_PACKAGES=["botbase.ext", "my_bot.ext", "my_bot.plugins"]
```

Or in a `Settings` subclass:

```python
extension_packages: list[str] = Field(
    default_factory=lambda: ["botbase.ext", "my_bot.ext", "my_bot.plugins"],
)
```

## Rich or JSON logging

```dotenv
BOT_LOG_FORMAT=rich     # needs: uv add "discord-bot-base[rich]"
# or
BOT_LOG_FORMAT=json     # line-delimited JSON, no extra dependency
```

## Database

Enable it (`uv sync --extra db`, set `BOT_DATABASE__URL`) and define your models against
the re-exported metadata:

```python
# my_bot/models.py
from sqlmodel import Field, SQLModel


class Note(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
```

Query from a cog:

```python
from sqlmodel import select

from my_bot.models import Note


class Notes(BaseCog):
    @discord.app_commands.command()
    async def get(self, interaction, key: str) -> None:
        async with self.bot.session() as db:
            row = (await db.exec(select(Note).where(Note.key == key))).one_or_none()
        await interaction.response.send_message(row.value if row else "not found", ephemeral=True)

    @discord.app_commands.command()
    async def set(self, interaction, key: str, value: str) -> None:
        async with self.bot.session() as db:
            await db.merge(Note(key=key, value=value))
            await db.commit()
        await interaction.response.send_message("saved", ephemeral=True)
```

For real schema history, point Alembic at `SQLModel.metadata` (the template's `alembic/`
already does), set `BOT_DATABASE__RUN_MIGRATIONS=true`, and use `botbase db revision -m
"…"` / `botbase db upgrade`.
