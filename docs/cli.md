# CLI

Installing the package provides a `botbase` command (and `python -m botbase`). A project
scaffolded from the template gets the same commands under its own name.

```
botbase [run | version | sync | ext list | db ...]
```

With no arguments, prints the version table (same as `botbase version`).

## `botbase run`

Start the bot. Reads config from the environment / `.env`.

```bash
botbase run
botbase run --env-file config/prod.env
```

Handles `SIGINT` / `SIGTERM` gracefully — `docker stop` / Kubernetes shutdown is instant.
An invalid token exits with a single clear message, not a traceback.

## `botbase version`

```
discord-bot-base  0.1.0
discord.py        2.7.1
Python            3.14.7
Platform          Linux-…-x86_64
```

## `botbase sync`

Push (or clear) application commands without running the bot. Useful for fixing stale
registrations.

```bash
botbase sync                          # global sync
botbase sync --guild 123456789        # sync to one guild (repeatable)
botbase sync --clear                  # remove all global commands
botbase sync --clear --guild 123456789
```

It logs in, loads extensions, does exactly the sync you asked for, and exits.

## `botbase ext list`

List the extensions that would be discovered from `extension_packages`, marking any that
are disabled.

```
botbase.ext.admin
botbase.ext.errors
botbase.ext.help
botbase.ext.meta  (disabled)
```

## `botbase db ...`

Alembic wrappers. Requires the `db` extra and an `alembic.ini` in the working directory
(the template ships one).

```bash
botbase db upgrade                 # alembic upgrade head
botbase db upgrade <revision>
botbase db downgrade <revision>
botbase db revision -m "add notes"  # --no-autogenerate to skip diffing
botbase db current
```
