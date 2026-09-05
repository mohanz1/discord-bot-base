# CLAUDE.md

Guidance for AI agents working in this repository.

## What this is

`discord-bot-base` is a **framework**, not a bot. It's published to PyPI as
`discord-bot-base` (import name `botbase`) and also carries a `copier` template in
`template/` that scaffolds a full bot project.

Keep the two concerns separate:

- **`src/botbase/`** — reusable machinery. No bot-specific features, no domain models, no
  deployment files. If a change only makes sense for one bot, it belongs downstream or in
  the template, not here.
- **`template/`** — a complete example bot project (cogs, models, `Dockerfile`,
  migrations, CI). Jinja-templated; excluded from the base's `ruff`/`ty`.

## Layout

```
src/botbase/
  app.py         Bot(commands.Bot) + run() + graceful shutdown
  config.py      Settings / IntentsSettings / DatabaseSettings (pydantic-settings)
  extensions.py  discover_extensions / load_extensions / reload_all
  tree.py        BotTree — overridable interaction_check + pluggable error_handler
  cog.py         BaseCog (owner_only flag, settings/db/log helpers)
  logs.py        configure_logging: text | rich | json
  errors.py      exception hierarchy
  cli.py         botbase run | version | sync | ext list | db ...
  utils.py       plural, humanize_timedelta
  database/      async engine + session + Alembic wrappers ([db] extra; NO models)
  ext/           meta, help, errors, admin — built-in extensions, each disable-able
alembic/         reference async env.py + alembic.ini (no versions)
tests/           116 tests; fixtures in tests/conftest.py
docs/            mkdocs-material site (published to GitHub Pages)
```

Read `docs/architecture.md` before making structural changes.

## Conventions

- **Run `uv run nox` before every push** — it's exactly what CI runs: `ruff` (lint +
  format), `ty`, `slotscheck`, `codespell`, `pytest`. CI also runs the 3.13/3.14 test
  matrix and the copier-template smoke test.
- **Coverage gate is 90% branch.** New behaviour needs tests.
- **Test our logic, not discord.py.** Use the fakes in `tests/conftest.py`
  (`FakeInteraction`, etc.); `# pragma: no cover` is only for blocks that need a live
  gateway (`async with Bot(): bot.start()`).
- Docstrings are required (`ruff` D rules, numpy convention). They render on the docs
  site via `mkdocstrings`, so keep them accurate.
- Lazy imports are fine (`PLC0415` is ignored) — used for optional deps and CLI startup.
- Runtime deps → `[project.dependencies]`; optional → an extra (`db`, `speedups`,
  `rich`); dev tooling → the `dev` dependency group; docs tooling → the `docs` group.
- `ruff`/`ty` are pinned to exact versions in the `dev` group; bump them together with
  the matching `.pre-commit-config.yaml` `rev:`.
- Update `CHANGELOG.md` under `[Unreleased]` for anything user-facing.
- GitHub Actions are pinned to major tags where the action publishes them
  (`actions/*`), otherwise a full version (`setup-uv@vX.Y.Z`).

## Gotchas

- **Python 3.14 + discord.py + uvloop** emit deprecation warnings
  (`iscoroutinefunction`, `AbstractEventLoopPolicy`); `pytest` `filterwarnings` has
  targeted ignores. Don't turn those into a blanket ignore.
- **`BotTree.on_error`** carries a `# ty: ignore[invalid-method-override]` — ty (beta)
  is over-strict about `self`/generic variance on this documented discord.py override.
- **discord.py's `load_extension` swaps `sys.modules` entries** for a fresh module
  object. `tests/conftest.py` has a `_stable_ext_modules` autouse fixture that restores
  them so `isinstance` checks stay valid across tests.
- **Don't run `nox`'s test matrix with `-p`** — `@nox.session(python=[...])` +
  `venv_backend="none"` doesn't produce selectable per-version sessions. The matrix is
  CI's job (`setup-uv` `python-version` input).
- **`get_settings()` is `lru_cache`d** — tests clear it via the `_isolated_env` fixture,
  which also `chdir`s to a tmp dir so the developer's real `.env` is never read.

## Common tasks

| Task | Where |
| --- | --- |
| Add a config option | `src/botbase/config.py` (+ `docs/configuration.md`, `.env.example`) |
| Add a built-in command | new module in `src/botbase/ext/` (+ tests, `CHANGELOG`) |
| Change startup behaviour | `Bot.setup_hook` / `run()` in `src/botbase/app.py` |
| Add a CLI subcommand | `_build_parser()` in `src/botbase/cli.py` |
| Change what the template generates | `template/` (verify with `uv run nox -s template`) |
| Build the docs | `uv run nox -s docs` → `site/` |
