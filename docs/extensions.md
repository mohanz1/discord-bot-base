# Writing extensions

An **extension** is a Python module with an `async def setup(bot)` function. A **cog** is
a class of related commands/listeners. You'll usually write one cog per extension and
add it in `setup()`.

## A minimal extension

`src/my_bot/ext/fun.py`:

```python
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from botbase.cog import BaseCog

if TYPE_CHECKING:
    from botbase.app import Bot


class Fun(BaseCog):
    @app_commands.command(description="Roll a die.")
    async def roll(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"🎲 {random.randint(1, 6)}")


async def setup(bot: Bot) -> None:
    await bot.add_cog(Fun(bot))
```

That's it. As long as `my_bot.ext` is in `extension_packages`, `fun` is discovered and
loaded on startup — no registration list to maintain.

## What `BaseCog` gives you

```python
class MyCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)  # sets self.bot and self.log

    async def do_thing(self):
        self.log.info("hello")  # logger named botbase.ext.<module>
        prefix = self.settings.command_prefix
        async with self.bot.session() as db:  # raises if no DB configured
            ...
```

`self.settings` is the running `Settings`; `self.db` is the `async_sessionmaker`.

## Discovery rules

`discover_extensions(package)`:

- imports `package` and walks it with `pkgutil` — works installed, editable, or zipped;
- **skips** modules and sub-packages whose leaf name starts with `_`
  (so `_shared.py`, `_helpers/` are safe to keep alongside real extensions);
- **descends** into sub-packages (`my_bot.ext.admin.users` is found).

## Enabling / disabling

- Add packages to scan: `BOT_EXTENSION_PACKAGES='["botbase.ext", "my_bot.ext"]'`
- Turn one off: `BOT_DISABLED_EXTENSIONS='["meta"]'` (leaf name) or
  `'["botbase.ext.meta"]'` (dotted path).
- Fail hard on any load error: `BOT_STRICT_EXTENSION_LOADING=true`.

## Reloading at runtime

The owner-only `/dev reload` command reloads one extension (or all of them via the
select menu). Programmatically:

```python
from botbase.extensions import reload_all

report = await reload_all(bot)
```

## The built-in extensions

Shipped in `botbase.ext`, loaded by default, each disable-able:

| Module | Commands | Notes |
| --- | --- | --- |
| `meta` | `/ping`, `/about`, `/uptime` | Latency meter; `/about` has an owner-only detail view. |
| `help` | `/help [command]` | Generated from the live tree; hides commands you can't run. |
| `errors` | – | Global slash + prefix error handling. |
| `admin` | `/dev reload\|load\|unload\|sync\|exec` | Owner-only (`is_owner`). `owner_only = True`. |

## Owner-only cogs

```python
import discord

from botbase.cog import BaseCog


class Ops(BaseCog):
    owner_only = True  # /help hides this cog from non-owners

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.is_owner(interaction.user)
```
