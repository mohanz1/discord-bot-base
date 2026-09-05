# discord-bot-base

[![CI](https://github.com/mohanz1/discord-bot-base/actions/workflows/ci.yml/badge.svg)](https://github.com/mohanz1/discord-bot-base/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with ty](https://img.shields.io/badge/types-ty-261230)](https://github.com/astral-sh/ty)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A modern, `uv`-first foundation for Discord bots. It gives you the boring-but-important parts once,
so each new bot is just cogs and config:

- **Dynamic extension loading** — drop a module in a package, it gets discovered and loaded (works
  installed, editable, or zipped; no directory scanning).
- **Typed, env-first config** — `pydantic-settings`, `BOT_`-prefixed variables, `.env` support,
  `SecretStr` token.
- **A `Bot` subclass** that wires intents, prefix, a custom command tree, extension loading, command
  syncing, uptime, and an optional async database off your settings.
- **Built-in commands** — `/ping` (gateway + REST + event-loop-lag meter), `/about` (build/runtime
  info with a live Refresh button; host + reach stats owner-only), `/uptime`, `/help` (generated
  from the command tree, autocomplete, hides what you can't use), a global error handler, and an
  owner-only `/dev` group (`reload` with a select-menu picker, `load`, `unload`, `sync`, `exec`
  with a multi-line modal).
- **Optional async DB layer** (`[db]` extra) — SQLModel + SQLAlchemy 2 + `aiosqlite`, with the
  async Alembic wiring done. You bring the models; the base ships the machinery.
- **Strict tooling** — `ruff` (lint + format), `ty`, `slotscheck`, `codespell`, `pytest` with a
  90% branch-coverage gate, `nox`, `pre-commit`, and GitHub Actions (lint / types / test matrix
  3.13 + 3.14 / copier-template smoke). Every check blocks merge.
- **A `copier` template** in [`template/`](template/) that scaffolds a full bot project —
  including its own `Dockerfile`, migrations, and CI.

Requires Python 3.13+. Graceful `SIGTERM` shutdown for containers.

## Quickstart (hacking on the base itself)

```bash
uv sync --all-extras
cp .env.example .env          # then put your token in BOT_TOKEN
uv run botbase run
```

Other commands:

```bash
uv run botbase version                     # or: python -m botbase
uv run botbase ext list                    # list discoverable extensions
uv run botbase sync                         # push slash commands (global)
uv run botbase sync --guild 123 --clear    # wipe a scope; --clear alone = global
uv run botbase db upgrade                   # run migrations (needs the [db] extra)
```

### Owner-only commands

`/dev reload | load | unload | sync | exec` are visible to everyone but only runnable by an owner
(`bot.is_owner`, checked in the cog's `interaction_check`); `/help` hides them from non-owners
because the cog sets `owner_only = True`. Owners are the application/team owner by default, or set
`BOT_OWNER_IDS`. `/dev exec` runs Python as the owner — disable the whole cog with
`BOT_DISABLED_EXTENSIONS='["admin"]'` if you'd rather not ship it.

Mark your own cog owner-only the same way:

```python
class Ops(BaseCog):
    owner_only = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.is_owner(interaction.user)
```

## Start a new bot from the template

```bash
uvx copier copy gh:mohanz1/discord-bot-base my-new-bot   # or: copier copy ./template my-new-bot
cd my-new-bot
uv sync
cp .env.example .env
uv run <your-bot> run
```

The generated project depends on `discord-bot-base`, ships an example `hello` extension, its own
strict `ruff`/`ty`/`pytest` config, and a trimmed CI workflow.

## Add a command

Create `src/<yourbot>/ext/fun.py`:

```python
from __future__ import annotations

import discord
from discord import app_commands

from botbase.cog import BaseCog


class Fun(BaseCog):
    @app_commands.command(description="Roll a die.")
    async def roll(self, interaction: discord.Interaction) -> None:
        import random

        await interaction.response.send_message(f"🎲 {random.randint(1, 6)}")


async def setup(bot) -> None:
    await bot.add_cog(Fun(bot))
```

Make sure your bot's `extension_packages` includes `<yourbot>.ext` (the template does this for you):

```bash
BOT_EXTENSION_PACKAGES='["botbase.ext","yourbot.ext"]'
```

## Enable the database

```bash
uv sync --extra db
export BOT_DATABASE__URL="sqlite+aiosqlite:///bot.sqlite3"
```

The base ships no models — define your own against the re-exported metadata:

```python
# yourbot/models.py
from sqlmodel import Field, SQLModel


class Note(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
```

`auto_create` builds missing tables on startup (good for dev). For real schema history, point
Alembic at `SQLModel.metadata` (the template does this for you), set
`BOT_DATABASE__RUN_MIGRATIONS=true`, and manage revisions with `botbase db revision -m "..."`.

Inside a cog:

```python
from sqlmodel import select

from yourbot.models import Note


class Notes(BaseCog):
    @app_commands.command()
    async def remember(self, interaction: discord.Interaction, key: str, value: str) -> None:
        async with self.bot.session() as s:
            await s.merge(Note(key=key, value=value))
            await s.commit()
        await interaction.response.send_message(f"saved `{key}`", ephemeral=True)
```

## Configuration reference

| Variable | Default | Notes |
| --- | --- | --- |
| `BOT_TOKEN` | – | Required to connect. |
| `BOT_APPLICATION_ID` | `None` | |
| `BOT_OWNER_IDS` | `[]` | JSON list; overrides the app/team owner for `is_owner` and `/dev`. |
| `BOT_MESSAGE_COMMANDS` | `false` | `true` enables `!`-prefix commands (also set `BOT_INTENTS__MESSAGE_CONTENT=true`). |
| `BOT_COMMAND_PREFIX` | `!` | Used only when `BOT_MESSAGE_COMMANDS=true`. |
| `BOT_DEV_GUILD_IDS` | `[]` | JSON list; instant per-guild command sync. |
| `BOT_SYNC_COMMANDS_ON_STARTUP` | `true` | |
| `BOT_EXTENSION_PACKAGES` | `["botbase.ext"]` | JSON list of packages to scan. |
| `BOT_DISABLED_EXTENSIONS` | `[]` | JSON list; matches dotted path or leaf name. |
| `BOT_STRICT_EXTENSION_LOADING` | `false` | Raise if any extension fails. |
| `BOT_LOG_LEVEL` | `INFO` | |
| `BOT_LOG_FORMAT` | `text` | `text` \| `rich` \| `json`. |
| `BOT_PRESENCE_TEXT` | `None` | "Playing ..." text. |
| `BOT_INTENTS__*` | see `config.py` | `members`, `message_content`, `presences`, ... |
| `BOT_DATABASE__URL` | `None` | Enables the DB layer when set. |

## Project layout

```
src/botbase/
  app.py          Bot(commands.Bot) + run()          config.py    typed Settings (pydantic-settings)
  extensions.py   discover_extensions / load / reload  tree.py     CommandTree with a pluggable gate
  cog.py          BaseCog                              logs.py      text / rich / json logging
  errors.py       exception hierarchy                  cli.py       run | version | sync | ext | db
  ext/            meta · help · errors · admin (built-in extensions, each disable-able)
  database/       async engine + session + Alembic wrappers ([db] extra; no models shipped)
alembic/          reference async env.py + alembic.ini (bots keep their own copy)
template/         copier template — a full bot project: cogs, models, Dockerfile, migrations, CI
```

Deployment lives in `template/` (Docker, migrations, a domain model), not here — this repo is the
installable framework.

## Development

```bash
uv run nox            # lint + types + slots + spelling + tests (mirrors CI)
uv run nox -s format  # apply ruff format + autofixes
uv run nox -s template  # render + check the copier template (both DB variants)
uv run pre-commit install
```

CI (`.github/workflows/ci.yml`) runs on every push and PR and blocks merge: `ruff` lint + format
check, `ty`, `slotscheck`, `codespell`, `pytest` on 3.13 and 3.14 with the 90% branch-coverage
gate, and the copier-template smoke test. Turn on branch protection for `main` requiring these
checks. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
