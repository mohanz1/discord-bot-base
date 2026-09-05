# Architecture

## The big picture

```
run(Settings)
  ├─ configure_logging(level, format)          # text | rich | json
  ├─ install uvloop / winloop  (best effort)
  ├─ settings.require_token()
  └─ asyncio.run:
       async with Bot(settings):
         ├─ install SIGINT / SIGTERM -> bot.close()
         └─ bot.start(token)
              └─ Bot.setup_hook()               # after login, before the gateway is ready
                   ├─ init database   (if settings.database)
                   ├─ load_extensions(extension_packages, disabled, strict)
                   └─ sync commands   (dev guilds instantly, else global)
```

Everything is driven by one [`Settings`](reference/config.md) object. `run()` is a thin
wrapper; you can also construct [`Bot`](reference/app.md) yourself and call
`await bot.start(token)`.

## Startup order

`Bot.setup_hook()` runs once, after the bot authenticates but before it connects to the
gateway. In order:

1. **Database** — if `settings.database` is set, build the async engine + session factory.
   Then, depending on the [`DatabaseSettings`](reference/config.md):
     - `run_migrations = true` → `alembic upgrade head` (run in a thread);
     - else `auto_create = true` → `SQLModel.metadata.create_all` for any missing tables.
2. **Extensions** — `load_extensions()` discovers and loads every module in
   `extension_packages` (minus `disabled_extensions`). The result is stored on
   `bot.load_report` ([`LoadReport`](reference/extensions.md)).
3. **Command sync** — skipped if `sync_commands_on_startup = false`. If `dev_guild_ids`
   is set, commands are `copy_global_to`'d and synced **per guild** (instant). Otherwise
   a single global `tree.sync()` (can take up to an hour to propagate).

## Dynamic extension loading

This is the part you'll touch most. See [Writing extensions](extensions.md) for the
how-to; the mechanics:

- **Discovery** — [`discover_extensions(package)`](reference/extensions.md) imports the
  package and walks it with `pkgutil` (not a directory scan), so it works the same
  installed, editable, or zipped. Modules and sub-packages whose leaf name starts with
  `_` are skipped; sub-packages are descended into.
- **Loading** — [`load_extensions()`](reference/extensions.md) iterates the discovered
  modules across every configured package, skips anything in `disabled` (matched by full
  dotted path **or** bare leaf name), and calls `bot.load_extension()` on the rest. Each
  failure is caught, logged, and collected; the underlying exception (unwrapped from
  discord.py's `ExtensionFailed`) is kept on the report. With `strict_extension_loading =
  true` a combined [`ExtensionLoadError`](reference/errors.md) is raised at the end.
- **Reloading** — [`reload_all(bot)`](reference/extensions.md) reloads every currently
  loaded extension; `/dev reload` exposes it at runtime.

Each extension module must expose the standard discord.py entry point:

```python
async def setup(bot) -> None:
    await bot.add_cog(MyCog(bot))
```

## Configuration resolution

[`Settings`](reference/config.md) is a `pydantic-settings` model:

- prefix `BOT_`, `.env` file support, `extra="ignore"`;
- nested models use `__` — e.g. `BOT_DATABASE__URL`, `BOT_INTENTS__MESSAGE_CONTENT`;
- list/set/dict fields parse JSON — `BOT_DEV_GUILD_IDS='[123, 456]'`;
- the token is a `SecretStr` and is optional at construction time (so `botbase version`
  and the test suite work without one); `settings.require_token()` raises a clear error
  if it's missing when you actually connect.

`get_settings()` returns a process-wide cached instance. Override any default by
subclassing `Settings` (the template does this to change `extension_packages`).

## Command tree and error handling

- [`BotTree`](reference/tree.md) is the `app_commands.CommandTree` subclass the bot uses.
  Override `interaction_check` (and pass `tree_cls=` to `Bot`) to gate *all* slash
  commands — allow-list, block-list, maintenance mode.
- `BotTree` also holds a pluggable `error_handler`. The built-in `errors` extension sets
  it on load and clears it on unload. That handler:
    - **ignores** `CommandNotFound` (usually a stale registration);
    - turns *expected* errors (`MissingPermissions`, `CommandOnCooldown`, `CheckFailure`,
      …) into a short ephemeral reply;
    - logs anything else with a traceback and sends a generic ephemeral message.
  The reply is wrapped so a dead/expired interaction can't raise a second exception.
- Prefix-command errors are handled by an `on_command_error` listener in the same cog.

## Owner-only cogs

`BaseCog.owner_only` is a class flag. Set it `True` and add an `interaction_check` that
calls `bot.is_owner`; the built-in `/help` reads the flag and hides the cog's commands
from everyone else. The `admin` cog (`/dev …`) uses this. Owners are the Discord
application/team owner by default, or `BOT_OWNER_IDS`.

## Slash-only by default

`message_commands` defaults to `false`: the prefix is `@mention`-only, which does **not**
require the privileged message-content intent. Set `message_commands = true` (and
`BOT_INTENTS__MESSAGE_CONTENT = true`) to enable classic `!`-prefixed commands.
