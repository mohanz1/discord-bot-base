# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Documentation site (mkdocs-material) — getting started, architecture,
  configuration, extension guide, recipes, CLI, deployment, and an auto-generated
  API reference. Built with `--strict` in CI and deployed to GitHub Pages on
  push to `main`.
- `CLAUDE.md` — repository guidance for AI agents.

### Changed

- Bumped GitHub Actions to current majors (`checkout` v7, `setup-uv` v10,
  `upload-artifact` v7, `download-artifact` v8, `action-gh-release` v3,
  `docker/*` v4/v7) and `pre-commit-hooks` to v6.
- Expanded `.gitignore` with the common Python defaults.
- Template CI now pins the interpreter via `setup-uv` so the 3.13/3.14 matrix
  actually tests both.

## [0.1.0] - 2026-09-05

### Added

- `Bot` (`commands.Bot` subclass) wired from env-first `Settings`
  (`pydantic-settings`, `BOT_` prefix, `SecretStr` token).
- Dynamic extension discovery/loading (`discover_extensions`, `load_extensions`,
  `reload_all`) that works installed, editable, or zipped.
- `BaseCog` with `settings` / `db` / namespaced logger.
- Built-in extensions:
  - `meta` — `/ping` (gateway + REST + event-loop-lag with a bar meter),
    `/about` (versions/uptime/latency publicly; host + reach stats owner-only,
    with a live Refresh button), `/uptime`.
  - `help` — `/help [command]` generated from the command tree (grouped by cog,
    autocomplete, per-parameter detail); hides commands the caller cannot use.
  - `errors` — global slash + prefix error handling; ignores stale
    `CommandNotFound`.
  - `admin` — `/dev` group: `reload` (argument or a select-menu picker), `load`,
    `unload`, `sync`, and `exec` (Python eval with a multi-line modal). Visible to
    all, runnable only by `is_owner` (a cog `interaction_check`); `BaseCog.owner_only`
    tells `/help` to hide it from everyone else.
- Optional async database *machinery* behind the `[db]` extra: SQLModel +
  SQLAlchemy 2 + `aiosqlite` + reusable async Alembic `env.py`
  (`render_as_batch` for SQLite). No models shipped — bots bring their own.
- CLI: `botbase run | version | sync | ext list | db {upgrade,downgrade,revision,current}`.
- `Settings.owner_ids` (`BOT_OWNER_IDS`) and `Settings.message_commands`
  (default off → slash-only, no privileged message-content intent needed).
- Structured logging (`text` / `rich` / `json`).
- Graceful `SIGINT` / `SIGTERM` shutdown in `run()` (instant container stop).
- Tooling: `ruff` (lint + format), `ty`, `slotscheck`, `codespell`, `pytest`
  (branch coverage gate at 90%), `nox`, `pre-commit`, least-privilege GitHub
  Actions (lint / types / test matrix 3.13 + 3.14 / copier-template smoke) and a
  PyPI Trusted Publishing release workflow.
- Community health: `CONTRIBUTING.md`, `SECURITY.md`, issue / PR templates,
  `CODEOWNERS`, `.gitattributes`.
- `copier` template in `template/` that scaffolds a **full bot project** —
  cogs, models, `Dockerfile` (uv, non-root, OCI labels), Alembic migrations, and
  CI — verified end to end by the template smoke test.

[Unreleased]: https://github.com/mohanz1/discord-bot-base/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mohanz1/discord-bot-base/releases/tag/v0.1.0
