# discord-bot-base

A modern, `uv`-first foundation for Discord bots. It gives you the boring-but-important
parts once, so each new bot is just cogs and config.

- **Dynamic extension loading** — drop a module in a package; it's discovered and loaded
  (works installed, editable, or zipped — no directory scanning).
- **Typed, env-first config** — `pydantic-settings`, `BOT_`-prefixed variables, `.env`
  support, `SecretStr` token.
- **A `Bot` subclass** that wires intents, prefix, a custom command tree, extension
  loading, command syncing, uptime, and an optional async database from your settings.
- **Built-in commands** — `/ping`, `/about`, `/uptime`, `/help` (generated from the
  command tree), a global error handler, and an owner-only `/dev` group
  (`reload`, `load`, `unload`, `sync`, `exec`).
- **Optional async DB layer** (`[db]` extra) — SQLModel + SQLAlchemy 2 + `aiosqlite`
  with the async Alembic wiring done. You bring the models.
- **A `copier` template** that scaffolds a full bot project — cogs, models, `Dockerfile`,
  migrations, CI.

## Two ways to use it

| | |
| --- | --- |
| **As a dependency** | `uv add discord-bot-base` in your own project, point `extension_packages` at your `ext` package, write cogs. |
| **From the template** | `uvx copier copy gh:mohanz1/discord-bot-base my-bot` — a complete, CI-ready project. |

Start at [Getting started](getting-started.md). To understand how the pieces fit,
read [Architecture](architecture.md).

Requires Python 3.13+.
