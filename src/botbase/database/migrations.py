"""Thin wrappers over Alembic's Python API, used by ``botbase db ...``.

Resolution order for ``alembic.ini``: an explicit ``config_path``, then
``./alembic.ini`` in the current working directory. Downstream bots keep their
own ``alembic.ini`` + ``alembic/`` directory at the project root.

The database URL is resolved in ``alembic/env.py``: an explicit ``url=`` passed
here (stored on ``Config.attributes`` under :data:`URL_ATTRIBUTE`) wins, else the
bot's own :class:`~botbase.config.Settings` (``BOT_DATABASE__URL`` from the
environment or ``.env``), so migrations always target the bot's database.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

_log = logging.getLogger("botbase.database.migrations")

URL_ATTRIBUTE = "botbase.database_url"
"""``Config.attributes`` key that carries an explicit database URL to ``env.py``."""


def _config(config_path: str | Path | None = None, url: str | None = None) -> Config:
    candidates = [Path(config_path)] if config_path else []
    candidates.append(Path.cwd() / "alembic.ini")
    for candidate in candidates:
        if candidate.is_file():
            _log.debug("using alembic config at %s", candidate)
            config = Config(str(candidate))
            if url is not None:
                config.attributes[URL_ATTRIBUTE] = url
            return config
    msg = "No alembic.ini found. Run from a project root that has one, or pass config_path."
    raise FileNotFoundError(msg)


def upgrade(revision: str = "head", *, config_path: str | Path | None = None, url: str | None = None) -> None:
    """``alembic upgrade <revision>``."""
    command.upgrade(_config(config_path, url), revision)


def downgrade(revision: str, *, config_path: str | Path | None = None, url: str | None = None) -> None:
    """``alembic downgrade <revision>``."""
    command.downgrade(_config(config_path, url), revision)


def revision(
    message: str,
    *,
    autogenerate: bool = True,
    config_path: str | Path | None = None,
    url: str | None = None,
) -> None:
    """``alembic revision [--autogenerate] -m <message>``."""
    command.revision(_config(config_path, url), message=message, autogenerate=autogenerate)


def current(*, config_path: str | Path | None = None, url: str | None = None) -> None:
    """``alembic current`` (verbose)."""
    command.current(_config(config_path, url), verbose=True)
