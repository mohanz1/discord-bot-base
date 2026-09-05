# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report privately via GitHub's [private vulnerability reporting](https://github.com/mohanz1/discord-bot-base/security/advisories/new)
(Security → Advisories → *Report a vulnerability*), or email the maintainer.

You should get an acknowledgement within a few days. Once a fix is ready we'll
publish a GitHub Security Advisory and a patch release, crediting you unless you
ask otherwise.

## Supported versions

Until `1.0.0`, only the latest `0.x` release receives security fixes.

## Notes for operators

- **`botbase.ext.admin` ships an owner-only `/dev exec`** that runs arbitrary
  Python in the bot process. It is gated by `bot.is_owner` on every path, but it
  is still remote code execution for whoever your owner IDs are. Set
  `BOT_OWNER_IDS` explicitly, keep that list minimal, and disable the cog
  entirely with `BOT_DISABLED_EXTENSIONS='["admin"]'` if you don't need it.
- The bot **token** is read from the environment / `.env` only and is never
  written to the image or logs (`SecretStr`). Keep `.env` out of version control
  (`.gitignore` already excludes it).
- Run the container with a read-only root filesystem and a writable volume only
  where you need state, e.g.
  `docker run --read-only --tmpfs /tmp -v botdata:/data ...`.
