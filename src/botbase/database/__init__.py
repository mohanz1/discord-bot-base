"""Optional async database layer (SQLModel + SQLAlchemy 2).

Importing this package raises :class:`~botbase.errors.MissingDependencyError`
with an actionable message if the ``[db]`` extra is not installed.

The base ships the *machinery* only — no models. Define your tables against the
re-exported :data:`SQLModel` metadata in your own bot and point Alembic at it.
"""

from __future__ import annotations

try:
    import sqlalchemy as _sqlalchemy  # noqa: F401
    import sqlmodel as _sqlmodel  # noqa: F401
except ModuleNotFoundError as exc:  # pragma: no cover - exercised via the [db] extra matrix
    from botbase.errors import MissingDependencyError

    raise MissingDependencyError("The database layer", "db") from exc  # noqa: EM101 - structured args, not a message

from sqlmodel import SQLModel

from botbase.database.engine import build_engine, init_models, make_sessionmaker, session

__all__ = [
    "SQLModel",
    "build_engine",
    "init_models",
    "make_sessionmaker",
    "session",
]
