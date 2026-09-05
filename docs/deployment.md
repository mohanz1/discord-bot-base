# Deployment

Deployment artifacts live in a **project scaffolded from the template**, not in the
framework package. A generated project ships a production `Dockerfile`, `.dockerignore`,
Alembic migrations, and CI.

## Docker

```bash
docker build -t my-bot .
docker run --rm --env-file .env my-bot
```

The template's `Dockerfile`:

- multi-stage — `uv` resolves and installs into a `.venv` in a build stage; the runtime
  stage is `python:<floor>-slim` with just the venv (and Alembic assets if you enabled
  the DB);
- runs as a non-root `bot` user;
- has OCI labels for provenance;
- `ENTRYPOINT` is your bot's console script, so `docker run <image>` starts it. Use
  `docker run --entrypoint botbase <image> version` (or `db upgrade`, …) for the CLI.

Config is read from the environment only — nothing is baked into the image. For a
hardened runtime:

```bash
docker run --read-only --tmpfs /tmp -v botdata:/data --env-file .env my-bot
```

## Graceful shutdown

`run()` installs `SIGINT` / `SIGTERM` handlers that call `bot.close()`, so `docker stop`
and Kubernetes pod termination shut down cleanly within a fraction of a second instead of
waiting for the kill timeout.

## Migrations in production

- **Development:** `BOT_DATABASE__AUTO_CREATE=true` (the default) creates missing tables
  on startup. Fine until your schema settles.
- **Production:** commit real migrations. Run them either
  - on startup: `BOT_DATABASE__RUN_MIGRATIONS=true`, or
  - as a separate step before rollout: `docker run --entrypoint botbase my-bot db upgrade`.

## Secrets

`BOT_TOKEN` is a `SecretStr` — never logged, never written to the image. Inject it as an
environment variable or a mounted secret; keep `.env` out of version control
(`.gitignore` already excludes it).
