# Configuration

All configuration is environment variables, optionally via a `.env` file in the working
directory. Prefix everything with `BOT_`. Nested settings use `__`. List/set/dict values
are JSON.

```dotenv
BOT_TOKEN=your-token
BOT_LOG_FORMAT=rich
BOT_DEV_GUILD_IDS=[123456789012345678]
BOT_INTENTS__MESSAGE_CONTENT=true
BOT_DATABASE__URL=sqlite+aiosqlite:///bot.sqlite3
```

## Top-level

| Variable | Type | Default | Notes |
| --- | --- | --- | --- |
| `BOT_TOKEN` | secret | – | Required to connect. Never logged; never bake it into an image. |
| `BOT_APPLICATION_ID` | int | `None` | Usually auto-detected after login. |
| `BOT_OWNER_IDS` | JSON list[int] | `[]` | Overrides the app/team owner for `bot.is_owner` and `/dev`. |
| `BOT_MESSAGE_COMMANDS` | bool | `false` | `true` enables `!`-prefix commands (also set `BOT_INTENTS__MESSAGE_CONTENT=true`). |
| `BOT_COMMAND_PREFIX` | str | `!` | Only used when `BOT_MESSAGE_COMMANDS=true`. |
| `BOT_DEV_GUILD_IDS` | JSON list[int] | `[]` | Sync commands to these guilds instantly instead of a slow global sync. |
| `BOT_SYNC_COMMANDS_ON_STARTUP` | bool | `true` | Set `false` and sync manually with `botbase sync`. |
| `BOT_EXTENSION_PACKAGES` | JSON list[str] | `["botbase.ext"]` | Dotted packages to scan for extensions. |
| `BOT_DISABLED_EXTENSIONS` | JSON list[str] | `[]` | Skip these; matches full dotted path or bare leaf name. |
| `BOT_STRICT_EXTENSION_LOADING` | bool | `false` | Raise if any extension fails to load. |
| `BOT_LOG_LEVEL` | str | `INFO` | |
| `BOT_LOG_FORMAT` | str | `text` | `text` \| `rich` \| `json`. `rich` falls back to `text` if `rich` isn't installed. |
| `BOT_PRESENCE_TEXT` | str | `None` | Sets a "Playing …" status. |

## Intents (`BOT_INTENTS__*`)

Starts from `discord.Intents.default()` (set `BOT_INTENTS__DEFAULT=false` to start from
`none()`), then applies:

| Variable | Default |
| --- | --- |
| `BOT_INTENTS__MEMBERS` | `false` |
| `BOT_INTENTS__MESSAGE_CONTENT` | `false` |
| `BOT_INTENTS__PRESENCES` | `false` |
| `BOT_INTENTS__REACTIONS` | `true` |
| `BOT_INTENTS__VOICE_STATES` | `false` |
| `BOT_INTENTS__TYPING` | `false` |

The three privileged intents (`members`, `message_content`, `presences`) must also be
enabled in the Discord Developer Portal.

## Database (`BOT_DATABASE__*`)

Setting `BOT_DATABASE__URL` enables the DB layer. Requires the `db` extra
(`uv sync --extra db`).

| Variable | Default | Notes |
| --- | --- | --- |
| `BOT_DATABASE__URL` | `sqlite+aiosqlite:///bot.sqlite3` | SQLAlchemy async URL. Use an async driver (`+aiosqlite`, `+asyncpg`). |
| `BOT_DATABASE__ECHO` | `false` | Echo SQL to the logger. |
| `BOT_DATABASE__AUTO_CREATE` | `true` | Create missing tables on startup. Good for development. |
| `BOT_DATABASE__RUN_MIGRATIONS` | `false` | Run `alembic upgrade head` on startup. Takes precedence over `auto_create`. |

See [Recipes → Database](recipes.md#database) for models and queries.

## Overriding defaults in code

Subclass `Settings` when an env var isn't the right home for a default:

```python
from botbase import Settings as BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    extension_packages: list[str] = Field(
        default_factory=lambda: ["botbase.ext", "my_bot.ext"],
    )
    log_format: str = "rich"
```
