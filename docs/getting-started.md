# Getting started

## From the template (recommended)

```bash
uvx copier copy gh:mohanz1/discord-bot-base my-bot
cd my-bot
uv sync
cp .env.example .env          # set BOT_TOKEN
uv run my-bot
```

Copier asks a few questions (project name, whether you want a database, Python floor)
and produces a complete project: an example `hello` extension, strict `ruff` / `ty` /
`pytest` config, a `Dockerfile`, and CI. Its `Settings` subclass already points
`extension_packages` at both `botbase.ext` and your package.

## As a dependency

```bash
uv init my-bot && cd my-bot
uv add discord-bot-base
```

Create `src/my_bot/config.py`:

```python
from botbase import Settings as BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    extension_packages: list[str] = Field(
        default_factory=lambda: ["botbase.ext", "my_bot.ext"],
    )
```

Create `src/my_bot/__main__.py`:

```python
from botbase import run

from my_bot.config import Settings


def main() -> None:
    run(Settings())


if __name__ == "__main__":
    main()
```

Add a cog at `src/my_bot/ext/hello.py`:

```python
from __future__ import annotations

import discord
from discord import app_commands

from botbase.cog import BaseCog


class Hello(BaseCog):
    @app_commands.command(description="Say hi.")
    async def hello(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"hi {interaction.user.mention}")


async def setup(bot) -> None:
    await bot.add_cog(Hello(bot))
```

Then:

```bash
echo "BOT_TOKEN=..." > .env
uv run python -m my_bot
```

## First run

On startup the bot:

1. loads every extension it discovers in `extension_packages`
   (`botbase.ext` ships `meta`, `help`, `errors`, `admin`);
2. connects to the gateway;
3. syncs slash commands — instantly to `dev_guild_ids` if set, otherwise a slow global sync.

Try `/ping`, `/about`, `/uptime`, and `/help` in your server. See
[Configuration](configuration.md) for the full list of `BOT_*` variables.
