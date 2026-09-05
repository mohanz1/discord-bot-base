"""Thin wrappers over Alembic's Python API, used by ``botbase db ...``.

Resolution order for ``alembic.ini``: an explicit ``config_path``, then
``./alembic.ini`` in the current working directory. Downstream bots keep their
own ``alembic.ini`` + ``alembic/`` directory at the project root.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

_log = logging.getLogger("botbase.database.migrations")


def _config(config_path: str | Path | None = None) -> Config:
    candidates = [Path(config_path)] if config_path else []
    candidates.append(Path.cwd() / "alembic.ini")
    for candidate in candidates:
        if candidate.is_file():
            _log.debug("using alembic config at %s", candidate)
            return Config(str(candidate))
    msg = "No alembic.ini found. Run from a project root that has one, or pass config_path."
    raise FileNotFoundError(msg)


def upgrade(revision: str = "head", *, config_path: str | Path | None = None) -> None:
    """``alembic upgrade <revision>``."""
    command.upgrade(_config(config_path), revision)


def downgrade(revision: str, *, config_path: str | Path | None = None) -> None:
    """``alembic downgrade <revision>``."""
    command.downgrade(_config(config_path), revision)


def revision(message: str, *, autogenerate: bool = True, config_path: str | Path | None = None) -> None:
    """``alembic revision [--autogenerate] -m <message>``."""
    command.revision(_config(config_path), message=message, autogenerate=autogenerate)


def current(*, config_path: str | Path | None = None) -> None:
    """``alembic current`` (verbose)."""
    command.current(_config(config_path), verbose=True)
